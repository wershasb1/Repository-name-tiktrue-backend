#!/usr/bin/env python3
"""
Working Console Test Application - Guaranteed to show output
"""

import sys
import time
import os

def main():
    print("=" * 60)
    print("🎉 TikTrue LLM Platform - Working Console Test")
    print("=" * 60)
    print()
    
    print("✅ Build automation system is working correctly!")
    print(f"✅ Python version: {sys.version}")
    print(f"✅ Executable path: {sys.executable}")
    print(f"✅ Current directory: {os.getcwd()}")
    print()
    
    # Test imports
    try:
        import json
        print("✅ JSON module loaded successfully")
    except ImportError as e:
        print(f"❌ JSON import failed: {e}")
    
    try:
        import datetime
        print(f"✅ Current time: {datetime.datetime.now()}")
    except ImportError as e:
        print(f"❌ Datetime import failed: {e}")
    
    print()
    print("This executable was created with PyInstaller")
    print("Build automation test: SUCCESS!")
    print()
    
    # Force flush output
    sys.stdout.flush()
    
    # Keep window open for 10 seconds
    print("This window will close in 10 seconds...")
    for i in range(10, 0, -1):
        print(f"Closing in {i} seconds...", end="\r")
        sys.stdout.flush()
        time.sleep(1)
    
    print("\nClosing now!")
    return 0

if __name__ == "__main__":
    try:
        result = main()
        sys.exit(result)
    except Exception as e:
        print(f"Error occurred: {e}")
        input("Press Enter to close...")
        sys.exit(1)