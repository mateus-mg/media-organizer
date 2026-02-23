"""
Utilities module for Media Organization System

Consolidated module containing:
- Logger (Rich-based logging with custom theme)
- ConflictHandler (File conflict resolution)
- ConcurrencyManager (Async concurrency control)
- FileOperations (Safe file operations)
- Helper functions (hash calculation, subtitle moving, naming normalization)

Usage:
    from src.utils import (
        get_logger, MediaOrganizerLogger,
        ConflictHandler, ConflictResolution,
        ConcurrencyManager, FileOperations,
        calculate_partial_hash, normalize_title
    )
"""
import hashlib
import logging
import asyncio
import threading
import re
import fcntl
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any, Callable
from logging.handlers import RotatingFileHandler
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme
from contextlib import asynccontextmanager


# ============================================================================
# SECTION 1: LOGGER
# ============================================================================

CUSTOM_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "dry_run": "bold magenta",
    "conflict": "bold yellow",
})


class MediaOrganizerLogger:
    """
    Custom logger with Rich formatting.
    
    Features:
    - Colorized console output
    - File logging with rotation
    - Dry-run mode support
    - Custom log levels
    """
    
    def __init__(
        self,
        name: str = "media-organizer",
        log_level: str = "INFO",
        log_file: Optional[Path] = None,
        max_size_mb: int = 50,
        backup_count: int = 5,
        dry_run: bool = False
    ):
        self.name = name
        self.dry_run = dry_run
        self.console = Console(theme=CUSTOM_THEME, width=180)
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        self.logger.handlers.clear()
        
        # Console handler with Rich
        console_handler = RichHandler(
            console=self.console,
            show_time=True,
            show_level=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
            log_time_format="[%d/%m/%y %H:%M:%S]"
        )
        console_handler.setLevel(getattr(logging, log_level.upper()))
        self.logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(file_handler)
    
    def debug(self, message: str, **kwargs):
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self.logger.error(message, **kwargs)
    
    def success(self, message: str):
        self.console.print(f"[success]✓[/success] {message}")
        self.logger.info(f"SUCCESS: {message}")
    
    def dry_run_action(self, action: str, details: str = ""):
        prefix = "[dry_run][DRY-RUN][/dry_run]"
        message = f"{prefix} Would {action}"
        if details:
            message += f": {details}"
        self.console.print(message)
        self.logger.info(f"DRY-RUN: Would {action}: {details}")
    
    def conflict_detected(self, path: str, strategy: str, resolution: str):
        self.console.print(f"[conflict]⚠ CONFLICT:[/conflict] File exists: {path}")
        self.console.print(f"[conflict]  Strategy:[/conflict] {strategy} -> {resolution}")
        self.logger.warning(f"CONFLICT: {path} (strategy: {strategy}, result: {resolution})")


def get_logger(
    name: str = "media-organizer",
    config=None,
    dry_run: bool = False
) -> MediaOrganizerLogger:
    """
    Get or create logger instance
    
    Args:
        name: Logger name
        config: Config object (optional)
        dry_run: Dry-run mode
        
    Returns:
        MediaOrganizerLogger instance
    """
    if config:
        return MediaOrganizerLogger(
            name=name,
            log_level=config.log_level,
            log_file=config.log_file,
            max_size_mb=config.log_max_size_mb,
            backup_count=config.log_backup_count,
            dry_run=dry_run
        )
    return MediaOrganizerLogger(name=name, dry_run=dry_run)


# ============================================================================
# SECTION 2: CONFLICT HANDLER
# ============================================================================

class ConflictResolution:
    """Conflict resolution result constants"""
    SKIPPED = "skipped"
    RENAMED = "renamed"
    OVERWRITTEN = "overwritten"
    NO_CONFLICT = "no_conflict"


