#!/usr/bin/env python3
"""Unit tests for trash/deletion/validator integrations."""

import asyncio
import tempfile
import unittest
from pathlib import Path

from app.infrastructure.deletion_manager import DeletionManager
from app.infrastructure.trash_manager import TrashManager
from app.validators.integrations import FileCompletionValidator


class _FakeLinkRegistry:
    def __init__(self):
        self.unregistered = []

    def get_all_links(self, path: Path):
        return [{"path": str(path), "type": "original"}]

    def unregister_link(self, path: Path):
        self.unregistered.append(str(path))

    def get_stats(self):
        return {"total_files": 1}


class _FakeTrashManager:
    retention_days = 30

    def __init__(self):
        self.calls = []

    def move_to_trash(self, primary_path, all_links, metadata=None):
        self.calls.append((str(primary_path), len(all_links), metadata or {}))
        return "trash123"

    def get_stats(self):
        return {"active_items": 0}


class TestTrashManager(unittest.TestCase):
    def test_move_to_trash_removes_original_and_indexes_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            trash = TrashManager(base / "trash", retention_days=7)

            source = base / "source.txt"
            source.write_text("payload", encoding="utf-8")

            trash_id = trash.move_to_trash(
                primary_path=source,
                all_links=[{"path": str(source), "type": "original"}],
                metadata={"media_type": "book"},
            )

            self.assertIsNotNone(trash_id)
            self.assertFalse(source.exists())

            item = trash.get_item(trash_id)
            self.assertIsNotNone(item)
            self.assertEqual(item.get("status"), "active")

            trash.close()


class TestDeletionManager(unittest.IsolatedAsyncioTestCase):
    async def test_delete_to_trash_dry_run_reports_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.txt"
            path.write_text("x", encoding="utf-8")

            manager = DeletionManager(
                link_registry=_FakeLinkRegistry(),
                trash_manager=_FakeTrashManager(),
                organization_database=None,
                require_confirmation=False,
                default_dry_run=True,
            )

            result = await manager.delete_to_trash(path, dry_run=True)

            self.assertTrue(result.success)
            self.assertEqual(result.operation_type, "dry_run")
            self.assertEqual(result.removed_links, [str(path)])


class TestFileCompletionValidator(unittest.TestCase):
    def test_validate_rejects_temp_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "movie.part"
            path.write_text("x", encoding="utf-8")

            validator = FileCompletionValidator(min_file_age_seconds=0, size_check_duration=0)
            result = asyncio.run(validator.validate(path))
            self.assertFalse(result.is_valid)

    def test_validar_arquivos_filters_temp_and_accepts_regular_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            valid = base / "book.epub"
            temp = base / "book.part"
            valid.write_text("ok", encoding="utf-8")
            temp.write_text("tmp", encoding="utf-8")

            validator = FileCompletionValidator(min_file_age_seconds=0, size_check_duration=0)
            files = validator.validar_arquivos([valid, temp])

            self.assertIn(valid, files)
            self.assertNotIn(temp, files)


if __name__ == "__main__":
    unittest.main()
