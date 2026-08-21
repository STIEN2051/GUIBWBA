import os
import sys
import unittest
import importlib
import datetime
import tempfile

# Ensure repo root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from wirelessengine import WirelessNetwork
from sparrowbluetooth import BluetoothDevice


class TestGuiScannerLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(sys.argv)

    def setUp(self):
        sparrow_module = importlib.import_module("sparrow-wifi")
        mainWindowClass = getattr(sparrow_module, "mainWindow")
        self.win = mainWindowClass()

    def tearDown(self):
        self.win.close()

    def test_main_window_only_wifi_and_bluetooth_tabs(self):
        # Check Tab Widget
        self.assertIsNotNone(self.win.tabs)
        self.assertEqual(self.win.tabs.count(), 2)
        tab0_text = self.win.tabs.tabText(0)
        tab1_text = self.win.tabs.tabText(1)
        self.assertIn("WiFi", tab0_text)
        self.assertIn("Bluetooth", tab1_text)

        # Check WiFi Table
        self.assertIsNotNone(self.win.networkTable)
        self.assertEqual(self.win.networkTable.columnCount(), 13)
        self.assertEqual(self.win.networkTable.horizontalHeaderItem(0).text(), 'MAC Address')
        self.assertEqual(self.win.networkTable.horizontalHeaderItem(1).text(), 'Vendor')
        self.assertEqual(self.win.networkTable.horizontalHeaderItem(2).text(), 'SSID')

        # Check Bluetooth Table
        self.assertIsNotNone(self.win.bluetoothTable)
        self.assertEqual(self.win.bluetoothTable.columnCount(), 10)
        self.assertEqual(self.win.bluetoothTable.horizontalHeaderItem(0).text(), 'UUID')
        self.assertEqual(self.win.bluetoothTable.horizontalHeaderItem(1).text(), 'Address (MAC)')
        self.assertEqual(self.win.bluetoothTable.horizontalHeaderItem(2).text(), 'Name')

        # Check that removed attributes/widgets are NOT present
        self.assertFalse(hasattr(self.win, 'Plot24'))
        self.assertFalse(hasattr(self.win, 'Plot5'))
        self.assertFalse(hasattr(self.win, 'chart24'))
        self.assertFalse(hasattr(self.win, 'chart5'))
        self.assertFalse(hasattr(self.win, 'btnGPSStatus'))
        self.assertFalse(hasattr(self.win, 'lblGPS'))
        self.assertFalse(hasattr(self.win, 'gpsEngine'))
        self.assertFalse(hasattr(self.win, 'horizontalDivider'))

        # Check Menu structure
        menus = [action.text() for action in self.win.menuBar().actions()]
        self.assertIn('&File', menus)
        self.assertIn('&Help', menus)
        self.assertNotIn('&Spectrum', menus)
        self.assertNotIn('&Geo', menus)
        self.assertNotIn('&Agent', menus)
        self.assertNotIn('&Falcon', menus)
        self.assertNotIn('&Telemetry', menus)

    def test_wifi_data_population_and_clearing(self):
        # Create mock WiFi networks
        net1 = WirelessNetwork()
        net1.macAddr = "00:11:22:33:44:55"
        net1.ssid = "TestWiFi_1"
        net1.security = "WPA2"
        net1.privacy = "AES"
        net1.channel = 6
        net1.frequency = 2437
        net1.signal = -55
        net1.bandwidth = 20
        net1.lastSeen = datetime.datetime.now()
        net1.firstSeen = datetime.datetime.now()

        net2 = WirelessNetwork()
        net2.macAddr = "66:77:88:99:AA:BB"
        net2.ssid = "TestWiFi_2"
        net2.security = "WPA3"
        net2.privacy = "GCMP"
        net2.channel = 36
        net2.frequency = 5180
        net2.signal = -68
        net2.bandwidth = 80
        net2.lastSeen = datetime.datetime.now()
        net2.firstSeen = datetime.datetime.now()

        wifi_dict = {net1.getKey(): net1, net2.getKey(): net2}

        # Populate
        self.win.populateTable(wifi_dict)
        self.assertEqual(self.win.networkTable.rowCount(), 2)

        # Clear
        self.win.onClearWifiData()
        self.assertEqual(self.win.networkTable.rowCount(), 0)

    def test_bluetooth_data_population_and_clearing(self):
        # Create mock Bluetooth devices
        dev1 = BluetoothDevice()
        dev1.uuid = "12345678-1234-5678-1234-567812345678"
        dev1.macAddress = "AA:BB:CC:DD:EE:01"
        dev1.name = "Beacon_Alpha"
        dev1.company = "Apple"
        dev1.btType = BluetoothDevice.BT_LE
        dev1.rssi = -62
        dev1.txPower = -59
        dev1.txPowerValid = True
        dev1.iBeaconRange = 1.45
        dev1.lastSeen = datetime.datetime.now()
        dev1.firstSeen = datetime.datetime.now()

        dev2 = BluetoothDevice()
        dev2.uuid = "87654321-4321-8765-4321-876543210987"
        dev2.macAddress = "AA:BB:CC:DD:EE:02"
        dev2.name = "BT_Headset"
        dev2.company = "Sony"
        dev2.btType = BluetoothDevice.BT_CLASSIC
        dev2.rssi = -75
        dev2.txPowerValid = False
        dev2.lastSeen = datetime.datetime.now()
        dev2.firstSeen = datetime.datetime.now()

        bt_dict = {dev1.getKey(): dev1, dev2.getKey(): dev2}

        # Populate
        self.win.updateBtTable(bt_dict)
        self.assertEqual(self.win.bluetoothTable.rowCount(), 2)

        # Clear
        self.win.onClearBtData()
        self.assertEqual(self.win.bluetoothTable.rowCount(), 0)

    def test_clear_all_data(self):
        net = WirelessNetwork()
        net.macAddr = "00:11:22:33:44:55"
        net.ssid = "TestWiFi"
        self.win.populateTable({net.getKey(): net})

        dev = BluetoothDevice()
        dev.uuid = "1234"
        dev.macAddress = "AA:BB:CC:DD:EE:01"
        self.win.updateBtTable({dev.getKey(): dev})

        self.assertEqual(self.win.networkTable.rowCount(), 1)
        self.assertEqual(self.win.bluetoothTable.rowCount(), 1)

        self.win.onClearAllData()
        self.assertEqual(self.win.networkTable.rowCount(), 0)
        self.assertEqual(self.win.bluetoothTable.rowCount(), 0)


if __name__ == '__main__':
    unittest.main()
