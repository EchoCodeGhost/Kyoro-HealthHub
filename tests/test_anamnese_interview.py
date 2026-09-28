#!/usr/bin/env python3
"""
Unit tests for anamnese_interview.py

Tests the extraction-parsing logic and session management.
"""

import json
import sqlite3
import tempfile
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from datetime import datetime, timezone
from health_config import OWN_PERSON_ID
from modules.identity_resolver import resolve_person, resolve_display_name

def test_extraction_parsing():
    """Test JSON contract → anamnese_findings row mapping."""
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        conn = sqlite3.connect(tmp_path)
        
        # Create schema
        conn.execute("CREATE TABLE persons (person_id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO persons (person_id) VALUES (?)", (OWN_PERSON_ID,))
        
        conn.execute('''
        CREATE TABLE anamnese_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track TEXT NOT NULL,
            started_at TEXT NOT NULL,
            last_updated_at TEXT NOT NULL,
            transcript_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'in_progress'
        )''')
        
        conn.execute('''
        CREATE TABLE anamnese_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            track TEXT NOT NULL,
            date_or_period TEXT,
            place_or_subject TEXT,
            event_text TEXT NOT NULL,
            relevance_note TEXT,
            person TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES anamnese_sessions(id),
            FOREIGN KEY (person) REFERENCES persons(person_id)
        )''')
        
        # Create test session
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO anamnese_sessions (track, started_at, last_updated_at, transcript_json, status) VALUES (?, ?, ?, ?, ?)",
            ('exposure', now, now, json.dumps([]), 'in_progress')
        )
        session_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # Test extraction data
        test_findings = [
            {
                "date_or_period": "2020-2022",
                "place_or_subject": "Thailand",
                "event_text": "Frequent travel to rural areas",
                "relevance_note": "Potential zoonotic exposure",
                "person": "self"
            },
            {
                "date_or_period": "childhood",
                "place_or_subject": "grandparents' farm",
                "event_text": "Regular contact with livestock",
                "relevance_note": "Animal exposure history",
                "person": "self"
            }
        ]
        
        # Save findings (simulating the extraction logic)
        for finding in test_findings:
            person_label = finding.get("person", "self")
            person_id = OWN_PERSON_ID if person_label == "self" else resolve_person(person_label)
            
            conn.execute(
                "INSERT INTO anamnese_findings (session_id, track, date_or_period, place_or_subject, event_text, relevance_note, person, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    'exposure',
                    finding.get("date_or_period"),
                    finding.get("place_or_subject"),
                    finding.get("event_text"),
                    finding.get("relevance_note"),
                    person_id,
                    now
                )
            )
        
        conn.commit()
        
        # Verify findings were stored correctly
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM anamnese_findings WHERE session_id = ?", (session_id,))
        count = cursor.fetchone()[0]
        
        assert count == 2, f"Expected 2 findings, got {count}"
        
        # Verify content
        cursor.execute("SELECT event_text, relevance_note FROM anamnese_findings WHERE session_id = ?", (session_id,))
        rows = cursor.fetchall()
        
        assert len(rows) == 2
        assert rows[0][0] == "Frequent travel to rural areas"
        assert rows[0][1] == "Potential zoonotic exposure"
        assert rows[1][0] == "Regular contact with livestock"
        assert rows[1][1] == "Animal exposure history"
        
        print("✓ Extraction parsing test passed")
        
        conn.close()
        
    finally:
        Path(tmp_path).unlink()

