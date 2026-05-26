#!/usr/bin/env python3
"""
PyInstaller entry point for sqlfy binary.
Uses absolute imports to avoid relative import issues.
"""

if __name__ == '__main__':
    from sqlfy.main import main
    main()
