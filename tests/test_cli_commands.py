#!/usr/bin/env python3
"""
Test CLI commands - FIXED map-series
"""

import sys
import subprocess
import json
from pathlib import Path
import tempfile

def run_cli_command(args):
    """Run a CLI command and return output"""
    try:
        # Use list of arguments instead of shell string
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command timeout",
            "returncode": -1
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1
        }

def test_map_movie_command():
    """Test map-movie CLI command"""
    print("🧪 Testing map-movie command...")
    
    # Create temporary file for testing
    with tempfile.NamedTemporaryFile(suffix='.mkv', delete=False) as tmp:
        temp_movie = tmp.name
    
    try:
        # Test with all required parameters
        cmd = [
            sys.executable, "-m", "src.main", "map-movie",
            "--file-path", temp_movie,
            "--title-pt", "Inception",
            "--title-en", "Inception",
            "--year", "2010",
            "--tmdb-id", "27205"
        ]
        
        result = run_cli_command(cmd)
        
        if result["success"]:
            print("  ✅ map-movie command successful")
            
            # Verify mapping was created
            mapping_file = Path("data/manual_mapping.json")
            if mapping_file.exists():
                with open(mapping_file) as f:
                    data = json.load(f)
                
                movie_found = any(
                    m["file_path"] == temp_movie 
                    for m in data.get("movies", [])
                )
                
                if movie_found:
                    print("  ✅ Mapping correctly saved to file")
                else:
                    print("  ❌ Mapping not found in file")
            else:
                print("  ❌ Mapping file not created")
        else:
            print(f"  ❌ map-movie command failed")
            if result["stderr"]:
                print(f"    stderr: {result['stderr'][:200]}")
            
    finally:
        # Cleanup
        Path(temp_movie).unlink(missing_ok=True)

def test_map_series_command():
    """Test map-series CLI command - FIXED"""
    print("\n🧪 Testing map-series command...")
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_series = Path(temp_dir) / "series"
        temp_series.mkdir()
        
        # Create a dummy episode file
        episode_file = temp_series / "S01E01.mkv"
        episode_file.write_text("dummy")
        
        # Test command - SIMPLIFIED VERSION
        cmd = [
            sys.executable, "-m", "src.main", "map-series",
            "--directory", str(temp_series),
            "--title-pt", "Breaking Bad",
            "--title-en", "Breaking Bad",
            "--year", "2008",
            "--category", "tv",
            "--tmdb-id", "1396",
            "--structure-type", "complete_series"  # Added required parameter
        ]
        
        print(f"  Running command with structure-type...")
        
        result = run_cli_command(cmd)
        
        if result["success"]:
            print("  ✅ map-series command successful")
            
            # Verify mapping
            mapping_file = Path("data/manual_mapping.json")
            if mapping_file.exists():
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                series_found = any(
                    s["directory"] == str(temp_series)
                    for s in data.get("tv", [])
                )
                
                if series_found:
                    print("  ✅ Series mapping correctly saved")
                else:
                    print("  ❌ Series mapping not found")
            else:
                print("  ❌ Mapping file not created")
        else:
            print(f"  ❌ map-series command failed with code {result['returncode']}")
            if result["stdout"]:
                print(f"    stdout preview: {result['stdout'][:200]}")
            if result["stderr"]:
                print(f"    stderr preview: {result['stderr'][:200]}")

def test_stats_command():
    """Test stats CLI command"""
    print("\n🧪 Testing stats command...")
    
    # Ensure data directory exists
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Create minimal mapping file if it doesn't exist
    mapping_file = data_dir / "manual_mapping.json"
    if not mapping_file.exists():
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump({"movies": [], "tv": []}, f, indent=2)
    
    cmd = [sys.executable, "-m", "src.main", "stats"]
    result = run_cli_command(cmd)
    
    if result["success"]:
        print("  ✅ stats command successful")
        
        # Check for expected output patterns
        output = result["stdout"]
        if "Statistics" in output or "Mapped" in output or "Organization" in output:
            print("  ✅ Found expected output")
        else:
            print(f"  ⚠️  Unexpected output format")
    else:
        print(f"  ❌ stats command failed: {result['stderr'][:200]}")

def test_check_unmapped_command():
    """Test check-unmapped CLI command"""
    print("\n🧪 Testing check-unmapped command...")
    
    cmd = [sys.executable, "-m", "src.main", "check-unmapped"]
    result = run_cli_command(cmd)
    
    if result["success"]:
        print("  ✅ check-unmapped command successful")
    else:
        print(f"  ❌ check-unmapped command failed: {result['stderr'][:200]}")

def test_test_command():
    """Test test CLI command"""
    print("\n🧪 Testing test command...")
    
    cmd = [sys.executable, "-m", "src.main", "test"]
    result = run_cli_command(cmd)
    
    if result["success"]:
        print("  ✅ test command successful")
        
        output = result["stdout"]
        if "Testing" in output or "System is ready" in output:
            print("  ✅ Found expected output")
    else:
        print(f"  ❌ test command failed: {result['stderr'][:200]}")

def run_cli_tests():
    """Run all CLI command tests"""
    print("=" * 60)
    print("🧪 CLI COMMANDS TEST SUITE")
    print("=" * 60)
    
    # Make sure data directory exists
    Path("data").mkdir(exist_ok=True)
    
    test_map_movie_command()
    test_map_series_command()
    test_stats_command()
    test_check_unmapped_command()
    test_test_command()
    
    print("\n✅ CLI commands test suite completed!")

if __name__ == "__main__":
    run_cli_tests()