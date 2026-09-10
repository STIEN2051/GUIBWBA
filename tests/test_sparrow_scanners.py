import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import datetime
import pytest

from wirelessengine import WirelessEngine, WirelessNetwork, channelToFreq, freqToChannel
from sparrowbluetooth import SparrowBluetooth, BluetoothDevice


def test_channel_frequency_maps():
    assert channelToFreq['1'] == '2412'
    assert channelToFreq['6'] == '2437'
    assert channelToFreq['11'] == '2462'
    assert freqToChannel['2412'] == '1'
    assert freqToChannel['2437'] == '6'
    assert freqToChannel['2462'] == '11'


def test_wireless_network_beacon_tracking():
    net = WirelessNetwork()
    assert net.beaconCount == 0

    net.macAddr = "00:11:22:33:44:55"
    net.ssid = "TestRouter"
    net.channel = 6
    net.frequency = 2437
    net.signal = -50
    net.beaconCount = 15

    # Test serialization
    data = net.toJsondict()
    assert data['beaconCount'] == 15
    assert data['macAddr'] == "00:11:22:33:44:55"

    # Test deserialization
    restored = WirelessNetwork.createFromJsonDict(data)
    assert restored.beaconCount == 15
    assert restored.ssid == "TestRouter"
    assert restored.signal == -50


def test_wireless_engine_interface_detection():
    interfaces = WirelessEngine.getInterfaces()
    assert isinstance(interfaces, list)
    for iface in interfaces:
        mode = WirelessEngine.getInterfaceMode(iface)
        assert mode in ('managed', 'monitor', 'unknown')


def test_bluetooth_initialization():
    bt_interfaces = SparrowBluetooth.getBluetoothInterfaces()
    assert isinstance(bt_interfaces, list)

    dev = BluetoothDevice()
    dev.macAddr = "AA:BB:CC:DD:EE:FF"
    dev.name = "SmartWatch"
    dev.rssi = -65
    assert dev.macAddr == "AA:BB:CC:DD:EE:FF"

    bt = SparrowBluetooth()
    bt.startDiscovery()
    bt.updateDeviceList()
    assert isinstance(bt.devices, dict)
    bt.stopDiscovery()


def test_gui_table_structure_offscreen():
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PyQt5.QtWidgets import QApplication
    import importlib

    app = QApplication.instance() or QApplication(sys.argv)
    sparrow_mod = importlib.import_module('sparrow-wifi')
    win = sparrow_mod.mainWindow()

    # Verify 14 columns
    assert win.networkTable.columnCount() == 14
    headers = [win.networkTable.horizontalHeaderItem(i).text() for i in range(14)]
    assert 'Beacons' in headers
    assert headers[8] == 'Beacons'
    assert headers[0] == 'MAC Address'
    assert headers[2] == 'SSID'

    # Verify table population with Beacons
    net = WirelessNetwork()
    net.macAddr = "DE:AD:BE:EF:00:01"
    net.ssid = "BeaconAP"
    net.channel = 1
    net.frequency = 2412
    net.signal = -70
    net.beaconCount = 7
    net.stationcount = 3

    win.populateTable({net.getKey(): net})
    assert win.networkTable.rowCount() == 1
    assert win.networkTable.item(0, 8).text() == "7"
    assert win.networkTable.item(0, 11).text() == "3"

    # Accumulate beacons update
    net_update = net.copy()
    net_update.beaconCount = 5
    net_update.stationcount = 4
    win.populateTable({net_update.getKey(): net_update})
    assert win.networkTable.item(0, 8).text() == "12"
    assert win.networkTable.item(0, 11).text() == "4"

    win.close()


def test_wireless_client_data_model():
    from wirelessengine import WirelessClient
    client = WirelessClient()
    client.macAddr = "F0:6C:5D:95:4E:08"
    client.bssid = "24:2F:D0:F4:9E:61"
    client.ssid = "IdeaLab-3(2.4)"
    client.signal = -72
    client.packetCount = 42
    client.probedSSIDs = ["HomeNetwork", "CoffeeShop"]

    assert client.getKey() == "F0:6C:5D:95:4E:08"

    # Serialization test
    d = client.toJsondict()
    assert d['macAddr'] == "F0:6C:5D:95:4E:08"
    assert d['bssid'] == "24:2F:D0:F4:9E:61"
    assert d['packetCount'] == 42
    assert "HomeNetwork" in d['probedSSIDs']

    # Deserialization test
    restored = WirelessClient.createFromJsonDict(d)
    assert restored.macAddr == "F0:6C:5D:95:4E:08"
    assert restored.bssid == "24:2F:D0:F4:9E:61"
    assert restored.packetCount == 42
    assert restored.signal == -72
    assert restored.probedSSIDs == ["HomeNetwork", "CoffeeShop"]


def test_gui_client_table_offscreen():
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PyQt5.QtWidgets import QApplication
    import importlib
    from wirelessengine import WirelessClient

    app = QApplication.instance() or QApplication(sys.argv)
    sparrow_mod = importlib.import_module('sparrow-wifi')
    win = sparrow_mod.mainWindow()

    # Verify clientTable exists and has 8 columns
    assert hasattr(win, 'clientTable')
    assert win.clientTable.columnCount() == 8
    expected_headers = [
        'Client MAC Address', 'Vendor', 'Connected AP (BSSID)', 'Network (SSID)',
        'Signal (dBm)', 'Packets', 'Probed SSIDs', 'Last Seen'
    ]
    actual_headers = [win.clientTable.horizontalHeaderItem(i).text() for i in range(8)]
    assert actual_headers == expected_headers

    # Create test clients
    client1 = WirelessClient()
    client1.macAddr = "AA:BB:CC:DD:EE:01"
    client1.bssid = "11:22:33:44:55:66"
    client1.ssid = "AP-One"
    client1.signal = -60
    client1.packetCount = 10
    client1.probedSSIDs = ["GuestWiFi"]

    client2 = WirelessClient()
    client2.macAddr = "AA:BB:CC:DD:EE:02"
    client2.bssid = "77:88:99:AA:BB:CC"
    client2.ssid = "AP-Two"
    client2.signal = -80
    client2.packetCount = 5

    # Populate client table
    win.populateClientTable({client1.getKey(): client1, client2.getKey(): client2})
    assert win.clientTable.rowCount() == 2

    # Filter client table to AP-One only
    win.filterClientTableRows("11:22:33:44:55:66")
    for r in range(win.clientTable.rowCount()):
        apMac = win.clientTable.item(r, 2).text().strip().upper()
        if apMac == "11:22:33:44:55:66":
            assert not win.clientTable.isRowHidden(r)
        else:
            assert win.clientTable.isRowHidden(r)

    # Show all
    win.onShowAllClientsClicked()
    visible_count = 0
    for r in range(win.clientTable.rowCount()):
        if not win.clientTable.isRowHidden(r):
            visible_count += 1
    assert visible_count == 2

    # Test Clear Clients
    win.onClearClientsClicked()
    assert win.clientTable.rowCount() == 0

    win.close()

