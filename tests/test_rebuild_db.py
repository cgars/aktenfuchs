"""Tests for rebuilding the SQLite index from existing sidecars."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from aktenfux.cli import app
from aktenfux.config import AktenfuxConfig
from aktenfux.db import count_by_status, get_document, rebuild_index
from aktenfux.schema import SidecarDocument
from aktenfux.storage import sha256_file

runner = CliRunner()


def _make_config(base_dir: Path, *, use_sqlite_index: bool = True) -> AktenfuxConfig:
    return AktenfuxConfig(
        {
            "base_dir": str(base_dir),
            "dry_run": False,
            "use_sqlite_index": use_sqlite_index,
        }
    )


def _write_pdf_with_sidecar(directory: Path, pdf_name: str, doc_id: str, *, content: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    pdf = directory / pdf_name
    pdf.write_bytes(content)
    sidecar = SidecarDocument(
        id=doc_id,
        original_path=str(pdf),
        current_path="/old/location.pdf",
        sha256="0" * 64,
        suggested_filename=pdf_name,
        suggested_folder="Other",
        status="review",
    )
    pdf.with_suffix(".json").write_text(sidecar.model_dump_json(indent=2), encoding="utf-8")
    return pdf


class TestRebuildIndex:
    def test_indexes_review_and_archived_sidecars(self, tmp_path):
        cfg = _make_config(tmp_path)
        review_pdf = _write_pdf_with_sidecar(
            cfg.review_path, "review.pdf", "review0000000001", content=b"review-pdf"
        )
        archive_pdf = _write_pdf_with_sidecar(
            cfg.archive_path / "Other", "archived.pdf", "archive000000001", content=b"archive-pdf"
        )

        result = rebuild_index(cfg)

        assert result.indexed == 2
        assert result.skipped_missing_sidecar == 0
        review_row = get_document(cfg.sqlite_path, "review0000000001")
        archive_row = get_document(cfg.sqlite_path, "archive000000001")
        assert review_row is not None
        assert archive_row is not None
        assert review_row["status"] == "review"
        assert review_row["current_path"] == str(review_pdf)
        assert review_row["sha256"] == sha256_file(review_pdf)
        assert archive_row["status"] == "approved"
        assert archive_row["current_path"] == str(archive_pdf)
        assert archive_row["sha256"] == sha256_file(archive_pdf)
        assert count_by_status(cfg.sqlite_path) == {"approved": 1, "review": 1}

    def test_skips_pdf_without_sidecar(self, tmp_path):
        cfg = _make_config(tmp_path)
        cfg.archive_path.mkdir(parents=True)
        (cfg.archive_path / "orphan.pdf").write_bytes(b"orphan")

        result = rebuild_index(cfg)

        assert result.indexed == 0
        assert result.skipped_missing_sidecar == 1

    def test_skips_duplicate_sha_with_different_id(self, tmp_path):
        cfg = _make_config(tmp_path)
        content = b"same document bytes"
        first = _write_pdf_with_sidecar(
            cfg.review_path, "first.pdf", "first00000000001", content=content
        )
        second = _write_pdf_with_sidecar(
            cfg.archive_path / "Other", "second.pdf", "second0000000001", content=content
        )

        result = rebuild_index(cfg)

        assert result.indexed == 1
        assert result.skipped_duplicate_sha256 == 1
        existing_hash = sha256_file(first)
        with sqlite3.connect(cfg.sqlite_path) as conn:
            rows = conn.execute("SELECT id, sha256 FROM documents").fetchall()
        assert rows == [("first00000000001", existing_hash)]
        assert sha256_file(second) == existing_hash

    def test_cli_rebuild_db_creates_index_when_config_flag_is_off(self, tmp_path):
        cfg = _make_config(tmp_path, use_sqlite_index=False)
        _write_pdf_with_sidecar(
            cfg.archive_path / "Other", "archived.pdf", "archive000000001", content=b"archive-pdf"
        )

        with patch("aktenfux.cli._load_config", return_value=cfg):
            result = runner.invoke(app, ["rebuild-db"])

        assert result.exit_code == 0, result.output
        assert "SQLite index rebuilt" in result.output
        assert "indexed: 1" in result.output
        assert "use_sqlite_index is false" in result.output
        row = get_document(cfg.sqlite_path, "archive000000001")
        assert row is not None
        assert row["status"] == "approved"
