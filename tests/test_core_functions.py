#!/usr/bin/env python3
"""
Test core functions and utilities
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.metadata import detect_media_type
from src.utils import (
    calculate_partial_hash,
    calculate_file_hash,
    normalize_title as sanitize_filename
)
from src.core import (
    FileExistenceValidator,
    FileTypeValidator,
    IncompleteFileValidator,
    JunkFileValidator
)

def test_media_type_detection():
    """Test detect_media_type function"""
    print("🧪 Testing media type detection...")
    
    # Testes com contexto de pasta
    test_cases = [
        # Formato: (caminho, tipo_esperado)
        ("/test/movie.mkv", "movie"),
        ("/test/tv/tv.show.s01e01.mkv", "tv"),  # Agora com contexto de pasta
        ("/test/anime/[Group] Anime - 01.mkv", "anime"),  # Com pasta anime
        ("/test/music/song.mp3", "music"),
        ("/test/books/book.epub", "book"),
        ("/test/audiobooks/audiobook.mp3", "audiobook"),  # Com pasta audiobooks
        ("/test/comics/comic.cbz", "comic"),
        # Testes de anime específicos
        ("/test/anime/Shingeki.no.Kyojin.S01E01.mkv", "anime"),
        ("/test/anime/[SubsPlease] Attack on Titan - 01.mkv", "anime"),
        ("/test/tv/Game.of.Thrones.S01E01.mkv", "tv"),  # TV normal
        ("/test/dorama/Midnight.Diner.E01.mkv", "dorama"),  # Dorama
    ]
    
    for filepath, expected in test_cases:
        test_path = Path(filepath)
        result = detect_media_type(test_path)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {test_path.name}: {result} (expected: {expected})")
        if result != expected:
            print(f"     Path context: {test_path}")
    
    print()

def test_validators():
    """Test validation functions"""
    print("🧪 Testing validators...")
    
    # Video files
    video_files = ["test.mp4", "test.mkv", "test.avi"]
    for ext in video_files:
        path = Path(f"test{ext}")
        result = validate_video_file(path)
        print(f"  Video {ext}: {'✅' if result else '❌'}")
    
    # Audio files
    audio_files = ["test.mp3", "test.flac", "test.m4a"]
    for ext in audio_files:
        path = Path(f"test{ext}")
        result = validate_audio_file(path)
        print(f"  Audio {ext}: {'✅' if result else '❌'}")
    
    # Book files
    book_files = ["test.epub", "test.pdf", "test.mobi"]
    for ext in book_files:
        path = Path(f"test{ext}")
        result = validate_book_file(path)
        print(f"  Book {ext}: {'✅' if result else '❌'}")
    
    # Temporary files
    temp_files = ["test.part", "test.tmp", ".test", "test.!qB"]
    for filename in temp_files:
        path = Path(filename)
        result = is_temporary_file(path)
        print(f"  Temp {filename}: {'✅' if result else '❌'}")
    
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
        partial_hash = calculate_partial_hash(test_file, chunk_size_mb=1)
        print(f"  Partial hash: {partial_hash[:16]}... ({len(partial_hash)} chars)")
        
        # Test full hash
        full_hash = calculate_file_hash(test_file, algorithm='sha256')
        print(f"  Full SHA256 hash: {full_hash[:16]}... ({len(full_hash)} chars)")
        
        # Test MD5
        md5_hash = calculate_file_hash(test_file, algorithm='md5')
        print(f"  MD5 hash: {md5_hash} ({len(md5_hash)} chars)")
        
        print("✅ Hashing tests passed")
        
    finally:
        test_file.unlink()
    
    print()

def run_core_tests():
    """Run all core function tests"""
    print("=" * 60)
    print("🧪 CORE FUNCTIONS TEST SUITE")
    print("=" * 60)
    
    test_media_type_detection()
    test_validators()
    test_hashing()
    
    print("✅ Core functions test suite completed!")

if __name__ == "__main__":
    run_core_tests()