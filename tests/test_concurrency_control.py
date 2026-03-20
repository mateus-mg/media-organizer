#!/usr/bin/env python3
"""Unit tests for concurrency utilities."""

import tempfile
import unittest
from pathlib import Path

from src.utils import ConcurrencyManager, FileOperations


class TestConcurrencyManager(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_parallel_execution_respects_task_completion(self):
        manager = ConcurrencyManager(max_concurrent=2)

        async def task_one():
            return "a"

        async def task_two():
            return "b"

        async def task_three():
            return "c"

        results = await manager.executar_em_paralelo(
            [task_one, task_two, task_three], limite_simultaneos=2
        )

        self.assertEqual(len(results), 3)
        self.assertIn("a", results)
        self.assertIn("b", results)
        self.assertIn("c", results)

    async def test_same_path_returns_same_lock(self):
        manager = ConcurrencyManager()
        file_path = self.temp_dir / "sample.txt"
        file_path.write_text("x", encoding="utf-8")

        lock_a = manager.obter_lock_arquivo(file_path)
        lock_b = manager.obter_lock_arquivo(file_path)

        self.assertIs(lock_a, lock_b)

    async def test_execute_operation_with_lock(self):
        manager = ConcurrencyManager()
        file_path = self.temp_dir / "locked.txt"
        file_path.write_text("x", encoding="utf-8")

        async def op():
            return "ok"

        result = await manager.executar_operacao_arquivo(file_path, op)
        self.assertEqual(result, "ok")


class TestFileOperations(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = ConcurrencyManager(max_concurrent=2)
        self.ops = FileOperations(self.manager)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_safe_copy_success(self):
        src = self.temp_dir / "a.txt"
        dst = self.temp_dir / "b.txt"
        src.write_text("copy me", encoding="utf-8")

        success = await self.ops.safe_copy(src, dst)

        self.assertTrue(success)
        self.assertTrue(dst.exists())
        self.assertEqual(dst.read_text(encoding="utf-8"), "copy me")

    async def test_safe_move_success(self):
        src = self.temp_dir / "move_a.txt"
        dst = self.temp_dir / "move_b.txt"
        src.write_text("move me", encoding="utf-8")

        success = await self.ops.safe_move(src, dst)

        self.assertTrue(success)
        self.assertFalse(src.exists())
        self.assertTrue(dst.exists())

    async def test_safe_hardlink_success(self):
        src = self.temp_dir / "hard_src.txt"
        dst = self.temp_dir / "hard_dst.txt"
        src.write_text("hardlink", encoding="utf-8")

        success = await self.ops.safe_hardlink(src, dst)

        self.assertTrue(success)
        self.assertTrue(dst.exists())
        self.assertEqual(dst.read_text(encoding="utf-8"), "hardlink")


if __name__ == "__main__":
    unittest.main()
