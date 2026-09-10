# GUI-Based WiFi and Bluetooth Analyser (GWBA)

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform Linux](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](https://kernel.org)
[![License MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A powerful, high-performance real-time wireless reconnaissance, spectrum analysis, and telemetry desktop application engineered in Python and PyQt5.

**GWBA** enables simultaneous multi-protocol monitoring of **Wi-Fi** (802.11 a/b/g/n/ac/ax) and **Bluetooth** (Classic BR/EDR and Bluetooth Low Energy / BLE). It is designed to capture live 802.11 beacon frames, monitor client probe requests, track access point utilization, estimate device proximity, and export structured audit logs to CSV and JSON.

---

## Key Highlights

- **Simultaneous Multi-Protocol Capture**: Concurrently monitors Wi-Fi radio frequencies and Bluetooth signals within a unified graphical interface.
- **Live 802.11 Beacon Tracking**: Dynamically captures and tallies beacon frames, calculating signal strength (RSSI), channel load, bandwidth, and encryption parameters in real time.
- **Client Association & Probing Engine**: Unmasks active client stations, maps them to their connected Access Points (BSSIDs), discovers unassociated probing devices, and records all probed SSIDs.
- **Interactive Per-AP Filtering & Search**: Click any Access Point in the upper table to immediately filter the connected clients table to show only stations associated with that network. Search instantly by MAC, vendor, or SSID.
- **Zero Additional Hardware Required**: Runs on standard laptops or desktop PCs with built-in Wi-Fi hardware that supports Linux monitor mode — **no need to purchase expensive external Wi-Fi dongles or specialized adapters online**.
- **Validated on Intel Wi-Fi 6 AX201**: Optimized for and tested on internal Intel AX201 adapters using Linux Virtual Interface (VIF) monitor mode architecture.
- **Comprehensive Logging & Export**: Save, export, and reload complete scan snapshots in standard CSV and JSON formats for offline security audits and reporting.

---

## Hardware Compatibility & Architecture

### Built for Standard Laptop Wi-Fi (No Dongles Needed)
Many wireless audit tools force users to purchase external USB adapters (such as Alfa AWUS036ACM / TP-Link TP-WN722N v1) because internal cards often struggle with conventional monitor-mode switches.

**GWBA solves this.** By utilizing the modern Linux `mac80211` / `iw` virtual interface architecture, GWBA can instantiate a high-performance monitor Virtual Interface (`wlan0mon`) directly alongside the physical PHY of standard internal laptop wireless chipsets.

### Verified Hardware
- **Primary Tested Adapter**: **Intel Wi-Fi 6 AX201 160MHz** (`iwlwifi` driver).
- **Compatible Chipsets**: Any Linux-compatible wireless card supporting monitor mode (`iw phy<id> info` indicating `* monitor` support), including:
  - Intel Wireless family (AX200, AX201, AX210, AC9260, AC8265, AC7265)
  - Realtek chipsets (RTL8812AU, RTL8814AU, RTL8188EUS)
  - Qualcomm Atheros (ath9k, ath10k)
  - MediaTek (mt7601u, mt7612u, mt7921)
- **Bluetooth Hardware**: Standard internal Bluetooth 4.0/5.0/5.2 controller (via BlueZ / `hci0`), external Bluetooth dongles, or Ubertooth One spectrum analyzers.

---

## User View & Log Storage Columns

GWBA organizes wireless intelligence into dedicated, sortable views and allows exporting full session logs. Below is the complete catalog of all columns captured, calculated, and displayed in the user interface:

### 1. Access Points Table (Wi-Fi Networks) — 14 Columns

| Column | Description | Data Example |
| :--- | :--- | :--- |
| **MAC Address** | Hardware BSSID of the Access Point | `DE:AD:BE:EF:00:01` |
| **Vendor** | Hardware manufacturer resolved via IEEE OUI lookup | `Intel Corporate` / `Cisco Systems` |
| **SSID** | Service Set Identifier (network broadcast name) | `Corporate-Secure-5G` |
| **Security** | Authentication protocol | `Open`, `WEP`, `WPA`, `WPA2`, `WPA3` |
| **Privacy** | Cipher encryption suite | `CCMP`, `TKIP`, `GCMP` |
| **Channel** | Primary operating channel | `1`, `6`, `11`, `36`, `44`, `149` |
| **Frequency (MHz)** | Operating RF center frequency | `2412`, `2437`, `2462`, `5180` |
| **Signal (dBm)** | Received Signal Strength Indicator (RSSI) | `-52` |
| **Beacons** | Cumulative count of captured 802.11 beacon frames | `1,248` |
| **Bandwidth (MHz)** | Channel bandwidth allocation | `20`, `40`, `80`, `160` |
| **% Utilization** | QBSS channel utilization / airtime load | `14%` |
| **Stations** | Number of associated client devices detected | `8` |
| **Last Seen** | Timestamp of most recent frame received | `09/10/2026 20:15:30` |
| **First Seen** | Timestamp when the AP was first detected | `09/10/2026 19:42:10` |

### 2. Connected Clients & Probing Devices Table — 8 Columns

| Column | Description | Data Example |
| :--- | :--- | :--- |
| **Client MAC Address** | Unique hardware MAC address of the client device | `F0:6C:5D:95:4E:08` |
| **Vendor** | Client device manufacturer resolved via OUI | `Apple, Inc.` / `Samsung Electronics` |
| **Connected AP (BSSID)** | MAC address of the AP to which the client is associated | `DE:AD:BE:EF:00:01` |
| **Network (SSID)** | Network name associated with the connection | `Corporate-Secure-5G` |
| **Signal (dBm)** | Signal strength of the client transmission | `-68` |
| **Packets** | Total packets and data frames captured from this station | `482` |
| **Probed SSIDs** | Historical list of SSIDs probed by the device | `HomeWiFi, Airport-Free, CoffeeShop` |
| **Last Seen** | Timestamp of the most recent packet captured | `09/10/2026 20:15:28` |

### 3. Bluetooth Devices Table — 10 Columns

| Column | Description | Data Example |
| :--- | :--- | :--- |
| **UUID** | Universally Unique Identifier for advertised service | `0000180f-0000-1000-8000-00805f9b34fb` |
| **Address (MAC)** | Bluetooth device hardware MAC address | `AA:BB:CC:11:22:33` |
| **Name** | Advertised friendly Bluetooth name | `Bose QC45` / `Galaxy Watch6` |
| **Company** | Registered company name from Bluetooth SIG | `Apple Inc.` / `Bose Corporation` |
| **Manufacturer** | Specific hardware manufacturer information | `Texas Instruments` |
| **Type** | Protocol standard | `BTLE` (Low Energy) or `Classic` (BR/EDR) |
| **RSSI (dBm)** | Advertised packet signal strength | `-64` |
| **TX Power** | Calibrated transmit power level in dBm | `-12` |
| **Est Range (m)** | Estimated distance calculated via path loss model | `3.2` |
| **Last Seen** | Timestamp of the most recently received packet | `09/10/2026 20:15:25` |

---

## Installation & Prerequisites

### 1. System Requirements
- **Operating System**: Linux (Ubuntu 20.04/22.04/24.04, Debian 11/12, Kali Linux, Fedora 38+, Arch Linux).
- **Python**: Python 3.8 or newer (tested on Python 3.12 and 3.13).

### 2. Install System Dependencies
Open a terminal and install the required networking, packet capture, and Bluetooth utilities:

```bash
sudo apt update
sudo apt install -y iw wireless-tools tcpdump dumpcap bluez libcap2-bin python3-pyqt5
```

### 3. Install Python Dependencies
Install the required Python packages:

```bash
pip install -r requirements.txt
```

*(Optional: You can also use a Python virtual environment with `--system-site-packages` to leverage the system PyQt5 build).*

---

## Quick Start Guide

### Step 1: Automated Hardware Configuration
The included `setup.sh` script automatically:
1. Starts and enables the system Bluetooth service (`bluez`).
2. Configures non-root packet capture capabilities (`cap_net_raw,cap_net_admin`) on `tcpdump`, `dumpcap`, and `iw`.
3. Creates the high-performance `wlan0mon` monitor interface on your internal Wi-Fi adapter (e.g. Intel AX201) without disconnecting active internet routes if you have a secondary interface.

Run the setup script with `sudo`:
```bash
sudo ./setup.sh
```

*(Expected output: `[+] wlan0mon is active in MONITOR mode (capturing 10+ beacons/sec)!`)*

### Step 2: Diagnostic Check (Optional)
To verify that your wireless adapter and driver actually capture live 802.11 frames in monitor mode, run the built-in diagnostic tool:

```bash
# List available interfaces and capabilities:
python3 test_monitor_mode.py --list

# Or run a full live 5-second capture verification:
sudo ./test_monitor_mode.py
```

### Step 3: Launch the Application
Launch the GUI using either the primary command or the short alias:

```bash
python3 wifi_bt_analyser.py
# Or:
python3 gwba.py
```

### Step 4: Scanning & Analysis Workflow
1. **Select Interface**: In the top-left dropdown, select `wlan0mon` (or your desired wireless interface). The badge will display `MONITOR` in green.
2. **Choose Scan Mode**:
   - **Normal Mode**: Sweeps all 2.4 GHz and 5 GHz channels sequentially.
   - **Hunt Mode**: Focuses continuous dwell time on specific channels (e.g., `1`, `6`, `11`, or `36,40,44`) for high-speed beacon and probe capture.
3. **Start Scan**: Click **Scan** (or press `Ctrl+S`). Live Access Points will populate the upper table, and beacon counters will continuously increment.
4. **Inspect Clients**:
   - Click on any Access Point in the top table to instantly filter the bottom table to show only clients associated with that network.
   - Click **Show All Devices** to view all clients across all networks.
   - Use the **Filter / Search** box (`🔍 Search MAC / Vendor / SSID...`) to instantly find specific devices in real time.
5. **Bluetooth Monitoring**: Click the **Bluetooth** tab and toggle **Scan** to discover nearby Classic & BLE devices simultaneously.
6. **Export Logs**: Click **Export CSV** (or navigate to `File` ➔ `Export Scan` ➔ `WiFi to CSV` / `WiFi to JSON` / `Bluetooth to CSV`) to save logs with complete timestamps and column metrics.

### Step 5: Restoring Managed Wi-Fi Mode
When finished with testing, restore your wireless adapter to standard Wi-Fi station mode for regular internet browsing:

```bash
sudo ./setup.sh --managed
```

---

## Log Storage & Export Format Details

### Exporting Wi-Fi Access Points to CSV
The generated CSV file contains the following schema:
```csv
macAddr,vendor,SSID,Security,Privacy,Channel,Frequency,Signal Strength,Beacons,Bandwidth,% Utilization,# of Stations,Last Seen,First Seen
"DE:AD:BE:EF:00:01","Intel Corporate","OfficeNet","WPA2","CCMP",6,2437,-52,1248,20,14,3,"09/10/2026 20:15:30","09/10/2026 19:42:10"
```

### Exporting Bluetooth Devices to CSV
```csv
UUID,Address,Name,Company,Manufacturer,Type,RSSI,TX Power,Est Range (m),Last Seen
"0000180f-0000-1000-8000-00805f9b34fb","AA:BB:CC:11:22:33","SmartBand","Apple Inc.","Texas Instruments","BTLE",-64,-12,3.2,"09/10/2026 20:15:25"
```

### Exporting Wi-Fi to JSON
The JSON export produces structured, hierarchically formatted records containing AP telemetry, channel parameters, and GPS coordinates (if GPS daemon is active):
```json
{
  "wifi-aps": [
    {
      "type": "wifi-ap",
      "macAddr": "DE:AD:BE:EF:00:01",
      "ssid": "OfficeNet",
      "security": "WPA2",
      "privacy": "CCMP",
      "channel": 6,
      "frequency": 2437,
      "signal": -52,
      "beaconCount": 1248,
      "bandwidth": 20,
      "utilization": 14,
      "stationcount": 3,
      "firstseen": "2026-09-10 19:42:10",
      "lastseen": "2026-09-10 20:15:30"
    }
  ]
}
```

---

## Running Automated Tests

GWBA includes an automated test suite verifying serialization, frequency mappings, off-screen GUI table structures, beacon tracking, and client filtering:

```bash
pytest tests/
```

*(All 7 tests run headless in off-screen mode and complete in under 1 second).*

---

## Project Structure

```
├── wifi_bt_analyser.py    # Main GUI application & Qt controller
├── gwba.py                # Fast launcher / CLI shortcut
├── wirelessengine.py      # Core 802.11 packet parsing & interface management
├── btengine.py            # Bluetooth (Classic & BLE) engine & BlueZ integration
├── common.py              # Shared thread primitives and utility helpers
├── gpsengine.py           # GPS telemetry integration (gpsd)
├── tablewidgets.py        # Customized numeric and date sortable table items
├── setup.sh               # Environment setup & monitor mode hardware configuration
├── test_monitor_mode.py   # Diagnostic script for verifying monitor mode RX
├── requirements.txt       # Python library dependencies
├── manuf                  # IEEE Organizationally Unique Identifier (OUI) database
├── tests/
│   └── test_scanners.py   # Automated pytest unit & GUI test cases
└── README.md              # Project documentation
```

---

## Troubleshooting

### 1. `wlan0mon: Device or resource busy`
If NetworkManager attempts to manage the monitor interface, either run `sudo ./setup.sh` which puts `wlan0` into unmanaged mode automatically, or disable NetworkManager intervention manually:
```bash
sudo nmcli device set wlan0 managed no
```

### 2. Intel AX201 Frame Capture Dropping
Intel `iwlwifi` drivers require creating a separate monitor virtual interface (`iw phy phyX interface add wlan0mon type monitor`) rather than altering the base interface in-place. `setup.sh` handles this method automatically.

### 3. Bluetooth Not Initializing
Ensure the Bluetooth daemon is active and powered on:
```bash
sudo systemctl restart bluetooth
sudo bluetoothctl power on
```

---

## License & Notice

Distributed under the MIT License. Developed for educational, research, and authorized wireless diagnostic and security auditing purposes.
