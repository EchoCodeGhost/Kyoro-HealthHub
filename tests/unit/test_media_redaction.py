# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests für modules.media_redaction (synthetische Dateien, Werkzeuge optional)."""
import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from modules import address_redaction as ar
from modules import media_redaction as mr
from modules import location_redaction as lr
from modules import name_redaction as nr

needs_ocr = pytest.mark.skipif(not mr.ocr_available(), reason="tesseract fehlt")
needs_pdf = pytest.mark.skipif(not (mr.bbox_available() and mr.render_available()), reason="poppler fehlt")


@pytest.fixture(autouse=True)
def _no_config(monkeypatch, tmp_path):
    monkeypatch.setattr(ar, "_config_path", lambda: tmp_path / "missing.json")
    monkeypatch.setattr(nr, "_config_path", lambda: tmp_path / "missing.json")
    monkeypatch.setattr(nr, "_identity_db_path", lambda: tmp_path / "missing.db")
    monkeypatch.setattr(lr, "_config_path", lambda: tmp_path / "missing.json")


def _font():
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",):
        if Path(p).exists():
            return ImageFont.truetype(p, 36)
    return ImageFont.load_default()


def _address_image() -> Image.Image:
    img = Image.new("RGB", (1200, 460), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 40), "Befund vom 01.02.2026", font=_font(), fill="black")
    d.text((40, 120), "Musterstrasse 12", font=_font(), fill="black")
    d.text((40, 180), "12345 Musterstadt", font=_font(), fill="black")
    d.text((40, 260), "Patientin: Erika Mustermann", font=_font(), fill="black")
    d.text((40, 320), "Tel. 0171 1234567", font=_font(), fill="black")
    d.text((40, 380), "GPS: 48.1351, 11.5820", font=_font(), fill="black")
    return img


def _text_pdf(path: Path, lines: list[str]) -> None:
    content = "BT /F1 14 Tf 72 700 Td 18 TL " + " ".join(f"({ln}) Tj T*" for ln in lines) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        "<< /Author (Max Muster) /Title (Befund) >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info 6 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(out)


def test_image_exif_gps_reported_and_removed(tmp_path):
    img = Image.new("RGB", (64, 64), "white")
    exif = Image.Exif()
    exif[0x013B] = "Max Muster"
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = "N", (48.0, 30.0, 0.0), "E", (11.0, 30.0, 0.0)
    src, dst = tmp_path / "a.jpg", tmp_path / "b.jpg"
    img.save(src, "JPEG", exif=exif)
    rep = mr.report_image(src)
    assert rep["has_gps"] and "Artist" in rep["pii_tags"] and "values" not in rep
    assert "values" in mr.report_image(src, show_values=True)
    res = mr.scrub_image(src, dst, ocr="never")
    assert len(res.locations) == 1
    rep2 = mr.report_image(dst)
    assert not rep2["has_gps"] and not rep2["pii_tags"] and rep2["exif_tags"] == []


@needs_ocr
def test_image_visible_address_blacked_out(tmp_path):
    src, dst = tmp_path / "a.png", tmp_path / "b.png"
    _address_image().save(src)
    res = mr.scrub_image(src, dst)
    assert res.addresses == 1 and res.names == 1 and res.identifiers == 1 and res.places == 1
    assert res.residual == 0
    words = " ".join(w.text for w in mr.ocr_words(Image.open(dst)))
    assert "Musterstrasse" not in words and "Mustermann" not in words and "1234567" not in words
    assert "11.5820" not in words and "Befund" in words


@needs_pdf
def test_text_pdf_metadata_active_content_and_address(tmp_path):
    src, dst = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _text_pdf(src, ["Befund", "Musterstrasse 12", "12345 Musterstadt", "Frau Dr. med. Beispiel",
                    "Tel. 0171 1234567", "GPS: 48.1351, 11.5820", "CRP 1.2 mg/l"])
    rep = mr.report_pdf(src)
    assert rep["info_keys"] and rep["open_action"] and rep["addresses_in_text_layer"] == 1
    assert rep["names_in_text_layer"] == 1 and rep["identifiers_in_text_layer"] == 1
    assert rep["places_in_text_layer"] == 1
    res = mr.scrub_pdf_full(src, dst, ocr="never")
    assert res.addresses == 1 and res.names == 1 and res.identifiers == 1 and res.places == 1
    assert res.pages_redacted == 1 and res.residual == 0
    out = " ".join(w.text for _, ws in mr.pdf_text_words(dst) for w in ws)
    assert "Beispiel" not in out and "1234567" not in out and "11.5820" not in out
    rep2 = mr.report_pdf(dst)
    assert not rep2["findings"] and not rep2["open_action"] and rep2["info_keys"] == []


@needs_pdf
def test_pdf_without_address_keeps_text_layer(tmp_path):
    src, dst = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _text_pdf(src, ["Befund", "CRP 1.2 mg/l", "Vitamin D 25 ng/ml, normal im Verlauf"])
    res = mr.scrub_pdf_full(src, dst, ocr="never")
    assert res.addresses == 0 and res.pages_redacted == 0
    assert mr.report_pdf(dst)["has_text_layer"]


@needs_pdf
@needs_ocr
def test_scanned_pdf_address_removed_via_ocr(tmp_path):
    src, dst = tmp_path / "scan.pdf", tmp_path / "out.pdf"
    _address_image().save(src, "PDF", resolution=150)
    res = mr.scrub_pdf_full(src, dst)
    assert res.ocr_used and res.addresses == 1 and res.names == 1 and res.identifiers == 1
    assert res.places == 1 and res.residual == 0


def test_missing_tools_degrade_to_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "ocr_available", lambda: False)
    src, dst = tmp_path / "a.jpg", tmp_path / "b.jpg"
    Image.new("RGB", (32, 32)).save(src)
    res = mr.scrub_image(src, dst)
    assert res.warnings and dst.exists()


@needs_pdf
def test_names_can_be_kept_and_extra_names_removed(tmp_path):
    src, dst = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _text_pdf(src, ["Befund fuer Max Muster", "Frau Beispiel", "CRP 1.2 mg/l und weitere Werte"])
    res = mr.scrub_pdf_full(src, dst, ocr="never", redact_names=False)
    assert res.names == 0 and res.pages_redacted == 0
    res = mr.scrub_pdf_full(src, dst, ocr="never", extra_names=["Max Muster"])
    assert res.names >= 1 and res.residual == 0
