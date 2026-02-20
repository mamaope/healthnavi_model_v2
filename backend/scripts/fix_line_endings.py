#!/usr/bin/env python3
"""
Convert CRLF to LF line endings for shell scripts.
"""
import sys

if len(sys.argv) < 2:
    print("Usage: fix_line_endings.py <file>")
    sys.exit(1)

file_path = sys.argv[1]
try:
    with open(file_path, 'rb') as f:
        data = f.read()
    
    # Convert CRLF and CR to LF
    data = data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    
    with open(file_path, 'wb') as f:
        f.write(data)
    
    print(f"Fixed line endings for {file_path}")
except Exception as e:
    print(f"Error fixing line endings: {e}", file=sys.stderr)
    sys.exit(1)
    