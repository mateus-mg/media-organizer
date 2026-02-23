#!/usr/bin/env python3
"""
Main test runner - runs all test suites
"""

import sys
import os
import subprocess
import time
from pathlib import Path
import shutil

def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"🚀 {title}")
    print("=" * 70)

def run_test_script(script_name, description):
    """Run a test script"""
    print(f"\n📋 {description}")
    print(f"   Running: {script_name}")
    print("-" * 50)
    
    start_time = time.time()
    
    try:
        # Run the script
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ SUCCESS ({elapsed:.1f}s)")
            # Print first few lines of output
            lines = result.stdout.strip().split('\n')
            for line in lines[:10]:  # Show first 10 lines
                if line.strip():
                    print(f"   {line}")
            if len(lines) > 10:
                print(f"   ... and {len(lines) - 10} more lines")
            return True
        else:
            print(f"❌ FAILED ({elapsed:.1f}s)")
            print(f"   Return code: {result.returncode}")
            if result.stdout:
                print(f"   Output: {result.stdout[:200]}...")
            if result.stderr:
                print(f"   Error: {result.stderr[:200]}...")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ TIMEOUT (300s)")
        return False
    except Exception as e:
        print(f"💥 EXCEPTION: {e}")
        return False

def setup_tests_directory():
    """Create tests directory and copy scripts"""
    tests_dir = Path("tests")
    tests_dir.mkdir(exist_ok=True)
    
    # List of test scripts
    test_scripts = [
        "test_setup.py",
        "test_core_functions.py", 
        "test_mapping_system.py",
        "test_organizers.py",
        "test_cli_commands.py",
        "test_integration.py"
    ]
    
    # Copy this file to tests directory
    current_file = Path(__file__).name
    if current_file != "run_all_tests.py":
        shutil.copy(__file__, tests_dir / "run_all_tests.py")
    
    print("📁 Created tests directory")
    return tests_dir

def run_all_tests():
    """Run all test suites"""
    
    # Ensure we're in the project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Setup tests directory
    tests_dir = setup_tests_directory()
    
    # Create logs and data directories
    Path("logs").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)
    
    # Test results tracking
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0
    }
    
    print_header("COMPREHENSIVE TEST SUITE - MEDIA ORGANIZER")
    
    # Define test phases
    test_phases = [
        ("test_setup.py", "Setting up test environment"),
        ("test_core_functions.py", "Testing core functions"),
        ("test_mapping_system.py", "Testing manual mapping system"),
        ("test_organizers.py", "Testing organizer classes"),
        ("test_cli_commands.py", "Testing CLI commands"),
        ("test_integration.py", "Testing complete integration")
    ]
    
    phase_names = ["Setup", "Core Functions", "Mapping System", "Organizers", "CLI Commands", "Integration"]
    
    for i, (script_name, description) in enumerate(test_phases, 1):
        print(f"\n🔧 PHASE {i}: {phase_names[i-1]}")
        script_path = tests_dir / script_name
        
        if script_path.exists():
            if run_test_script(str(script_path), description):
                results["passed"] += 1
            else:
                results["failed"] += 1
            results["total"] += 1
        else:
            print(f"❌ Test script not found: {script_path}")
            results["failed"] += 1
            results["total"] += 1
    
    # Print summary
    print_header("TEST RESULTS SUMMARY")
    print(f"""
📊 Results:
   Total Tests: {results["total"]}
   ✅ Passed:   {results["passed"]}
   ❌ Failed:   {results["failed"]}
   📈 Success Rate: {(results['passed'] / results['total'] * 100) if results['total'] > 0 else 0:.1f}%
    """)
    
    # Cleanup
    print("\n🧹 Cleaning up test files...")
    cleanup_dirs = [
        "test_environment",
        "test_library",
        "test_data",
        "test_organizer_*",
        "logs/test*",
        "data/test*"
    ]
    
    import glob
    
    for pattern in cleanup_dirs:
        for path in glob.glob(pattern):
            if os.path.exists(path):
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    try:
                        os.remove(path)
                    except:
                        pass
    
    print("✅ Cleanup complete")
    
    # Exit with appropriate code
    if results["failed"] > 0:
        print("\n❌ Some tests failed!")
        return 1
    else:
        print("\n🎉 All tests passed!")
        return 0

if __name__ == "__main__":
    sys.exit(run_all_tests())