class ConflictHandler:
    """
    Handle file conflicts during organization.
    
    Strategies:
    - skip: Keep existing file, skip new one
    - rename: Rename new file with counter
    - overwrite: Replace existing file
    """
    
    def __init__(
        self,
        strategy: str = "skip",
        rename_pattern: str = "{name}_{counter}{ext}",
        max_attempts: int = 100
    ):
        if strategy not in ["skip", "rename", "overwrite"]:
            raise ValueError(f"Invalid strategy: {strategy}")
        
        self.strategy = strategy
        self.rename_pattern = rename_pattern
        self.max_attempts = max_attempts
    
    def resolve(
        self,
        source_path: Path,
        dest_path: Path,
        dry_run: bool = False
    ) -> Tuple[Optional[Path], str]:
        """
        Resolve file conflict
        
        Args:
            source_path: Source file path
            dest_path: Destination file path
            dry_run: Dry-run mode
            
        Returns:
            Tuple of (resolved_path, action_taken)
        """
        if not dest_path.exists():
            return dest_path, ConflictResolution.NO_CONFLICT
        
        if self._are_identical(source_path, dest_path):
            return dest_path, ConflictResolution.SKIPPED
        
        if self.strategy == "skip":
            return dest_path, ConflictResolution.SKIPPED
        
        elif self.strategy == "overwrite":
            if not dry_run:
                dest_path.unlink()
            return dest_path, ConflictResolution.OVERWRITTEN
        
        elif self.strategy == "rename":
            new_path = self._generate_unique_name(dest_path)
            if new_path:
                return new_path, ConflictResolution.RENAMED
            return dest_path, ConflictResolution.SKIPPED
        
        return dest_path, ConflictResolution.SKIPPED
    
    def _generate_unique_name(self, base_path: Path) -> Optional[Path]:
        """Generate unique filename"""
        parent = base_path.parent
        stem = base_path.stem
        ext = base_path.suffix
        
        for counter in range(2, self.max_attempts + 2):
            new_name = self.rename_pattern.format(
                name=stem, counter=counter, ext=ext
            )
            new_path = parent / new_name
            
            if not new_path.exists():
                return new_path
        
        return None
    
    def _are_identical(self, file1: Path, file2: Path) -> bool:
        """Check if files are identical"""
        try:
            if file1.stat().st_ino == file2.stat().st_ino:
                return True
        except:
            pass
        
        try:
            if file1.stat().st_size != file2.stat().st_size:
                return False
        except:
            return False
        
        # Hash comparison for small files
        if file1.stat().st_size < 100 * 1024 * 1024:
            return self._compare_hashes(file1, file2)
        
        return False
    
    def _compare_hashes(self, file1: Path, file2: Path, chunk_size: int = 8192) -> bool:
        """Compare file hashes"""
        try:
            hash1 = hashlib.md5()
            hash2 = hashlib.md5()
            
            with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
                while True:
                    chunk1 = f1.read(chunk_size)
                    chunk2 = f2.read(chunk_size)
                    
                    if not chunk1 and not chunk2:
                        break
                    
                    hash1.update(chunk1)
                    hash2.update(chunk2)
            
            return hash1.hexdigest() == hash2.hexdigest()
        except:
            return False


# ============================================================================
# SECTION 3: CONCURRENCY MANAGER
# ============================================================================

