#!/usr/bin/env python3
"""
Simple script to update the app version in the VERSION file and pyproject.toml.
Usage: python scripts/update_version.py <new_version>
Example: python scripts/update_version.py 1.2.3
"""

import re
import sys
from pathlib import Path


def update_version(new_version: str) -> None:
    """Update the VERSION file and the [project] version in pyproject.toml."""
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

    # Keep the Poetry package version in sync
    pyproject_path = project_root / "pyproject.toml"
    content = pyproject_path.read_text(encoding="utf-8")
    content, count = re.subn(r'(?m)^version = "[^"]*"$', f'version = "{new_version.strip()}"', content, count=1)
    if count != 1:
        raise ValueError("No version line found in pyproject.toml")
    pyproject_path.write_text(content, encoding="utf-8")

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