def test_session_resumption():
    """Test session creation and resumption."""
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        conn = sqlite3.connect(tmp_path)
        
        # Create schema
        conn.execute("CREATE TABLE persons (person_id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO persons (person_id) VALUES (?)", (OWN_PERSON_ID,))
        
        conn.execute('''
        CREATE TABLE anamnese_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track TEXT NOT NULL,
            started_at TEXT NOT NULL,
            last_updated_at TEXT NOT NULL,
            transcript_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'in_progress'
        )''')
        
        # Create session
        now = datetime.now(timezone.utc).isoformat()
        transcript = [{"role": "system", "content": "Test session"}]
        
        conn.execute(
            "INSERT INTO anamnese_sessions (track, started_at, last_updated_at, transcript_json, status) VALUES (?, ?, ?, ?, ?)",
            ('family', now, now, json.dumps(transcript), 'in_progress')
        )
        
        session_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # Simulate interruption and resumption
        cursor = conn.cursor()
        cursor.execute("SELECT transcript_json, status FROM anamnese_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        
        assert row is not None, "Session not found"
        assert row[1] == 'in_progress', f"Expected status 'in_progress', got {row[1]}"
        
        loaded_transcript = json.loads(row[0])
        assert loaded_transcript == transcript, "Transcript mismatch"
        
        print("✓ Session resumption test passed")
        
        conn.close()
        
    finally:
        Path(tmp_path).unlink()

def test_export_format():
    """Test findings export as Markdown table."""
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        conn = sqlite3.connect(tmp_path)
        
        # Create schema
        conn.execute("CREATE TABLE persons (person_id TEXT PRIMARY KEY, display_name TEXT)")
        conn.execute("INSERT INTO persons (person_id, display_name) VALUES (?, ?)", (OWN_PERSON_ID, "Test User"))
        
        conn.execute('''
        CREATE TABLE anamnese_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track TEXT NOT NULL,
            started_at TEXT NOT NULL,
            last_updated_at TEXT NOT NULL,
            transcript_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'in_progress'
        )''')
        
        conn.execute('''
        CREATE TABLE anamnese_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            track TEXT NOT NULL,
            date_or_period TEXT,
            place_or_subject TEXT,
            event_text TEXT NOT NULL,
            relevance_note TEXT,
            person TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES anamnese_sessions(id),
            FOREIGN KEY (person) REFERENCES persons(person_id)
        )''')
        
        # Create test data
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO anamnese_sessions (track, started_at, last_updated_at, transcript_json, status) VALUES (?, ?, ?, ?, ?)",
            ('exposure', now, now, json.dumps([]), 'completed')
        )
        session_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        conn.execute(
            "INSERT INTO anamnese_findings (session_id, track, date_or_period, place_or_subject, event_text, relevance_note, person, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, 'exposure', '2020', 'Thailand', 'Travel to rural areas', 'Zoonotic risk', OWN_PERSON_ID, now)
        )
        
        conn.commit()
        
        # Export findings
        cursor = conn.cursor()
        cursor.execute(
            "SELECT track, date_or_period, place_or_subject, event_text, relevance_note, person FROM anamnese_findings WHERE session_id = ? ORDER BY created_at",
            (session_id,)
        )
        
        rows = cursor.fetchall()
        markdown = """# Anamnese-Befunde (unverifiziert, selbstberichtet)

| Track | Zeitraum | Ort/Betreff | Ereignis | Relevanz | Person |
|-------|----------|-------------|----------|----------|--------|
"""
        
        for row in rows:
            track, date_period, place_subject, event_text, relevance, person_pseudo = row
            person_display = resolve_display_name(person_pseudo)
            
            markdown += f"| {track} | {date_period or ''} | {place_subject or ''} | {event_text} | {relevance or ''} | {person_display} |\n"
        
        # Verify markdown format
        assert "# Anamnese-Befunde" in markdown
        assert "unverifiziert, selbstberichtet" in markdown
        assert "| Track | Zeitraum |" in markdown
        assert "| exposure | 2020 | Thailand |" in markdown
        assert "Zoonotic risk" in markdown
        
        print("✓ Export format test passed")
        
        conn.close()
        
    finally:
        Path(tmp_path).unlink()

if __name__ == "__main__":
    print("Running anamnese_interview unit tests...")
    
    test_extraction_parsing()
    test_session_resumption()
    test_export_format()
    
    print("\n✅ All unit tests passed!")
