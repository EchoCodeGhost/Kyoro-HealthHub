# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for log_import() with SHA-256 file hashing functionality.

Tests the Chain-of-Custody feature: automatic SHA-256 hash computation
and storage in import_file_hashes table.
"""

import hashlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA
from modules.base import log_import


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def _compute_expected_sha256(content: str) -> str:
    """Compute expected SHA-256 hash for comparison."""
    return hashlib.sha256(content.encode()).hexdigest()


class TestLogImportHashes:
    """Test suite for log_import() hash functionality."""

    def test_single_file_hash(self):
        """Test: log_import with a single file path should create hash entry."""
        conn = _fresh_conn()
        
        # Create a temporary file with known content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("date,value\n2026-01-01,100\n")
            temp_path = f.name
        
        try:
            # Call log_import with the file path
            log_import(conn, 'test_source', temp_path, rows_inserted=1, rows_skipped=0)
            
            # Verify import_log entry exists
            import_log_row = conn.execute(
                "SELECT id FROM import_log WHERE source = 'test_source'"
            ).fetchone()
            assert import_log_row is not None, "import_log entry not found"
            import_log_id = import_log_row['id']
            
            # Verify import_file_hashes entry exists
            hash_row = conn.execute(
                "SELECT * FROM import_file_hashes WHERE import_log_id = ?",
                (import_log_id,)
            ).fetchone()
            assert hash_row is not None, "import_file_hashes entry not found"
            
            # Verify hash is correct
            expected_hash = _compute_expected_sha256("date,value\n2026-01-01,100\n")
            assert hash_row['sha256'] == expected_hash, f"Hash mismatch: {hash_row['sha256']} != {expected_hash}"
            
            # Verify file_path is stored
            assert hash_row['file_path'] == temp_path
            
            # Verify file_size is stored
            assert hash_row['file_size'] == os.path.getsize(temp_path)
            
            # Verify file_mtime is stored (ISO format)
            assert hash_row['file_mtime'] is not None
            
        finally:
            os.unlink(temp_path)

    def test_directory_hash(self):
        """Test: log_import with a directory should hash all top-level files."""
        conn = _fresh_conn()
        
        # Create a temporary directory with multiple files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create 3 test files
            file_paths = []
            for i in range(3):
                file_path = Path(temp_dir) / f"file_{i}.txt"
                content = f"content_{i}"
                with open(file_path, 'w') as f:
                    f.write(content)
                file_paths.append((file_path, content))
            
            # Call log_import with the directory path
            log_import(conn, 'test_dir_source', temp_dir, rows_inserted=3, rows_skipped=0)
            
            # Verify import_log entry exists
            import_log_row = conn.execute(
                "SELECT id FROM import_log WHERE source = 'test_dir_source'"
            ).fetchone()
            assert import_log_row is not None, "import_log entry not found"
            import_log_id = import_log_row['id']
            
            # Verify all 3 files have hash entries
            hash_rows = conn.execute(
                "SELECT * FROM import_file_hashes WHERE import_log_id = ?",
                (import_log_id,)
            ).fetchall()
            assert len(hash_rows) == 3, f"Expected 3 hash entries, got {len(hash_rows)}"
            
            # Create a mapping of file_path to content for verification
            file_content_map = {str(file_path): content for file_path, content in file_paths}
            
            # Verify each hash is correct (order doesn't matter due to iterdir())
            for row in hash_rows:
                file_path = row['file_path']
                assert file_path in file_content_map, f"Unexpected file path: {file_path}"
                content = file_content_map[file_path]
                expected_hash = _compute_expected_sha256(content)
                assert row['sha256'] == expected_hash, f"Hash mismatch for {file_path}"

    def test_empty_string_path(self):
        """Test: log_import with empty string should not create hash entries."""
        conn = _fresh_conn()
        
        # Call log_import with empty data_path (common case: no new files found)
        log_import(conn, 'test_empty', '', rows_inserted=0, rows_skipped=0)
        
        # Verify import_log entry exists
        import_log_row = conn.execute(
            "SELECT id FROM import_log WHERE source = 'test_empty'"
        ).fetchone()
        assert import_log_row is not None, "import_log entry not found"
        
        # Verify NO hash entries were created
        hash_rows = conn.execute(
            "SELECT * FROM import_file_hashes"
        ).fetchall()
        assert len(hash_rows) == 0, f"Expected 0 hash entries, got {len(hash_rows)}"

    def test_nonexistent_path(self):
        """Test: log_import with non-existent path should not create hash entries."""
        conn = _fresh_conn()
        
        # Call log_import with a path that doesn't exist
        log_import(conn, 'test_missing', '/nonexistent/path/file.csv', rows_inserted=0, rows_skipped=0)
        
        # Verify import_log entry exists
        import_log_row = conn.execute(
            "SELECT id FROM import_log WHERE source = 'test_missing'"
        ).fetchone()
        assert import_log_row is not None, "import_log entry not found"
        
        # Verify NO hash entries were created
        hash_rows = conn.execute(
            "SELECT * FROM import_file_hashes"
        ).fetchall()
        assert len(hash_rows) == 0, f"Expected 0 hash entries, got {len(hash_rows)}"

    def test_nested_directory_not_recursive(self):
        """Test: log_import with directory should NOT hash nested files recursively."""
        conn = _fresh_conn()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a file in the top level
            top_file = temp_path / "top.txt"
            with open(top_file, 'w') as f:
                f.write("top content")
            
            # Create a subdirectory with a file
            subdir = temp_path / "subdir"
            subdir.mkdir()
            nested_file = subdir / "nested.txt"
            with open(nested_file, 'w') as f:
                f.write("nested content")
            
            # Call log_import with the directory path
            log_import(conn, 'test_nested', str(temp_path), rows_inserted=1, rows_skipped=0)
            
            # Verify import_log entry exists
            import_log_row = conn.execute(
                "SELECT id FROM import_log WHERE source = 'test_nested'"
            ).fetchone()
            assert import_log_row is not None, "import_log entry not found"
            import_log_id = import_log_row['id']
            
            # Verify ONLY the top-level file has a hash entry (not the nested one)
            hash_rows = conn.execute(
                "SELECT * FROM import_file_hashes WHERE import_log_id = ?",
                (import_log_id,)
            ).fetchall()
            assert len(hash_rows) == 1, f"Expected 1 hash entry (non-recursive), got {len(hash_rows)}"
            assert hash_rows[0]['file_path'] == str(top_file)

    def test_chunked_reading_large_file(self):
        """Test: chunked SHA-256 computation handles larger files correctly."""
        conn = _fresh_conn()
        
        # Create a larger temporary file (> 1MB to test chunking)
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.dat', delete=False) as f:
            # Write 2MB of data
            chunk = b"A" * 65536  # 64KB
            for _ in range(32):  # 32 * 64KB = 2MB
                f.write(chunk)
            temp_path = f.name
        
        try:
            # Compute expected hash
            with open(temp_path, 'rb') as f:
                expected_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Call log_import
            log_import(conn, 'test_large', temp_path, rows_inserted=1, rows_skipped=0)
            
            # Verify hash matches
            import_log_row = conn.execute(
                "SELECT id FROM import_log WHERE source = 'test_large'"
            ).fetchone()
            hash_row = conn.execute(
                "SELECT sha256 FROM import_file_hashes WHERE import_log_id = ?",
                (import_log_row['id'],)
            ).fetchone()
            
            assert hash_row is not None, "Hash entry not found for large file"
            assert hash_row['sha256'] == expected_hash, "Hash mismatch for large file"
            
        finally:
            os.unlink(temp_path)

    def test_binary_file_hash(self):
        """Test: SHA-256 computation works with binary files."""
        conn = _fresh_conn()
        
        # Create a temporary binary file
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.bin', delete=False) as f:
            # Write some binary data
            f.write(b'\x00\x01\x02\x03\xff\xfe\xfd\xfc')
            temp_path = f.name
        
        try:
            # Compute expected hash
            with open(temp_path, 'rb') as f:
                expected_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Call log_import
            log_import(conn, 'test_binary', temp_path, rows_inserted=1, rows_skipped=0)
            
            # Verify hash matches
            import_log_row = conn.execute(
                "SELECT id FROM import_log WHERE source = 'test_binary'"
            ).fetchone()
            hash_row = conn.execute(
                "SELECT sha256 FROM import_file_hashes WHERE import_log_id = ?",
                (import_log_row['id'],)
            ).fetchone()
            
            assert hash_row is not None, "Hash entry not found for binary file"
            assert hash_row['sha256'] == expected_hash, "Hash mismatch for binary file"
            
        finally:
            os.unlink(temp_path)

    def test_multiple_imports_independent(self):
        """Test: multiple log_import calls create independent hash entries."""
        conn = _fresh_conn()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='_1.txt', delete=False) as f1:
            f1.write("content_1")
            temp_path_1 = f1.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='_2.txt', delete=False) as f2:
            f2.write("content_2")
            temp_path_2 = f2.name
        
        try:
            # First import
            log_import(conn, 'source_1', temp_path_1, rows_inserted=1)
            
            # Second import
            log_import(conn, 'source_2', temp_path_2, rows_inserted=1)
            
            # Verify both imports have their own log entries and hash entries
            import_log_rows = conn.execute(
                "SELECT id, source FROM import_log ORDER BY id"
            ).fetchall()
            assert len(import_log_rows) == 2
            
            # Verify hash entries
            hash_rows = conn.execute(
                "SELECT import_log_id, file_path, sha256 FROM import_file_hashes ORDER BY import_log_id"
            ).fetchall()
            assert len(hash_rows) == 2
            
            # Verify first import's hash
            assert hash_rows[0]['file_path'] == temp_path_1
            assert hash_rows[0]['sha256'] == _compute_expected_sha256("content_1")
            
            # Verify second import's hash
            assert hash_rows[1]['file_path'] == temp_path_2
            assert hash_rows[1]['sha256'] == _compute_expected_sha256("content_2")
            
        finally:
            os.unlink(temp_path_1)
            os.unlink(temp_path_2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
