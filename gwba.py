#!/usr/bin/env python3
"""
GUI-Based WiFi and Bluetooth Analyser (GWBA)
CLI / Desktop Shortcut Launcher
"""
import sys
import os

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    import wifi_bt_analyser
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    mainWin = wifi_bt_analyser.mainWindow()
    sys.exit(app.exec_())
