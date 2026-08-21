# Wi-Spy

A clean, focused WiFi and Bluetooth scanner for Linux with GPS support and MAC address tracking.

Built with Python 3 and PyQt5. Derived from [Sparrow-WiFi](https://github.com/ghostop14/sparrow-wifi) by ghostop14.

---

## Features

### 📡 WiFi Scanner
- 2.4 GHz and 5 GHz SSID discovery
- Signal strength (dBm) with visual quality bars
- Channel, security type, and bandwidth detection
- Sortable, auto-updating results table
- Multiple interface support with auto-detection

### 🔵 Bluetooth Scanner
- Bluetooth Low Energy (BLE) advertisement scanning
- Classic Bluetooth discovery (with Ubertooth/BlueHydra, optional)
- Device name, company, RSSI, and estimated range
- Auto-reconnect on adapter errors

### 📍 GPS Status
- Real-time GPS monitoring via gpsd
- Latitude, longitude, altitude, speed display
- Graceful degradation when GPS is unavailable

### 🔔 MAC Address Tracker
- Add known MAC addresses to a watchlist with friendly labels
- Automatic alert (visual + audio beep) when a watched device appears
- Works across both WiFi and Bluetooth scans
- Persistent watchlist saved to `mac_watchlist.json`

---

## System Requirements

| Requirement | Details |
|---|---|
| **OS** | Ubuntu 20.04+, Kali, Debian 11+, Raspberry Pi OS |
| **Python** | 3.8+ |
| **Root** | Required (for `iw scan` and Bluetooth HCI access) |
| **WiFi adapter** | Any Linux-supported adapter with `iw` |
| **Bluetooth** | Optional — any BLE-capable adapter |
| **GPS** | Optional — gpsd with a USB GPS receiver |

---

## Installation

```bash
# System packages
sudo apt install python3-pip python3-pyqt5 python3-pyqt5.qtchart gpsd gpsd-clients

# Python dependencies
sudo pip3 install --break-system-packages -r requirements.txt
# or with a venv:
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

## Running

```bash
sudo python3 ./wi-spy.py
# or with venv:
sudo venv/bin/python3 ./wi-spy.py
```

> **Note:** Root access is required because `iw dev <iface> scan` and Bluetooth HCI access both need elevated privileges.

---

## Project Structure

```
wi-spy/
├── wi-spy.py              # Main GUI application (PyQt5)
├── mac_tracker.py          # MAC address watchlist & alert system
├── wirelessengine.py       # WiFi scan engine (iw scan + parser)
├── sparrowbluetooth.py     # Bluetooth scan engine (btmon + bluetoothctl)
├── sparrowgps.py           # GPS engine (gpsd integration)
├── sparrowcommon.py        # Shared thread base class & utilities
├── requirements.txt        # Python dependencies
├── wifi_icon.png           # Application icon
└── LICENSE                 # GNU GPL v3
```

---

## MAC Address Tracking

Add devices to watch from the panel at the bottom of the WiFi or Bluetooth tabs.

The watchlist is saved to `mac_watchlist.json` in the application directory. Example:

```json
{
  "AA:BB:CC:DD:EE:FF": "My Phone",
  "11:22:33:44:55:66": "Office Router"
}
```

When a watched device appears in scan results:
- The row is highlighted in the table
- A visual alert appears in the tracker panel
- A system beep sounds
- The device status changes from "⏳ Watching..." to "✅ DETECTED"

---

## License

This project is licensed under the GNU General Public License v3. See the [LICENSE](LICENSE) file for details.

Originally derived from [Sparrow-WiFi](https://github.com/ghostop14/sparrow-wifi) by ghostop14.
