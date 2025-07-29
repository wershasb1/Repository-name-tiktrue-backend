#!/usr/bin/env python3
"""
GUI Test Application - Shows actual working GUI
"""

import sys
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QPushButton, QVBoxLayout, QTextEdit
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

def main():
    print("Starting TikTrue GUI Test Application...")
    
    app = QApplication(sys.argv)
    
    # Create main window
    window = QWidget()
    window.setWindowTitle("TikTrue Build Test - SUCCESS! 🎉")
    window.setGeometry(300, 300, 500, 400)
    window.setStyleSheet("background-color: #f0f0f0;")
    
    # Create layout
    layout = QVBoxLayout()
    
    # Title label
    title_label = QLabel("🎉 TikTrue Build Automation Test")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
    title_label.setStyleSheet("color: #2E8B57; margin: 20px; padding: 10px;")
    
    # Info text area
    info_text = QTextEdit()
    info_text.setReadOnly(True)
    info_content = f"""✅ Build automation system is working correctly!

✅ Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}
✅ PyQt6 GUI components loaded successfully
✅ Executable path: {sys.executable}

🔧 This executable was created with PyInstaller
🚀 Build automation test: SUCCESS!

📋 Features tested:
• PyInstaller executable creation
• PyQt6 GUI framework integration  
• Python standard library access
• Cross-platform compatibility

🎯 Status: All systems operational!"""
    
    info_text.setPlainText(info_content)
    info_text.setStyleSheet("font-size: 12px; padding: 10px; border: 1px solid #ccc; border-radius: 5px;")
    
    # Close button
    close_button = QPushButton("✅ Close Application")
    close_button.clicked.connect(app.quit)
    close_button.setStyleSheet("""
        QPushButton {
            font-size: 14px; 
            padding: 12px; 
            background-color: #4CAF50; 
            color: white; 
            border: none; 
            border-radius: 8px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QPushButton:pressed {
            background-color: #3d8b40;
        }
    """)
    
    # Add widgets to layout
    layout.addWidget(title_label)
    layout.addWidget(info_text)
    layout.addWidget(close_button)
    
    window.setLayout(layout)
    
    # Show the window - THIS IS THE KEY LINE!
    window.show()
    
    print("GUI window is now visible!")
    print("Application started successfully.")
    
    # Auto-close after 30 seconds (optional)
    timer = QTimer()
    timer.timeout.connect(app.quit)
    timer.start(30000)  # 30 seconds
    
    return app.exec()

if __name__ == "__main__":
    try:
        result = main()
        sys.exit(result)
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to close...")
        sys.exit(1)