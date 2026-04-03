"""Integrations module for Media Organization System."""

import fcntl
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

from app.core import ValidationResult, ValidatorInterface

load_dotenv()


class FileCompletionValidator(ValidatorInterface):
    """Validate files are complete and no longer being downloaded."""

    def __init__(
        self,
        min_file_age_seconds: Optional[int] = None,
        size_check_duration: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
    ):
        if min_file_age_seconds is None:
            try:
                min_file_age_seconds = int(
                    os.getenv("FILE_COMPLETION_MIN_AGE_SECONDS", "300"))
            except ValueError:
                min_file_age_seconds = 300

        if size_check_duration is None:
            try:
                size_check_duration = int(os.getenv(
                    "FILE_COMPLETION_SIZE_CHECK_DURATION_SECONDS", "5"))
            except ValueError:
                size_check_duration = 5

        self.min_file_age = min_file_age_seconds
        self.size_check_duration = size_check_duration
        self.logger = logger or logging.getLogger(__name__)
        self.temp_extensions = {".part", ".tmp",
                                ".!qB", ".crdownload", ".download", ".aria2"}

    def validar_arquivos(self, arquivos: List[Path]) -> List[Path]:
        if not arquivos:
            return []

        self.logger.info(
            "Validating file completion for %s file(s)",
            len(arquivos),
        )

        prefiltered: List[Path] = []
        initial_sizes: Dict[Path, int] = {}

        for index, arquivo in enumerate(arquivos, start=1):
            if index == 1 or index % 25 == 0 or index == len(arquivos):
                self.logger.info(
                    "Completion validation progress: %s/%s",
                    index,
                    len(arquivos),
                )

            if not arquivo.exists() or self._has_temp_extension(arquivo):
                continue

            if self._is_locked(arquivo):
                continue

            if not self._is_old_enough(arquivo):
                continue

            try:
                initial_sizes[arquivo] = arquivo.stat().st_size
                prefiltered.append(arquivo)
            except OSError:
                continue

        if not prefiltered:
            self.logger.info("Completion validation finished: 0 valid files")
            return []

        if self.size_check_duration > 0:
            self.logger.info(
                "Waiting %ss for batch size stability check (%s file(s))",
                self.size_check_duration,
                len(prefiltered),
            )
            time.sleep(self.size_check_duration)

        valid: List[Path] = []
        for arquivo in prefiltered:
            try:
                current_size = arquivo.stat().st_size
                if current_size == initial_sizes[arquivo]:
                    valid.append(arquivo)
            except OSError:
                continue

        self.logger.info(
            "Completion validation finished: %s/%s valid",
            len(valid),
            len(arquivos),
        )
        return valid

    async def validate(self, file_path: Path) -> ValidationResult:
        if self._is_complete(file_path):
            return ValidationResult(is_valid=True)
        return ValidationResult(is_valid=False, error_message="File is incomplete")

    def can_validate(self, file_path: Path) -> bool:
        return file_path.is_file()

    def _is_complete(self, file_path: Path) -> bool:
        if not file_path.exists():
            return False
        if self._has_temp_extension(file_path):
            return False
        if self._is_locked(file_path):
            return False
        if not self._is_size_stable(file_path):
            return False
        if not self._is_old_enough(file_path):
            return False
        return True

    def _has_temp_extension(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.temp_extensions

    def _is_locked(self, file_path: Path) -> bool:
        try:
            with open(file_path, "r+b") as file_handle:
                fcntl.flock(file_handle.fileno(),
                            fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
                return False
        except (IOError, OSError):
            return True

    def _is_size_stable(self, file_path: Path) -> bool:
        try:
            initial = file_path.stat().st_size
            time.sleep(self.size_check_duration)
            current = file_path.stat().st_size
            return initial == current
        except Exception:
            return False

    def _is_old_enough(self, file_path: Path) -> bool:
        try:
            mtime = file_path.stat().st_mtime
            age = time.time() - mtime
            return age >= self.min_file_age
        except Exception:
            return False

    def esta_conectado(self) -> bool:
        return True

    async def desconectar(self) -> None:
        return None
