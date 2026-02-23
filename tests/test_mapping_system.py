#!/usr/bin/env python3
"""
Test manual mapping system
"""

import sys
import json
from pathlib import Path
import tempfile

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simple_mapping import SimpleMappingDB

def test_mapping_database():
    """Test SimpleMappingDB functionality"""
    print("🧪 Testing mapping database...")
    
    # Create temporary mapping file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        # Initialize database
        db = SimpleMappingDB(tmp_path)
        
        # Test 1: Add movie mapping
        print("  Test 1: Adding movie mapping...")
        try:
            db.add_movie(
                file_path="/test/movie.mkv",
                title_pt="Inception",
                title_en="Inception",
                year=2010,
                tmdb_id=27205  # Real TMDB ID for Inception
            )
            print("    ✅ Movie added successfully")
        except Exception as e:
            print(f"    ❌ Failed to add movie: {e}")
        
        # Test 2: Add movie WITHOUT TMDB ID (should fail)
        print("  Test 2: Adding movie without TMDB ID...")
        try:
            db.add_movie(
                file_path="/test/movie2.mkv",
                title_pt="Test",
                title_en="Test",
                year=2020,
                tmdb_id=None  # This should fail
            )
            print("    ❌ Should have failed but didn't!")
        except ValueError as e:
            print(f"    ✅ Correctly rejected: {e}")
        
        # Test 3: Add series mapping
        print("  Test 3: Adding series mapping...")
        try:
            db.add_series(
                directory="/test/series",
                title_pt="Breaking Bad",
                title_en="Breaking Bad",
                year=2008,
                category="tv",
                tmdb_id=1396  # Real TMDB ID for Breaking Bad
            )
            print("    ✅ Series added successfully")
        except Exception as e:
            print(f"    ❌ Failed to add series: {e}")
        
        # Test 4: Find mappings
        print("  Test 4: Finding mappings...")
        
        movie = db.find_movie_for_file("/test/movie.mkv")
        print(f"    Find movie: {'✅ Found' if movie else '❌ Not found'}")
        
        series = db.find_series_for_file("/test/series/S01E01.mkv")
        print(f"    Find series: {'✅ Found' if series else '❌ Not found'}")
        
        # Test 5: Extract season/episode
        print("  Test 5: Extracting season/episode...")
        
        test_filenames = [
            "Show.S01E01.mkv",
            "show.s01e02.mkv",
            "Show.1x01.mkv",
            "Show - 101.mkv",
            "Show.Episode.01.mkv",
        ]
        
        for filename in test_filenames:
            season, episode = db.extract_season_episode(filename)
            print(f"    {filename}: S{season or '?'}E{episode or '?'}")
        
        # Test 6: Get statistics
        print("  Test 6: Database statistics...")
        stats = db.get_stats()
        print(f"    Movies: {stats['total_movies']}")
        print(f"    Series: {stats['total_series']}")
        print(f"    Categories: {json.dumps(stats['categories'], indent=6)}")
        
        # Save and reload
        db.save()
        
        # Create new instance to test loading
        db2 = SimpleMappingDB(tmp_path)
        movie2 = db2.find_movie_for_file("/test/movie.mkv")
        print(f"    Reload test: {'✅ Success' if movie2 else '❌ Failed'}")
        
        print("✅ Mapping database tests completed!")
        
    finally:
        # Clean up
        Path(tmp_path).unlink(missing_ok=True)

def test_mapping_validation():
    """Test mapping validation rules"""
    print("\n🧪 Testing mapping validation...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        db = SimpleMappingDB(tmp_path)
        
        # Test invalid TMDB IDs
        invalid_ids = [0, -1, "not_a_number", ""]
        
        for invalid_id in invalid_ids:
            print(f"  Testing TMDB ID: {invalid_id}...")
            try:
                db.add_movie(
                    file_path=f"/test/movie_{invalid_id}.mkv",
                    title_pt="Test",
                    title_en="Test",
                    year=2020,
                    tmdb_id=invalid_id if isinstance(invalid_id, int) else None
                )
                print(f"    ❌ Should have rejected ID: {invalid_id}")
            except (ValueError, TypeError) as e:
                print(f"    ✅ Correctly rejected: {e}")
        
        print("✅ Mapping validation tests completed!")
        
    finally:
        Path(tmp_path).unlink(missing_ok=True)

def run_mapping_tests():
    """Run all mapping system tests"""
    print("=" * 60)
    print("🧪 MAPPING SYSTEM TEST SUITE")
    print("=" * 60)
    
    test_mapping_database()
    test_mapping_validation()
    
    print("\n✅ Mapping system test suite completed!")

if __name__ == "__main__":
    run_mapping_tests()