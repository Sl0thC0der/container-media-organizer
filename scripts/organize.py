#!/usr/bin/env python3
"""
Backward compatibility wrapper for media_organizer CLI.
Delegates to new package structure while maintaining existing interface.
"""
import sys
from media_organizer.cli import main

if __name__ == "__main__":
    sys.exit(main())
