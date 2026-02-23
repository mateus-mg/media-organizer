"""
Test initialization - sets up proper import paths
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Also add src directory
src_path = project_root / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

print(f"✅ Test imports configured")
print(f"   Project root: {project_root}")
print(f"   Sys.path: {sys.path[:3]}...")