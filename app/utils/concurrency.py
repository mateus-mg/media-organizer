"""Async concurrency helpers used by tests and file operations."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Awaitable, Callable, Dict, Iterable, TypeVar


T = TypeVar("T")


class ConcurrencyManager:
    """Simple async concurrency utility for bounded parallel execution."""

    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max(1, int(max_concurrent))
        self._file_locks: Dict[Path, asyncio.Lock] = {}

    async def executar_em_paralelo(
        self,
        tarefas: Iterable[Callable[[], Awaitable[T]]],
        limite_simultaneos: int | None = None,
    ) -> list[T]:
        limite = self.max_concurrent if limite_simultaneos is None else max(
            1, int(limite_simultaneos))
        semaphore = asyncio.Semaphore(limite)

        async def _run(task_factory: Callable[[], Awaitable[T]]) -> T:
            async with semaphore:
                return await task_factory()

        coros = [_run(task_factory) for task_factory in tarefas]
        return list(await asyncio.gather(*coros))

    def obter_lock_arquivo(self, caminho_arquivo: Path) -> asyncio.Lock:
        key = Path(caminho_arquivo)
        lock = self._file_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._file_locks[key] = lock
        return lock

    async def executar_operacao_arquivo(
        self,
        caminho_arquivo: Path,
        operacao: Callable[[], Awaitable[T]],
    ) -> T:
        lock = self.obter_lock_arquivo(caminho_arquivo)
        async with lock:
            return await operacao()


class FileOperations:
    """Thread-backed safe file operations guarded by ConcurrencyManager."""

    def __init__(self, concurrency_manager: ConcurrencyManager):
        self.concurrency_manager = concurrency_manager

    async def safe_copy(self, origem: Path, destino: Path) -> bool:
        async def _copy() -> bool:
            destino.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(shutil.copy2, origem, destino)
            return True

        return await self.concurrency_manager.executar_operacao_arquivo(destino, _copy)

    async def safe_move(self, origem: Path, destino: Path) -> bool:
        async def _move() -> bool:
            destino.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(shutil.move, origem, destino)
            return True

        return await self.concurrency_manager.executar_operacao_arquivo(destino, _move)

    async def safe_hardlink(self, origem: Path, destino: Path) -> bool:
        async def _hardlink() -> bool:
            destino.parent.mkdir(parents=True, exist_ok=True)
            if destino.exists():
                destino.unlink()
            await asyncio.to_thread(destino.hardlink_to, origem)
            return True

        return await self.concurrency_manager.executar_operacao_arquivo(destino, _hardlink)
