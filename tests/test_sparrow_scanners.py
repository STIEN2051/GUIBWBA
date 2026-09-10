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

    win.populateTable({net.getKey(): net})
    assert win.networkTable.rowCount() == 1
    assert win.networkTable.item(0, 8).text() == "7"

    # Accumulate beacons update
    net_update = net.copy()
    net_update.beaconCount = 5
    win.populateTable({net_update.getKey(): net_update})
    assert win.networkTable.item(0, 8).text() == "12"

    win.close()
