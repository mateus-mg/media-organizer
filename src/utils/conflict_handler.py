"""
Conflict resolution handler for file organization
Handles duplicate files with configurable strategies: skip, rename, overwrite
"""

import hashlib
from pathlib import Path
from typing import Tuple, Optional


class ConflictResolution:
    """Result of conflict resolution"""
    SKIPPED = "skipped"
    RENAMED = "renamed"
    OVERWRITTEN = "overwritten"
    NO_CONFLICT = "no_conflict"


class ConflictHandler:
    """Handle file conflicts during organization"""
    
    def __init__(
        self,
        strategy: str = "skip",
        rename_pattern: str = "{name}_{counter}{ext}",
        max_attempts: int = 100
    ):
        """
        Initialize conflict handler
        
        Args:
            strategy: Resolution strategy ('skip', 'rename', 'overwrite')
            rename_pattern: Pattern for renaming files (supports {name}, {counter}, {ext})
            max_attempts: Maximum rename attempts before giving up
        """
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
    ) -> Tuple[Path, str]:
        """
        Resolve file conflict based on strategy
        
        Args:
            source_path: Source file path
            dest_path: Destination file path (may exist)
            dry_run: Whether in dry-run mode
        
        Returns:
            Tuple of (resolved_path, action_taken)
            - resolved_path: Final destination path to use
            - action_taken: ConflictResolution value
        """
        # No conflict if destination doesn't exist
        if not dest_path.exists():
            return dest_path, ConflictResolution.NO_CONFLICT
        
        # Check if files are identical (same inode or content)
        if self._are_files_identical(source_path, dest_path):
            return dest_path, ConflictResolution.SKIPPED
        
        # Apply strategy
        if self.strategy == "skip":
            return dest_path, ConflictResolution.SKIPPED
        
        elif self.strategy == "overwrite":
            if not dry_run:
                # Delete existing file (will be replaced)
                dest_path.unlink()
            return dest_path, ConflictResolution.OVERWRITTEN
        
        elif self.strategy == "rename":
            new_path = self._generate_unique_filename(dest_path)
            if new_path:
                return new_path, ConflictResolution.RENAMED
            else:
                # Failed to generate unique name, fall back to skip
                return dest_path, ConflictResolution.SKIPPED
        
        return dest_path, ConflictResolution.SKIPPED
    
    def _generate_unique_filename(self, base_path: Path) -> Optional[Path]:
        """
        Generate unique filename using pattern
        
        Args:
            base_path: Base file path
        
        Returns:
            Unique path or None if failed
        """
        parent = base_path.parent
        stem = base_path.stem
        ext = base_path.suffix
        
        for counter in range(2, self.max_attempts + 2):
            # Apply rename pattern
            new_name = self.rename_pattern.format(
                name=stem,
                counter=counter,
                ext=ext
            )
            new_path = parent / new_name
            
            if not new_path.exists():
                return new_path
        
        # Failed to find unique name
        return None
    
    def _are_files_identical(self, file1: Path, file2: Path) -> bool:
        """
        Check if two files are identical
        
        Args:
            file1: First file
            file2: Second file
        
        Returns:
            True if files are identical (same inode or content)
        """
        # Check if same inode (hardlink or same file)
        try:
            if file1.stat().st_ino == file2.stat().st_ino:
                return True
        except (OSError, AttributeError):
            pass
        
        # Check if same size first (quick check)
        try:
            if file1.stat().st_size != file2.stat().st_size:
                return False
        except OSError:
            return False
        
        # Compare file hashes (more reliable but slower)
        # Only do this for small files or if size matches
        file_size = file1.stat().st_size
        if file_size < 100 * 1024 * 1024:  # Only hash files < 100MB
            return self._compare_file_hashes(file1, file2)
        
        # For large files, assume different if not same inode
        return False
    
    def _compare_file_hashes(
        self,
        file1: Path,
        file2: Path,
        chunk_size: int = 8192
    ) -> bool:
        """
        Compare files by MD5 hash
        
        Args:
            file1: First file
            file2: Second file
            chunk_size: Bytes to read at a time
        
        Returns:
            True if hashes match
        """
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
        
        except Exception:
            return False
    
    def get_conflict_info(self, source: Path, dest: Path) -> dict:
        """
        Get detailed information about a conflict
        
        Args:
            source: Source file
            dest: Destination file
        
        Returns:
            Dictionary with conflict details
        """
        info = {
            "source": str(source),
            "dest": str(dest),
            "dest_exists": dest.exists(),
            "strategy": self.strategy,
        }
        
        if dest.exists():
            try:
                source_stat = source.stat()
                dest_stat = dest.stat()
                
                info.update({
                    "source_size": source_stat.st_size,
                    "dest_size": dest_stat.st_size,
                    "same_inode": source_stat.st_ino == dest_stat.st_ino,
                    "size_difference": source_stat.st_size - dest_stat.st_size,
                })
            except Exception as e:
                info["error"] = str(e)
        
        return info
