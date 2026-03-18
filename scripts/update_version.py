#!/usr/bin/env python3
"""
Simple script to update the app version in the VERSION file.
Usage: python scripts/update_version.py <new_version>
Example: python scripts/update_version.py 1.2.3
"""

import sys
import os
from pathlib import Path

def update_version(new_version: str) -> None:
    """Update the VERSION file with the new version."""
    # Validate the version format (simple check)
    if not new_version or not isinstance(new_version, str):
        raise ValueError("Invalid version format")
    
    # Get the project root directory (assuming script is in scripts/ folder)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    version_file_path = project_root / "VERSION"
    
    # Write the new version to the file
    with open(version_file_path, "w", encoding="utf-8") as f:
        f.write(new_version.strip())
    
    print(f"Successfully updated version to {new_version}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python update_version.py <new_version>")
        print("Example: python update_version.py 1.2.3")
        sys.exit(1)
    
    new_version = sys.argv[1]
    try:
        update_version(new_version)
    except Exception as e:
        print(f"Error updating version: {e}")
        sys.exit(1)