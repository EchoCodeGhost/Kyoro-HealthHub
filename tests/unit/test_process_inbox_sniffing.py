# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit-Tests für process_inbox.py's Dateiname-Erkennung (_sniff_csv, _sniff_pdf).

Hintergrund: Hilo-Blutdruckberichte und RENPHO-CSVs hatten keine
Sniff-Regel und fielen entweder auf den falschen Handler zurück
(import_lab_results.py statt import_hilo_pdf.py) oder wurden als
"unbekannte Quelle" stillschweigend übersprungen. Beide Dateien landeten
trotzdem in _inbox/processed/ — ohne je beim richtigen Importer anzukommen.
Diese Tests fixieren die erwartete Zuordnung für jede unterstützte Quelle,
damit eine neue Quelle, die vergessen wird zu verdrahten, sofort aus dem
grünen CI-Lauf herausfällt statt erst beim nächsten echten Datei-Drop.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from process_inbox import _sniff_csv, _sniff_pdf, _sniff_json, _sniff_txt  # noqa: E402


class TestSniffCsv:
    def test_kyoro_symptomtrack(self):
        assert _sniff_csv(Path("symptom-history-30d-20260705-1424.csv")) == "kyoro_st"

    def test_symptomtagebuch(self):
        assert _sniff_csv(Path("symptomtagebuch_7_tage_csv_bericht.csv")) == "symptomtagebuch"

    def test_womanlog(self):
        assert _sniff_csv(Path("womanlog_data_report__export.csv")) == "womanlog"

    def test_bearable(self):
        assert _sniff_csv(Path("bearable-export-22-06-2026.csv")) == "bearable"

    def test_hrv4training(self):
        assert _sniff_csv(Path("hrv4t_export.csv")) == "hrv4training"

    def test_ecowitt(self):
        assert _sniff_csv(Path("ecowitt_2026-07.csv")) == "ecowitt"

    def test_sleep_cycle(self):
        assert _sniff_csv(Path("sleepdata-2026-07-11.csv")) == "sleep_cycle"

    def test_beurer_health_manager(self):
        assert _sniff_csv(Path("HealthManager Pro Export - 18.05.2023 - 05.06.2024.csv")) == "health_manager"

    def test_renpho(self):
        assert _sniff_csv(Path("RENPHO Health-_20250711_191410.csv")) == "renpho"

    def test_fddb(self):
        assert _sniff_csv(Path("diary_05_07_2025.csv")) == "fddb"

    def test_unknown_csv_returns_none(self, tmp_path):
        f = tmp_path / "some_random_export.csv"
        f.write_text("col_a,col_b\n1,2\n")
        assert _sniff_csv(f) is None


class TestSniffPdf:
    def test_hilo_blood_pressure(self, tmp_path):
        f = tmp_path / "Hilo_Blutdruckbericht_KW322023.pdf"
        f.write_bytes(b"%PDF-1.4 fake")
        assert _sniff_pdf(f) == "hilo"

    def test_medical_motion_by_prefix(self, tmp_path):
        f = tmp_path / "mm_report_05072024.pdf"
        f.write_bytes(b"%PDF-1.4 fake")
        assert _sniff_pdf(f) == "medical_motion"

    def test_medical_motion_by_content(self, tmp_path):
        f = tmp_path / "report_20240705.pdf"
        f.write_bytes("Medical Motion Physiotherapie Bericht".encode("utf-8"))
        assert _sniff_pdf(f) == "medical_motion"

    def test_unrecognized_pdf_returns_none(self, tmp_path):
        f = tmp_path / "irgendein_befund.pdf"
        f.write_bytes(b"%PDF-1.4 fake lab report content")
        assert _sniff_pdf(f) is None


class TestSniffJson:
    def test_shotsy_by_extension(self, tmp_path):
        f = tmp_path / "data_070525.shotsyjson"
        f.write_text('{"injections": []}')
        assert _sniff_json(f) == "shotsy"

    def test_unknown_json_returns_none(self, tmp_path):
        f = tmp_path / "export.json"
        f.write_text('{"foo": "bar"}')
        assert _sniff_json(f) is None


class TestSniffTxt:
    def test_kubios(self, tmp_path):
        f = tmp_path / "kubios_export.txt"
        f.write_text("KubiosHRV Analysis type: readiness")
        assert _sniff_txt(f) == "kubios"

    def test_unknown_txt_returns_none(self, tmp_path):
        f = tmp_path / "notes.txt"
        f.write_text("just some notes")
        assert _sniff_txt(f) is None
