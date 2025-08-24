#!/usr/bin/env python3
"""Python wrapper for the apidocs bash script."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Main entry point for the apidocs console script."""
    script_path = Path(__file__).parent / "apidocs"
    
    # Execute the bash script with all arguments
    try:
        result = subprocess.run([str(script_path)] + sys.argv[1:], check=False)
        sys.exit(result.returncode)
    except FileNotFoundError:
        print(f"Error: apidocs script not found at {script_path}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()