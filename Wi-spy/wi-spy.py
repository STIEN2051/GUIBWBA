#!/usr/bin/env python3
#
# Wi-Spy — Clean WiFi & Bluetooth Scanner
#
# A focused PyQt5 desktop application for WiFi scanning, Bluetooth Low Energy
# discovery, GPS status monitoring, and MAC address tracking/alerting.
#
# Copyright 2026 — Wi-Spy project (derived from Sparrow-WiFi by ghostop14)
# Licensed under the GNU General Public License v3
#

import sys
import os
import datetime
from time import sleep
from threading import Lock

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QComboBox,
    QLabel, QStatusBar, QGroupBox, QFormLayout, QMessageBox, QInputDialog,
    QLineEdit, QAbstractItemView, QFrame, QSplitter, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QIcon, QColor, QFont

# ── Project imports ──────────────────────────────────────────────────────────
from wirelessengine import WirelessEngine, WirelessNetwork
from sparrowcommon import BaseThreadClass

# GPS — optional (gpsd may not be installed)
try:
    from sparrowgps import GPSEngine, SparrowGPS
    HAS_GPS = True
except Exception:
    HAS_GPS = False

# Bluetooth — optional (btmon/bluetoothctl may not be present)
try:
    from sparrowbluetooth import SparrowBluetooth, BluetoothDevice
    HAS_BT_MODULE = True
except Exception:
    HAS_BT_MODULE = False

# MAC tracker
from mac_tracker import MacTracker, MacAlert

# OUI vendor lookup — optional
try:
    from manuf import manuf as manuf_module
    HAS_OUI = True
except Exception:
    HAS_OUI = False


# ══════════════════════════════════════════════════════════════════════════════
#  BACKGROUND THREADS
# ══════════════════════════════════════════════════════════════════════════════

class WifiScanThread(BaseThreadClass):
    """Background thread that continuously scans for WiFi networks."""

    def __init__(self, interface, main_win):
        super().__init__()
        self.interface = interface
        self.main_win = main_win
        self.scan_delay = 0.5  # seconds between scans

    def run(self):
        self.threadRunning = True
        while not self.signalStop:
            retCode, errString, networks = WirelessEngine.scanForNetworks(self.interface)
            if retCode == 0 and networks and not self.signalStop:
                self.main_win.wifi_results_signal.emit(networks)
            elif retCode != 0 and retCode != WirelessNetwork.ERR_DEVICEBUSY:
                self.main_win.wifi_error_signal.emit(retCode, errString)

            if retCode == WirelessNetwork.ERR_DEVICEBUSY:
                sleep(0.3)
            else:
                sleep(self.scan_delay)
        self.threadRunning = False


class BtDiscoveryPollThread(BaseThreadClass):
    """Background thread that polls Bluetooth discovery results."""

    def __init__(self, bt_engine, main_win):
        super().__init__()
        self.bt_engine = bt_engine
        self.main_win = main_win
        self.poll_interval = 2.0

    def run(self):
        self.threadRunning = True
        while not self.signalStop:
            try:
                errcode, device_list = self.bt_engine.getDiscoveredDevices()
                if errcode == 0 and device_list and not self.signalStop:
                    self.main_win.bt_results_signal.emit(device_list)
            except Exception:
                pass
            sleep(self.poll_interval)
        self.threadRunning = False


# ══════════════════════════════════════════════════════════════════════════════
#  CUSTOM TABLE ITEMS (for numeric sorting)
# ══════════════════════════════════════════════════════════════════════════════

class IntTableItem(QTableWidgetItem):
    """Table item that sorts numerically instead of alphabetically."""

    def __init__(self, text):
        super().__init__(text)
        self.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def __lt__(self, other):
        if isinstance(other, QTableWidgetItem):
            try:
                return int(self.data(Qt.EditRole)) < int(other.data(Qt.EditRole))
            except (ValueError, TypeError):
                pass
        return super().__lt__(other)


# ══════════════════════════════════════════════════════════════════════════════
#  SIGNAL QUALITY HELPER
# ══════════════════════════════════════════════════════════════════════════════

def signal_quality_text(dBm):
    """Convert dBm to a visual quality bar + percentage string."""
    try:
        dbm = int(dBm)
    except (ValueError, TypeError):
        return "?"
    if dbm <= -100:
        pct = 0
    elif dbm >= -50:
        pct = 100
    else:
        pct = 2 * (dbm + 100)

    bars = int(pct / 20)
    return '█' * bars + '░' * (5 - bars) + f' {pct}%'


