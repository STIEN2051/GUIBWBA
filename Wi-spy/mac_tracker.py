#!/usr/bin/env python3
#
# Wi-Spy MAC Address Tracker & Alert System
#
# Monitors WiFi and Bluetooth scan results for known MAC addresses
# and fires alerts when a watched device is detected.
#
# Copyright 2026 — Part of the Wi-Spy project
# Licensed under the GNU General Public License v3
#

import os
import json
import datetime


class MacAlert(object):
    """Represents a single alert fired when a watched MAC is detected."""

    def __init__(self, mac, label, signal, device_type, timestamp=None):
        self.mac = mac.upper()
        self.label = label
        self.signal = signal          # dBm
        self.device_type = device_type  # 'wifi' or 'bluetooth'
        self.timestamp = timestamp or datetime.datetime.now()
        self.acknowledged = False

    def __str__(self):
        return (f"[{self.device_type.upper()}] {self.label} ({self.mac}) "
                f"detected at {self.signal} dBm — {self.timestamp:%H:%M:%S}")

    def to_dict(self):
        return {
            'mac': self.mac,
            'label': self.label,
            'signal': self.signal,
            'device_type': self.device_type,
            'timestamp': str(self.timestamp),
            'acknowledged': self.acknowledged,
        }


class MacTracker(object):
    """
    Manages a watchlist of MAC addresses and checks scan results against it.

    Usage:
        tracker = MacTracker()
        tracker.add_mac('AA:BB:CC:DD:EE:FF', 'My Phone')

        # After a WiFi scan:
        alerts = tracker.check_wifi(wireless_networks_dict)

        # After a BLE scan:
        alerts = tracker.check_bluetooth(bluetooth_devices_list)
    """

    def __init__(self, watchlist_file='mac_watchlist.json'):
        self.watchlist_file = watchlist_file
        # { 'AA:BB:CC:DD:EE:FF': 'My Phone', ... }
        self.watchlist = {}
        # Callback: called with a MacAlert object when a watched device is found
        self.on_alert = None
        # History of alerts (list of MacAlert)
        self.alert_history = []
        # Track which MACs have already been alerted this session to avoid
        # spamming the same alert every scan cycle. Reset when the scan is
        # stopped/started or when the user acknowledges.
        self._alerted_this_session = set()

        self.load()

    # ── Watchlist management ──────────────────────────────────────────

    def add_mac(self, mac, label=''):
        """Add a MAC address to the watchlist."""
        mac = mac.upper().strip()
        if not label:
            label = mac
        self.watchlist[mac] = label
        self.save()

    def remove_mac(self, mac):
        """Remove a MAC address from the watchlist."""
        mac = mac.upper().strip()
        if mac in self.watchlist:
            del self.watchlist[mac]
            self._alerted_this_session.discard(mac)
            self.save()

    def clear_watchlist(self):
        """Remove all entries from the watchlist."""
        self.watchlist.clear()
        self._alerted_this_session.clear()
        self.save()

    def get_watchlist(self):
        """Return a copy of the watchlist dict."""
        return dict(self.watchlist)

    def is_watched(self, mac):
        """Check if a MAC is in the watchlist."""
        return mac.upper().strip() in self.watchlist

    # ── Scan result checking ──────────────────────────────────────────

    def check_wifi(self, networks_dict):
        """
        Check a dict of WirelessNetwork objects against the watchlist.

        Args:
            networks_dict: dict keyed by network key, values are WirelessNetwork objects
                           with .macAddr and .signal attributes.

        Returns:
            list of MacAlert objects for newly detected watched devices.
        """
        alerts = []
        if not self.watchlist or not networks_dict:
            return alerts

        for net_key, network in networks_dict.items():
            mac = network.macAddr.upper()
            if mac in self.watchlist and mac not in self._alerted_this_session:
                alert = MacAlert(
                    mac=mac,
                    label=self.watchlist[mac],
                    signal=network.signal,
                    device_type='wifi',
                )
                alerts.append(alert)
                self.alert_history.append(alert)
                self._alerted_this_session.add(mac)

                if self.on_alert:
                    self.on_alert(alert)

        return alerts

    def check_bluetooth(self, devices_list):
        """
        Check a list of BluetoothDevice objects against the watchlist.

        Args:
            devices_list: list of BluetoothDevice objects with .macAddress
                          and .rssi attributes.

        Returns:
            list of MacAlert objects for newly detected watched devices.
        """
        alerts = []
        if not self.watchlist or not devices_list:
            return alerts

        for device in devices_list:
            mac = device.macAddress.upper()
            if mac in self.watchlist and mac not in self._alerted_this_session:
                bt_type = 'bluetooth-le'
                if hasattr(device, 'btType') and device.btType == 1:
                    bt_type = 'bluetooth-classic'

                alert = MacAlert(
                    mac=mac,
                    label=self.watchlist[mac],
                    signal=device.rssi,
                    device_type=bt_type,
                )
                alerts.append(alert)
                self.alert_history.append(alert)
                self._alerted_this_session.add(mac)

                if self.on_alert:
                    self.on_alert(alert)

        return alerts

    # ── Alert management ──────────────────────────────────────────────

    def reset_alerts(self):
        """Reset the session alert tracking so devices can re-alert."""
        self._alerted_this_session.clear()

    def clear_history(self):
        """Clear all alert history."""
        self.alert_history.clear()
        self._alerted_this_session.clear()

    def get_active_alerts(self):
        """Return unacknowledged alerts."""
        return [a for a in self.alert_history if not a.acknowledged]

    def acknowledge_all(self):
        """Mark all alerts as acknowledged."""
        for alert in self.alert_history:
            alert.acknowledged = True

    # ── Persistence ───────────────────────────────────────────────────

    def save(self):
        """Save the watchlist to a JSON file."""
        try:
            with open(self.watchlist_file, 'w') as f:
                json.dump(self.watchlist, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save watchlist: {e}")

    def load(self):
        """Load the watchlist from a JSON file."""
        if not os.path.isfile(self.watchlist_file):
            return

        try:
            with open(self.watchlist_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # Normalize all keys to uppercase
                    self.watchlist = {k.upper(): v for k, v in data.items()}
        except Exception as e:
            print(f"Warning: Could not load watchlist: {e}")


if __name__ == '__main__':
    # Quick self-test
    tracker = MacTracker(watchlist_file='/tmp/test_watchlist.json')
    tracker.add_mac('AA:BB:CC:DD:EE:FF', 'Test Device')
    tracker.add_mac('11:22:33:44:55:66', 'My Phone')
    print("Watchlist:", tracker.get_watchlist())
    print("Is AA:BB:CC:DD:EE:FF watched?", tracker.is_watched('aa:bb:cc:dd:ee:ff'))
    tracker.remove_mac('11:22:33:44:55:66')
    print("After removal:", tracker.get_watchlist())
    print("Self-test passed.")
