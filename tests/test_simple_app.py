#!/usr/bin/env python3
"""
Simple test application for build automation testing
"""

import sys

def main():
    print("TikTrue LLM Platform - Test Application")
    print("Build automation system is working correctly!")
    print(f"Python version: {sys.version}")
    
    # Simple GUI test
    try:
        from PyQt6.QtWidgets import QApplication, QLabel, QWidget
        app = QApplication(sys.argv)
        
        window = QWidget()
        window.setWindowTitle("TikTrue Test")
        window.setGeometry(100, 100, 300, 200)
        
        label = QLabel("Build automation test successful!", window)
        label.move(50, 80)
        
        print("PyQt6 GUI components loaded successfully")
        # Don't show the window in automated testing
        # window.show()
        
    except ImportError as e:
        print(f"GUI test skipped: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())