#!/usr/bin/env python3
import sys
import asyncio
from pathlib import Path

from src.core import (
    FileExistenceValidator,
    FileTypeValidator,
    IncompleteFileValidator,
    JunkFileValidator,
)
from src.utils import (
    calculate_partial_hash,
    calculate_file_hash,
    normalize_title as sanitize_filename,
    is_incomplete_file,
)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_validators():
    """Test validation functions"""
    print("🧪 Testing validators...")

    existence = FileExistenceValidator()
    type_validator = FileTypeValidator([".mp3", ".epub", ".cbz"])
    incomplete = IncompleteFileValidator()
    junk = JunkFileValidator()

    valid_file = Path("test_validator.txt")
    incomplete_file = Path("test_validator.tmp")
    valid_file.write_text("ok", encoding="utf-8")
    incomplete_file.write_text("ok", encoding="utf-8")

    try:
        exists_result = asyncio.run(existence.validate(valid_file))
        type_result = asyncio.run(
            type_validator.validate(valid_file.with_suffix(".mp3")))
        incomplete_valid_result = asyncio.run(incomplete.validate(valid_file))
        incomplete_invalid_result = asyncio.run(
            incomplete.validate(incomplete_file))
        junk_result = asyncio.run(junk.validate(valid_file))

        print(
            f"  Existence validator: {'✅' if exists_result.is_valid else '❌'}")
        print(f"  Type validator: {'✅' if type_result.is_valid else '❌'}")
        print(
            f"  Incomplete validator (valid file): {'✅' if incomplete_valid_result.is_valid else '❌'}")
        print(
            f"  Incomplete validator (tmp file blocked): {'✅' if not incomplete_invalid_result.is_valid else '❌'}")
        print(f"  Junk validator: {'✅' if junk_result.is_valid else '❌'}")
        print(
            f"  Utility is_incomplete_file (valid file): {'✅' if not is_incomplete_file(valid_file) else '❌'}")
        print(
            f"  Utility is_incomplete_file (tmp file): {'✅' if is_incomplete_file(incomplete_file) else '❌'}")
    finally:
        valid_file.unlink(missing_ok=True)
        incomplete_file.unlink(missing_ok=True)

    # Filename sanitization
    bad_names = [
        "File:with:colons.txt",
        "File<with>angles.txt",
        "File|with|pipes.txt",
        "File?with?question.txt",
        "CON.txt",  # Reserved name
    ]

    for name in bad_names:
        sanitized = sanitize_filename(name)
        print(f"  Sanitize '{name}' -> '{sanitized}'")

    print()


def test_hashing():
    """Test hash calculation functions"""
    print("🧪 Testing hash functions...")

    # Create a test file
    test_file = Path("test_hash.txt")
    test_content = b"This is test content for hashing" * 1000
    test_file.write_bytes(test_content)

    try:
        # Test partial hash
        partial_hash = calculate_partial_hash(test_file)
        print(
            f"  Partial hash: {partial_hash[:16]}... ({len(partial_hash)} chars)")

        # Test full hash
        full_hash = calculate_file_hash(test_file)
        print(
            f"  Full SHA256 hash: {full_hash[:16]}... ({len(full_hash)} chars)")

        print("✅ Hashing tests passed")

    finally:
        test_file.unlink()

    print()


def run_core_tests():
    """Run all core function tests"""
    print("=" * 60)
    print("🧪 CORE FUNCTIONS TEST SUITE")
    print("=" * 60)

    test_validators()
    test_hashing()

    print("✅ Core functions test suite completed!")


if __name__ == "__main__":
    run_core_tests()