class ConcurrencyManager:
    """
    Manage concurrency for file operations.
    
    Provides:
    - Semaphore-based parallel execution
    - File-level locking
    - Resource management
    """
    
    def __init__(self, max_concurrent: int = 3, logger=None):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.file_locks: Dict[str, asyncio.Lock] = {}
        self.locks_lock = threading.Lock()
        self.logger = logger or logging.getLogger(__name__)
    
    async def executar_em_paralelo(
        self,
        tarefas: List[Callable],
        limite_simultaneos: int = None
    ) -> List[Any]:
        """
        Execute tasks in parallel with concurrency control
        
        Args:
            tarefas: List of tasks to execute
            limite_simultaneos: Max concurrent tasks
            
        Returns:
            List of results
        """
        if limite_simultaneos is None:
            limite_simultaneos = self.max_concurrent
        
        semaphore = asyncio.Semaphore(limite_simultaneos)
        
        async def limited_task(task):
            async with semaphore:
                return await task() if asyncio.iscoroutinefunction(task) else task()
        
        tasks = [limited_task(task) for task in tarefas]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Task {i} failed: {result}")
        
        return results
    
    def obter_lock_arquivo(self, caminho: Path):
        """Get file lock"""
        caminho_str = str(caminho.absolute())
        
        with self.locks_lock:
            if caminho_str not in self.file_locks:
                self.file_locks[caminho_str] = asyncio.Lock()
        
        return self.file_locks[caminho_str]
    
    async def executar_operacao_arquivo(self, caminho: Path, operacao: Callable):
        """Execute file operation with lock"""
        lock = self.obter_lock_arquivo(caminho)
        async with lock:
            return await operacao()


class FileOperations:
    """
    Safe file operations with concurrency control.
    
    Provides:
    - Safe hardlink creation
    - Safe file move
    - Safe file copy
    """
    
    def __init__(self, concurrency_manager: ConcurrencyManager, logger=None):
        self.concurrency_manager = concurrency_manager
        self.logger = logger or logging.getLogger(__name__)
    
    async def safe_hardlink(self, source: Path, dest: Path) -> bool:
        """Create hardlink safely"""
        async def create_link():
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                
                if dest.exists():
                    self.logger.warning(f"Destination exists: {dest}")
                    return False
                
                dest.hardlink_to(source)
                self.logger.info(f"Created hardlink: {source.name} -> {dest}")
                return True
            except Exception as e:
                self.logger.error(f"Hardlink failed: {e}")
                return False
        
        return await self.concurrency_manager.executar_operacao_arquivo(dest, create_link)
    
    async def safe_move(self, source: Path, dest: Path) -> bool:
        """Move file safely"""
        async def move_file():
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                
                if dest.exists():
                    return False
                
                source.replace(dest)
                self.logger.info(f"Moved: {source.name} -> {dest}")
                return True
            except Exception as e:
                self.logger.error(f"Move failed: {e}")
                return False
        
        return await self.concurrency_manager.executar_operacao_arquivo(dest, move_file)
    
    async def safe_copy(self, source: Path, dest: Path) -> bool:
        """Copy file safely"""
        async def copy_file():
            try:
                import shutil
                dest.parent.mkdir(parents=True, exist_ok=True)
                
                if dest.exists():
                    return False
                
                shutil.copy2(source, dest)
                self.logger.info(f"Copied: {source.name} -> {dest}")
                return True
            except Exception as e:
                self.logger.error(f"Copy failed: {e}")
                return False
        
        return await self.concurrency_manager.executar_operacao_arquivo(dest, copy_file)


# ============================================================================
# SECTION 4: HELPER FUNCTIONS
# ============================================================================

def calculate_partial_hash(file_path: Path, chunk_size: int = 4096) -> str:
    """
    Calculate partial file hash
    
    Args:
        file_path: Path to file
        chunk_size: Chunk size for reading
        
    Returns:
        MD5 hash string
    """
    hash_md5 = hashlib.md5()
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hash_md5.update(chunk)
    
    return hash_md5.hexdigest()


def calculate_file_hash(file_path: Path) -> str:
    """
    Calculate full file hash
    
    Args:
        file_path: Path to file
        
    Returns:
        MD5 hash string
    """
    hash_md5 = hashlib.md5()
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    
    return hash_md5.hexdigest()