# ══════════════════════════════════════════════════════════════════════════════
#  MAC TRACKER PANEL (shared widget used in WiFi & BT tabs)
# ══════════════════════════════════════════════════════════════════════════════

class MacTrackerPanel(QGroupBox):
    """Collapsible panel showing the MAC watchlist and alerts."""

    alert_fired = pyqtSignal(str)   # emits alert message string

    def __init__(self, tracker: MacTracker, parent=None):
        super().__init__("🔔 MAC Address Watchlist", parent)
        self.tracker = tracker
        self._build_ui()
        self._refresh_table()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Buttons row ──
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("➕ Add MAC")
        self.btn_remove = QPushButton("➖ Remove Selected")
        self.btn_clear_alerts = QPushButton("🔕 Clear Alerts")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        btn_row.addWidget(self.btn_clear_alerts)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── Watchlist table ──
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["MAC Address", "Label", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setMaximumHeight(150)
        layout.addWidget(self.table)

        # ── Alert log label ──
        self.alert_label = QLabel("")
        self.alert_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        layout.addWidget(self.alert_label)

        # ── Connections ──
        self.btn_add.clicked.connect(self._on_add)
        self.btn_remove.clicked.connect(self._on_remove)
        self.btn_clear_alerts.clicked.connect(self._on_clear_alerts)

    def _on_add(self):
        mac, ok = QInputDialog.getText(
            self, "Add MAC to Watchlist",
            "MAC address (e.g. AA:BB:CC:DD:EE:FF):",
            QLineEdit.Normal, ""
        )
        if ok and mac.strip():
            mac = mac.strip().upper()
            label, ok2 = QInputDialog.getText(
                self, "Label",
                f"Friendly name for {mac}:",
                QLineEdit.Normal, mac
            )
            if not ok2 or not label.strip():
                label = mac
            self.tracker.add_mac(mac, label.strip())
            self._refresh_table()

    def _on_remove(self):
        row = self.table.currentRow()
        if row < 0:
            return
        mac = self.table.item(row, 0).text()
        self.tracker.remove_mac(mac)
        self._refresh_table()

    def _on_clear_alerts(self):
        self.tracker.acknowledge_all()
        self.tracker.reset_alerts()
        self.alert_label.setText("")
        self._refresh_table()

    def _refresh_table(self):
        wl = self.tracker.get_watchlist()
        alerted = self.tracker._alerted_this_session
        self.table.setRowCount(len(wl))
        for i, (mac, label) in enumerate(wl.items()):
            self.table.setItem(i, 0, QTableWidgetItem(mac))
            self.table.setItem(i, 1, QTableWidgetItem(label))
            status_item = QTableWidgetItem("✅ DETECTED" if mac in alerted else "⏳ Watching...")
            if mac in alerted:
                status_item.setForeground(QColor(0, 200, 0))
            self.table.setItem(i, 2, status_item)

    def show_alert(self, alert: MacAlert):
        """Called when a tracked device is found."""
        msg = str(alert)
        self.alert_label.setText(f"⚠️ ALERT: {msg}")
        self.alert_fired.emit(msg)
        self._refresh_table()

        # System beep
        try:
            QApplication.beep()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  WiFi TAB
# ══════════════════════════════════════════════════════════════════════════════

class WifiTab(QWidget):
    """Tab 1: WiFi network scanning."""

    def __init__(self, tracker: MacTracker, parent=None):
        super().__init__(parent)
        self.tracker = tracker
        self.scan_thread = None
        self._networks = {}       # accumulated scan results
        self._updating = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Controls row ──
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Interface:"))
        self.combo_iface = QComboBox()
        self.combo_iface.setMinimumWidth(140)
        ctrl.addWidget(self.combo_iface)

        self.btn_refresh_ifaces = QPushButton("🔄")
        self.btn_refresh_ifaces.setToolTip("Refresh interface list")
        self.btn_refresh_ifaces.setMaximumWidth(36)
        ctrl.addWidget(self.btn_refresh_ifaces)

        self.btn_start = QPushButton("▶ Start Scan")
        self.btn_stop = QPushButton("⏹ Stop Scan")
        self.btn_stop.setEnabled(False)
        self.btn_clear = QPushButton("🗑 Clear")
        ctrl.addWidget(self.btn_start)
        ctrl.addWidget(self.btn_stop)
        ctrl.addWidget(self.btn_clear)
        ctrl.addStretch()
        self.lbl_count = QLabel("Networks: 0")
        ctrl.addWidget(self.lbl_count)
        layout.addLayout(ctrl)

        # ── Network table ──
        cols = ["SSID", "BSSID", "Channel", "Signal (dBm)", "Quality",
                "Security", "Bandwidth", "First Seen", "Last Seen"]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=3)

        # ── MAC tracker panel ──
        self.mac_panel = MacTrackerPanel(self.tracker)
        layout.addWidget(self.mac_panel, stretch=1)

        # ── Connections ──
        self.btn_refresh_ifaces.clicked.connect(self.refresh_interfaces)
        self.btn_start.clicked.connect(self.start_scan)
        self.btn_stop.clicked.connect(self.stop_scan)
        self.btn_clear.clicked.connect(self.clear_results)

        # Populate interfaces
        self.refresh_interfaces()

    def refresh_interfaces(self):
        self.combo_iface.clear()
        try:
            ifaces = WirelessEngine.getInterfaces()
            if ifaces:
                self.combo_iface.addItems(ifaces)
            else:
                self.combo_iface.addItem("(no interfaces found)")
        except Exception:
            self.combo_iface.addItem("(error detecting interfaces)")

    def start_scan(self):
        iface = self.combo_iface.currentText()
        if not iface or iface.startswith("("):
            QMessageBox.warning(self, "No Interface",
                                "No WiFi interface available for scanning.\n"
                                "Make sure you have a WiFi adapter and are running as root.")
            return

        self.tracker.reset_alerts()
        self._networks.clear()
        main_win = self.window()
        self.scan_thread = WifiScanThread(iface, main_win)
        self.scan_thread.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def stop_scan(self):
        if self.scan_thread:
            self.scan_thread.signalStop = True
            self.scan_thread.waitTillFinished(3)
            self.scan_thread = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def clear_results(self):
        self._networks.clear()
        self.table.setRowCount(0)
        self.lbl_count.setText("Networks: 0")

    def update_results(self, networks_dict):
        """Called from the main window signal handler with new scan data."""
        if self._updating:
            return
        self._updating = True

        try:
            # Merge new results into accumulated dict
            for key, net in networks_dict.items():
                if key in self._networks:
                    old = self._networks[key]
                    net.firstSeen = old.firstSeen
                    if net.signal > old.strongestsignal:
                        net.strongestsignal = net.signal
                    else:
                        net.strongestsignal = old.strongestsignal
                self._networks[key] = net

            # Check MAC tracker
            alerts = self.tracker.check_wifi(networks_dict)
            for alert in alerts:
                self.mac_panel.show_alert(alert)

            # Rebuild table
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(self._networks))
            for i, (key, net) in enumerate(self._networks.items()):
                self.table.setItem(i, 0, QTableWidgetItem(net.ssid or "<Hidden>"))
                self.table.setItem(i, 1, QTableWidgetItem(net.macAddr))
                self.table.setItem(i, 2, IntTableItem(str(net.channel)))
                self.table.setItem(i, 3, IntTableItem(str(net.signal)))
                self.table.setItem(i, 4, QTableWidgetItem(signal_quality_text(net.signal)))
                self.table.setItem(i, 5, QTableWidgetItem(net.security))
                self.table.setItem(i, 6, QTableWidgetItem(f"{net.bandwidth} MHz"))
                self.table.setItem(i, 7, QTableWidgetItem(
                    net.firstSeen.strftime('%H:%M:%S') if hasattr(net.firstSeen, 'strftime') else str(net.firstSeen)))
                self.table.setItem(i, 8, QTableWidgetItem(
                    net.lastSeen.strftime('%H:%M:%S') if hasattr(net.lastSeen, 'strftime') else str(net.lastSeen)))

                # Highlight watched MACs
                if self.tracker.is_watched(net.macAddr):
                    for col in range(self.table.columnCount()):
                        item = self.table.item(i, col)
                        if item:
                            item.setBackground(QColor(60, 60, 0))

            self.table.setSortingEnabled(True)
            self.lbl_count.setText(f"Networks: {len(self._networks)}")
        finally:
            self._updating = False

    def cleanup(self):
        self.stop_scan()


