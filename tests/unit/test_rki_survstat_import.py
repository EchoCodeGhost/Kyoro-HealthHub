# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for the RKI SurvStat OLAP/MDX SOAP import in import_outbreak_data.py.

The original SurvStat integration called a `GetResultRowData` operation that no
longer exists (RKI redesigned the API around an OLAP/MDX cube-query model) and
used the wrong WS-Addressing action namespace, so it always returned zero rows.
Fixed after reverse-engineering the live WSDL/XSDs. Network calls
are mocked here (safe to run anywhere) by monkeypatching `_rki_soap_call`; the
XML-parsing and cutoff-window logic is exercised against a synthetic but
schema-accurate GetOlapDataResponse body.
"""

import sqlite3
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA
import importers.import_outbreak_data as m


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def _fake_body(columns: list[str], row_caption: str, values: list[str]) -> ET.Element:
    """Builds a synthetic <s:Body> matching a real GetOlapDataResponse."""
    cols_xml = "".join(
        f'<b:QueryResultColumn><b:Caption>{c}</b:Caption>'
        f'<b:ColumnName>x</b:ColumnName></b:QueryResultColumn>'
        for c in columns
    )
    vals_xml = "".join(f"<b:string>{v}</b:string>" for v in values)
    envelope = f"""<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
<s:Body><GetOlapDataResponse xmlns="http://tools.rki.de/SurvStat/">
<GetOlapDataResult xmlns:b="http://schemas.datacontract.org/2004/07/Rki.SurvStat.WebService.Contracts.Mdx"
                    xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
<b:Columns>{cols_xml}</b:Columns>
<b:QueryResults>
<b:QueryResultRow><b:Caption>{row_caption}</b:Caption><b:RowName>x</b:RowName>
<b:Values>{vals_xml}</b:Values></b:QueryResultRow>
</b:QueryResults>
</GetOlapDataResult>
</GetOlapDataResponse></s:Body>
</s:Envelope>"""
    root = ET.fromstring(envelope)
    return root.find("{http://www.w3.org/2003/05/soap-envelope}Body")


def test_parse_olap_grid_extracts_counts_by_year_and_week():
    body = _fake_body(["2025", "2026"], "29", ["10", "24"])

    grid = m._rki_parse_olap_grid(body)

    assert grid == {(2025, 29): 10, (2026, 29): 24}


def test_parse_olap_grid_excludes_zero_cells():
    """A week/year cell with 0 cases must not appear at all (matches the old
    fetch_rki_survstat behavior of only storing counts > 0)."""
    body = _fake_body(["2026"], "30", ["0"])

    grid = m._rki_parse_olap_grid(body)

    assert grid == {}


def test_parse_olap_grid_returns_empty_dict_when_result_missing():
    body = ET.fromstring(
        '<s:Body xmlns:s="http://www.w3.org/2003/05/soap-envelope"/>'
    )
    assert m._rki_parse_olap_grid(body) == {}


def test_olap_data_request_omits_bundesland_filter_when_none():
    xml = m._rki_olap_data_request("Borreliose", None)
    assert xml.count("KeyValueOfFilterCollectionKeyFilterMemberCollectionb2rWaiIW") == 2
    assert m._RKI_HIER_BUNDESLAND not in xml.split("HierarchyFilters")[0]


def test_olap_data_request_includes_bundesland_filter_when_given():
    xml = m._rki_olap_data_request("Borreliose", "09")
    assert xml.count("KeyValueOfFilterCollectionKeyFilterMemberCollectionb2rWaiIW") == 4
    assert f"{m._RKI_HIER_BUNDESLAND}.&amp;[09]" in xml


def test_fetch_rki_survstat_defaults_to_all_16_bundeslaender(monkeypatch):
    """No hardcoded single federal state — some diseases (e.g. Borreliose)
    are only notifiable in a subset of states via their own Landesmelde-
    verordnung, so every installation needs the full picture, not just the
    configured home state (found while investigating why Bayern-only data
    only goes back to 2016 -- other states go back to 2001)."""
    this_year, this_week, _ = date.today().isocalendar()
    body = _fake_body([str(this_year)], f"{this_week:02d}", ["24"])
    monkeypatch.setattr(m, "_rki_soap_call", lambda op, req: body)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)

    conn = _fresh_conn()
    inserted = m.fetch_rki_survstat(conn)

    # Deutschland + all 16 Bundeslaender.
    assert inserted == (1 + len(m.RKI_BUNDESLAENDER)) * len(m.RKI_DISEASES)
    regions = {r for (r,) in conn.execute(
        "SELECT DISTINCT region FROM outbreak_events WHERE source='rki_survstat'"
    )}
    assert regions == {"Deutschland", *m.RKI_BUNDESLAENDER}


def test_fetch_rki_survstat_inserts_current_week_and_is_idempotent(monkeypatch):
    this_year, this_week, _ = date.today().isocalendar()
    old_year = this_year - 10  # outside the default ~1 year rolling window

    body = _fake_body([str(old_year), str(this_year)], f"{this_week:02d}", ["999", "24"])
    monkeypatch.setattr(m, "_rki_soap_call", lambda op, req: body)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)

    conn = _fresh_conn()
    inserted = m.fetch_rki_survstat(conn, bundeslaender=["Bayern"])

    # 2 regions (Deutschland + Bayern) x 12 diseases, only the current-week
    # cell survives the default rolling window -> old_year cell excluded.
    assert inserted == 2 * len(m.RKI_DISEASES)

    row = conn.execute(
        "SELECT region, date_start, disease FROM outbreak_events "
        "WHERE source='rki_survstat' AND disease='Borreliose' AND region='Bayern'"
    ).fetchone()
    assert row == ("Bayern", date.fromisocalendar(this_year, this_week, 1).isoformat(), "Borreliose")

    old_year_rows = conn.execute(
        "SELECT COUNT(*) FROM outbreak_events WHERE source='rki_survstat' "
        "AND date_start LIKE ?", (f"{old_year}-%",)
    ).fetchone()[0]
    assert old_year_rows == 0

    second = m.fetch_rki_survstat(conn, bundeslaender=["Bayern"])
    assert second == 0


def test_fetch_rki_survstat_full_history_includes_old_weeks(monkeypatch):
    this_year, this_week, _ = date.today().isocalendar()
    old_year = this_year - 10

    body = _fake_body([str(old_year), str(this_year)], f"{this_week:02d}", ["999", "24"])
    monkeypatch.setattr(m, "_rki_soap_call", lambda op, req: body)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)

    conn = _fresh_conn()
    inserted = m.fetch_rki_survstat(conn, bundeslaender=["Bayern"], weeks_back=100_000)

    assert inserted == 2 * len(m.RKI_DISEASES) * 2  # both weeks now included


def test_fetch_rki_survstat_skips_unknown_bundesland_name(monkeypatch, capsys):
    this_year, this_week, _ = date.today().isocalendar()
    body = _fake_body([str(this_year)], f"{this_week:02d}", ["24"])
    monkeypatch.setattr(m, "_rki_soap_call", lambda op, req: body)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)

    conn = _fresh_conn()
    inserted = m.fetch_rki_survstat(conn, bundeslaender=["Nirgendwo"])

    # Deutschland only -- the unknown name never became a region filter.
    assert inserted == len(m.RKI_DISEASES)
    regions = {r for (r,) in conn.execute(
        "SELECT DISTINCT region FROM outbreak_events WHERE source='rki_survstat'"
    )}
    assert regions == {"Deutschland"}