def move_subtitles_with_video(
    video_source: Path,
    video_dest: Path,
    dry_run: bool = False
) -> List[Path]:
    """
    Move subtitle files with video
    
    Args:
        video_source: Source video path
        video_dest: Destination video path
        dry_run: Dry-run mode
        
    Returns:
        List of moved subtitle paths
    """
    moved = []
    subtitle_exts = {'.srt', '.ass', '.vtt'}
    
    source_dir = video_source.parent
    dest_dir = video_dest.parent
    base_name = video_dest.stem
    
    for ext in subtitle_exts:
        for sub_file in source_dir.glob(f"*{ext}"):
            # Match subtitle to video
            if video_source.stem in sub_file.stem or sub_file.stem.startswith(video_source.stem.split('.')[0]):
                # Build new subtitle name
                new_name = f"{base_name}{sub_file.suffix}"
                dest_path = dest_dir / new_name
                
                if not dry_run:
                    sub_file.replace(dest_path)
                moved.append(dest_path)
    
    return moved


def normalize_title(title: str) -> str:
    """
    Normalize title for consistent naming
    
    Args:
        title: Title to normalize
        
    Returns:
        Normalized title
    """
    # Remove special characters
    title = re.sub(r'[^\w\s\-\(\)]', '', title)
    
    # Clean whitespace
    title = re.sub(r'\s+', ' ', title).strip()
    
    return title


def normalize_movie_filename(filename: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Extract title and year from movie filename
    
    Args:
        filename: Movie filename
        
    Returns:
        Tuple of (title, year)
    """
    name = Path(filename).stem
    
    # Pattern: Title (Year)
    match = re.match(r'^(.+?)\s*\((\d{4})\)', name)
    if match:
        title = match.group(1).replace('.', ' ').replace('_', ' ').strip()
        year = int(match.group(2))
        return title, year
    
    # Pattern: Title.Year
    match = re.match(r'^(.+?)\.(\d{4})', name)
    if match:
        title = match.group(1).replace('.', ' ').strip()
        year = int(match.group(2))
        return title, year
    
    # No year found
    title = name.replace('.', ' ').replace('_', ' ').strip()
    return title, None


def normalize_tv_filename(filename: str) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[int]]:
    """
    Extract title, season, episode, year from TV filename
    
    Args:
        filename: TV episode filename
        
    Returns:
        Tuple of (title, season, episode, year)
    """
    name = Path(filename).stem
    
    # Pattern: S01E01
    match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,2})', name)
    if match:
        season = int(match.group(1))
        episode = int(match.group(2))
        
        # Extract title (before season/episode)
        title_match = re.match(r'^(.+?)\.S\d+E\d+', name, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).replace('.', ' ').strip()
        else:
            title = name[:match.start()].replace('.', ' ').strip()
        
        # Extract year if present
        year_match = re.search(r'\((\d{4})\)', name)
        year = int(year_match.group(1)) if year_match else None
        
        return title, season, episode, year
    
    # Pattern: 1x01
    match = re.search(r'(\d{1,2})x(\d{1,2})', name)
    if match:
        season = int(match.group(1))
        episode = int(match.group(2))
        
        title = name[:match.start()].replace('.', ' ').strip()
        
        year_match = re.search(r'\((\d{4})\)', name)
        year = int(year_match.group(1)) if year_match else None
        
        return title, season, episode, year
    
    return None, None, None, None


def normalize_comic_filename(filename: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[int]]:
    """
    Extract series, issue, publisher, year from comic filename
    
    Args:
        filename: Comic filename
        
    Returns:
        Tuple of (series, issue, publisher, year)
    """
    # Pattern: Series #001 (Publisher) (Year)
    match = re.match(r'^(.+?)\s*#(\d+)\s*\(([^)]+)\)\s*\((\d{4})\)', filename)
    if match:
        return match.group(1).strip(), match.group(2), match.group(3).strip(), int(match.group(4))
    
    # Pattern: Series #001
    match = re.match(r'^(.+?)\s*#(\d+)', filename)
    if match:
        return match.group(1).strip(), match.group(2), None, None
    
    return None, None, None, None