# ══════════════════════════════════════════════════════════════════════════════
#  BLUETOOTH TAB
# ══════════════════════════════════════════════════════════════════════════════

class BluetoothTab(QWidget):
    """Tab 2: Bluetooth Low Energy + Classic discovery."""

    def __init__(self, tracker: MacTracker, parent=None):
        super().__init__(parent)
        self.tracker = tracker
        self.bt_engine = None
        self.poll_thread = None
        self._devices = {}
        self._updating = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Controls row ──
        ctrl = QHBoxLayout()
        self.btn_start = QPushButton("▶ Start BLE Discovery")
        self.btn_stop = QPushButton("⏹ Stop Discovery")
        self.btn_stop.setEnabled(False)
        self.btn_clear = QPushButton("🗑 Clear")
        ctrl.addWidget(self.btn_start)
        ctrl.addWidget(self.btn_stop)
        ctrl.addWidget(self.btn_clear)
        ctrl.addStretch()
        self.lbl_count = QLabel("Devices: 0")
        ctrl.addWidget(self.lbl_count)
        layout.addLayout(ctrl)

        # ── Status label ──
        self.lbl_status = QLabel("")
        layout.addWidget(self.lbl_status)

        # ── Device table ──
        cols = ["MAC Address", "Name", "Company", "Type", "RSSI (dBm)",
                "Est. Range (m)", "First Seen", "Last Seen"]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=3)

        # ── MAC tracker panel ──
        self.mac_panel = MacTrackerPanel(self.tracker)
        layout.addWidget(self.mac_panel, stretch=1)

        # ── Connections ──
        self.btn_start.clicked.connect(self.start_discovery)
        self.btn_stop.clicked.connect(self.stop_discovery)
        self.btn_clear.clicked.connect(self.clear_results)

        # Check hardware availability at init
        if not HAS_BT_MODULE:
            self.lbl_status.setText("⚠️ Bluetooth module not available (missing btmon/bluetoothctl)")
            self.btn_start.setEnabled(False)

    def start_discovery(self):
        if not HAS_BT_MODULE:
            QMessageBox.warning(self, "No Bluetooth",
                                "Bluetooth support is not available.\n"
                                "Make sure btmon and bluetoothctl are installed.")
            return

        try:
            self.bt_engine = SparrowBluetooth()
        except Exception as e:
            self.lbl_status.setText(f"⚠️ Error initializing Bluetooth: {e}")
            return

        if not self.bt_engine.hasBluetooth:
            self.lbl_status.setText("⚠️ No Bluetooth adapter detected.")
            QMessageBox.warning(self, "No Bluetooth Hardware",
                                "No Bluetooth adapter was found.\n"
                                "Make sure a BT adapter is connected.")
            return

        self.tracker.reset_alerts()
        self._devices.clear()
        self.lbl_status.setText("🔵 BLE discovery running...")

        # Start discovery using advertisement scan (no Ubertooth/BlueHydra needed)
        self.bt_engine.startDiscovery(useBlueHydra=False)

        # Start polling thread
        main_win = self.window()
        self.poll_thread = BtDiscoveryPollThread(self.bt_engine, main_win)
        self.poll_thread.start()

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def stop_discovery(self):
        if self.poll_thread:
            self.poll_thread.signalStop = True
            self.poll_thread.waitTillFinished(3)
            self.poll_thread = None

        if self.bt_engine:
            try:
                self.bt_engine.stopDiscovery()
            except Exception:
                pass
            self.bt_engine = None

        self.lbl_status.setText("Discovery stopped.")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def clear_results(self):
        self._devices.clear()
        self.table.setRowCount(0)
        self.lbl_count.setText("Devices: 0")

    def update_results(self, device_list):
        """Called from the main window signal handler with new BT scan data."""
        if self._updating:
            return
        self._updating = True

        try:
            # Merge into dict
            for dev in device_list:
                key = dev.macAddress.upper()
                if key in self._devices:
                    old = self._devices[key]
                    dev.firstSeen = old.firstSeen
                    if dev.rssi > old.strongestRssi:
                        dev.strongestRssi = dev.rssi
                    else:
                        dev.strongestRssi = old.strongestRssi
                self._devices[key] = dev

            # Check MAC tracker
            alerts = self.tracker.check_bluetooth(device_list)
            for alert in alerts:
                self.mac_panel.show_alert(alert)

            # Rebuild table
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(self._devices))
            for i, (key, dev) in enumerate(self._devices.items()):
                self.table.setItem(i, 0, QTableWidgetItem(dev.macAddress))
                self.table.setItem(i, 1, QTableWidgetItem(dev.name or ""))
                self.table.setItem(i, 2, QTableWidgetItem(dev.company or ""))
                bt_type_str = "Classic" if dev.btType == 1 else "BLE"
                self.table.setItem(i, 3, QTableWidgetItem(bt_type_str))
                self.table.setItem(i, 4, IntTableItem(str(dev.rssi)))
                range_str = f"{dev.iBeaconRange:.1f}" if dev.iBeaconRange >= 0 else "—"
                self.table.setItem(i, 5, QTableWidgetItem(range_str))
                self.table.setItem(i, 6, QTableWidgetItem(
                    dev.firstSeen.strftime('%H:%M:%S') if hasattr(dev.firstSeen, 'strftime') else str(dev.firstSeen)))
                self.table.setItem(i, 7, QTableWidgetItem(
                    dev.lastSeen.strftime('%H:%M:%S') if hasattr(dev.lastSeen, 'strftime') else str(dev.lastSeen)))

                # Highlight watched MACs
                if self.tracker.is_watched(dev.macAddress):
                    for col in range(self.table.columnCount()):
                        item = self.table.item(i, col)
                        if item:
                            item.setBackground(QColor(60, 60, 0))

            self.table.setSortingEnabled(True)
            self.lbl_count.setText(f"Devices: {len(self._devices)}")
        finally:
            self._updating = False

    def cleanup(self):
        self.stop_discovery()


# ══════════════════════════════════════════════════════════════════════════════
#  GPS TAB
# ══════════════════════════════════════════════════════════════════════════════

class GpsTab(QWidget):
    """Tab 3: GPS status monitoring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.gps_engine = None
        self.timer = None
        self._build_ui()
        self._init_gps()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Title ──
        title = QLabel("📍 GPS Status")
        title.setFont(QFont("", 16, QFont.Bold))
        layout.addWidget(title)

        # ── Status group ──
        group = QGroupBox("Current GPS Data")
        form = QFormLayout(group)

        self.lbl_available = QLabel("Checking...")
        self.lbl_synced = QLabel("—")
        self.lbl_lat = QLabel("—")
        self.lbl_lon = QLabel("—")
        self.lbl_alt = QLabel("—")
        self.lbl_speed = QLabel("—")

        form.addRow("GPS Available:", self.lbl_available)
        form.addRow("Synchronized:", self.lbl_synced)
        form.addRow("Latitude:", self.lbl_lat)
        form.addRow("Longitude:", self.lbl_lon)
        form.addRow("Altitude:", self.lbl_alt)
        form.addRow("Speed:", self.lbl_speed)

        # Style the labels
        for label in [self.lbl_available, self.lbl_synced, self.lbl_lat,
                      self.lbl_lon, self.lbl_alt, self.lbl_speed]:
            label.setFont(QFont("Monospace", 12))
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout.addWidget(group)
        layout.addStretch()

    def _init_gps(self):
        if not HAS_GPS:
            self.lbl_available.setText("❌ GPS module not available (gps3 not installed)")
            self.lbl_available.setStyleSheet("color: #ff6666;")
            return

        try:
            self.gps_engine = GPSEngine()
        except Exception:
            self.lbl_available.setText("❌ GPS initialization failed")
            self.lbl_available.setStyleSheet("color: #ff6666;")
            return

        if self.gps_engine.gpsAvailable:
            self.lbl_available.setText("✅ Yes (gpsd connected)")
            self.lbl_available.setStyleSheet("color: #66ff66;")
            self.gps_engine.start()

            # Start a 1-second timer to poll GPS data
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._update_gps)
            self.timer.start(1000)
        else:
            self.lbl_available.setText("❌ gpsd not running (start with: sudo gpsd -N /dev/ttyUSB0)")
            self.lbl_available.setStyleSheet("color: #ff6666;")

    def _update_gps(self):
        if not self.gps_engine:
            return

        coord = self.gps_engine.getLastCoord()
        if coord and coord.isValid:
            self.lbl_synced.setText("✅ Yes")
            self.lbl_synced.setStyleSheet("color: #66ff66;")
            self.lbl_lat.setText(f"{coord.latitude:.6f}°")
            self.lbl_lon.setText(f"{coord.longitude:.6f}°")
            self.lbl_alt.setText(f"{coord.altitude:.1f} m")
            self.lbl_speed.setText(f"{coord.speed:.1f} m/s")
        else:
            self.lbl_synced.setText("⏳ Waiting for fix...")
            self.lbl_synced.setStyleSheet("color: #ffaa00;")
            self.lbl_lat.setText("—")
            self.lbl_lon.setText("—")
            self.lbl_alt.setText("—")
            self.lbl_speed.setText("—")

    def cleanup(self):
        if self.timer:
            self.timer.stop()
        if self.gps_engine:
            try:
                self.gps_engine.stop()
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class WiSpyMainWindow(QMainWindow):
    """Main application window with 3 tabs: WiFi, Bluetooth, GPS."""

    # Signals for cross-thread communication
    wifi_results_signal = pyqtSignal(dict)
    wifi_error_signal = pyqtSignal(int, str)
    bt_results_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wi-Spy — WiFi & Bluetooth Scanner")
        self.setMinimumSize(900, 600)
        self.resize(1100, 750)

        # Set app icon
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wifi_icon.png')
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # MAC tracker (shared between tabs)
        self.tracker = MacTracker()

        # ── Central widget with tabs ──
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Tab 1: WiFi
        self.wifi_tab = WifiTab(self.tracker)
        self.tabs.addTab(self.wifi_tab, "📡 WiFi Scanner")

        # Tab 2: Bluetooth
        self.bt_tab = BluetoothTab(self.tracker)
        self.tabs.addTab(self.bt_tab, "🔵 Bluetooth Scanner")

        # Tab 3: GPS
        self.gps_tab = GpsTab()
        self.tabs.addTab(self.gps_tab, "📍 GPS Status")

        # ── Status bar ──
        self.statusBar().showMessage("Ready — Select an interface and click Start Scan")

        # ── Connect cross-thread signals ──
        self.wifi_results_signal.connect(self._on_wifi_results)
        self.wifi_error_signal.connect(self._on_wifi_error)
        self.bt_results_signal.connect(self._on_bt_results)

    # ── Signal handlers (thread-safe, run on GUI thread) ──────────────

    def _on_wifi_results(self, networks):
        self.wifi_tab.update_results(networks)
        self.statusBar().showMessage(
            f"WiFi: {len(self.wifi_tab._networks)} networks found  |  "
            f"Last scan: {datetime.datetime.now():%H:%M:%S}"
        )

    def _on_wifi_error(self, code, msg):
        self.statusBar().showMessage(f"WiFi scan error ({code}): {msg}")

    def _on_bt_results(self, device_list):
        self.bt_tab.update_results(device_list)
        self.statusBar().showMessage(
            f"Bluetooth: {len(self.bt_tab._devices)} devices found  |  "
            f"Last poll: {datetime.datetime.now():%H:%M:%S}"
        )

    # ── Cleanup on close ─────────────────────────────────────────────

    def closeEvent(self, event):
        self.wifi_tab.cleanup()
        self.bt_tab.cleanup()
        self.gps_tab.cleanup()
        event.accept()


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Wi-Spy")
    app.setStyle("Fusion")   # Modern cross-platform look

    # Apply a dark-ish stylesheet for a clean modern appearance
    app.setStyleSheet("""
        QMainWindow { background-color: #2b2b2b; }
        QTabWidget::pane { border: 1px solid #555; background: #2b2b2b; }
        QTabBar::tab {
            background: #3c3c3c; color: #ddd; padding: 8px 18px;
            border: 1px solid #555; border-bottom: none;
            margin-right: 2px; font-size: 13px;
        }
        QTabBar::tab:selected { background: #2b2b2b; color: #fff; }
        QTabBar::tab:hover { background: #4a4a4a; }
        QTableWidget {
            background-color: #1e1e1e; color: #ddd; gridline-color: #444;
            alternate-background-color: #262626; selection-background-color: #3a6ea5;
            font-size: 12px;
        }
        QHeaderView::section {
            background-color: #3c3c3c; color: #ddd; padding: 4px;
            border: 1px solid #555; font-weight: bold;
        }
        QPushButton {
            background-color: #3c3c3c; color: #ddd; border: 1px solid #666;
            padding: 6px 14px; border-radius: 3px; font-size: 12px;
        }
        QPushButton:hover { background-color: #505050; }
        QPushButton:pressed { background-color: #2a2a2a; }
        QPushButton:disabled { color: #666; background-color: #333; }
        QComboBox {
            background-color: #3c3c3c; color: #ddd; border: 1px solid #666;
            padding: 4px; border-radius: 3px;
        }
        QLabel { color: #ddd; }
        QGroupBox {
            color: #ddd; border: 1px solid #555; border-radius: 4px;
            margin-top: 8px; padding-top: 16px; font-weight: bold;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
        QStatusBar { background: #3c3c3c; color: #aaa; }
        QLineEdit {
            background-color: #1e1e1e; color: #ddd; border: 1px solid #666;
            padding: 4px; border-radius: 3px;
        }
    """)

    window = WiSpyMainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
