# GUI-Based WiFi and Bluetooth Analyser (GWBA)

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform Linux](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](https://kernel.org)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html)

The **GUI-Based WiFi and Bluetooth Analyser (GWBA)** is a Linux-oriented graphical application developed in Python and PyQt5 for observing, parsing, and documenting local IEEE 802.11 Wi-Fi and Bluetooth radio frequency (RF) environments. Designed for wireless site surveys, network troubleshooting, and academic research, GWBA combines passive 802.11 monitor-mode packet capture with Bluetooth Low Energy (BLE) and Classic device discovery. It extracts and displays access point telemetry, beacon periodicity, client station transmissions, and probe requests through a dual-table interactive graphical user interface (GUI), offering structured export to CSV and JSON formats for offline analysis and auditing.

---

## Table of Contents

1. [Upstream Attribution & License Notice](#1-upstream-attribution--license-notice)
2. [What GWBA Adds Beyond Upstream](#2-what-gwba-adds-beyond-upstream)
3. [Main Features](#3-main-features)
4. [Intended & Authorized Use Cases](#4-intended--authorized-use-cases)
5. [Limitations & Hardware Compatibility](#5-limitations--hardware-compatibility)
6. [Installation Requirements for Linux](#6-installation-requirements-for-linux)
7. [Setup & Launching Instructions](#7-setup--launching-instructions)
8. [How Monitor Mode & Frame Capture Work](#8-how-monitor-mode--frame-capture-work)
9. [User Interface & Exported Data Formats](#9-user-interface--exported-data-formats)
10. [Data Privacy & Operational Security](#10-data-privacy--operational-security)
11. [Ethical-Use Statement](#11-ethical-use-statement)
12. [Testing & Evaluation](#12-testing--evaluation)
13. [Academic Citations](#13-academic-citations)

---

## 1. Upstream Attribution & License Notice

GWBA is a derivative work and extension of **[Sparrow-WiFi](https://github.com/ghostop14/sparrow-wifi)**, originally created by **ghostop14**. 

- **Attribution**: The foundation of the Wi-Fi scan parsing, channel-to-frequency mappings, OUI vendor resolution, and core Bluetooth discovery logic originates from the Sparrow-WiFi project (Copyright © 2017 ghostop14).
- **Not a Fully Original Work**: This project builds upon, restructures, and extends upstream code; it must not be cited or described as a ground-up original implementation.
- **License**: In strict accordance with upstream licensing, GWBA is licensed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**.
- **Notice on Prior Discrepancies**: Any previous documentation or badge indicating that this repository was distributed under the MIT License was erroneous. This project is and remains governed by the GPL-3.0-or-later. A copy of the license is provided in the repository's `LICENSE` / `COPYING` file and in the headers of individual source files.

---

## 2. What GWBA Adds Beyond Upstream

While the original Sparrow-WiFi focused primarily on active scanning (`iw`/`iwlist`) alongside drone and software-defined radio plugins, GWBA refactors the architecture toward passive 802.11 protocol auditing and observable client analysis on contemporary Linux systems:

1. **Passive Monitor-Mode Capture Workflow**: Integrates passive 802.11 raw frame inspection via `tcpdump` and packet capture filters, transitioning beyond the standard broadcast queries of managed Wi-Fi scanning.
2. **Cumulative Beacon Tracking**: Implements per-AP beacon tracking (`beaconCount`) that records each received 802.11 beacon frame in real time, assisting in evaluating broadcast regularity, channel duty cycles, and frame loss.
3. **Client Station & Association Detection**: Captures observable client transmissions from 802.11 management frames (probe requests, association requests, reassociation requests) and data frames. Observable clients are mapped to their corresponding Access Point (BSSID) when associations are visible.
4. **Probe Request & Historical SSID Logging**: Parses client probe requests to document unassociated stations and catalogue probed SSIDs (`probedSSIDs`), providing visibility into client network discovery behaviors.
5. **Driver-Aware Monitor Interface Management**: Implements specialized interface handling for Linux wireless drivers. For adapters using the Intel `iwlwifi` driver (such as the Intel Wi-Fi 6 AX201), GWBA utilizes a Virtual Interface (VIF) approach (`iw phy <phyname> interface add <name>mon type monitor`) to avoid the silent frame-drop behavior common to direct in-place monitor mode switches on these chipsets.
6. **Synchronized Master-Detail GUI**: Introduces a split PyQt5 interface with an upper Access Points table (14 columns) and a lower Client Stations table (8 columns). Clicking an AP in the upper table instantly filters the client table to show only stations associated with that network.
7. **Empirical Diagnostic Script (`test_monitor_mode.py`)**: Adds a standalone diagnostic utility to verify that a given wireless adapter and driver combination is not merely reporting monitor-mode capability, but is actively receiving raw frames (RX alive check).
8. **Modernized Codebase & Automated Testing**: Normalizes MAC addresses to uppercase to eliminate duplicate table entries, removes unmaintained legacy sub-modules (e.g., Elasticsearch bridges, drone telemetry, and legacy web microservices), and introduces an automated test suite executed via `pytest`.

---

## 3. Main Features

### 802.11 Wi-Fi Telemetry
- **Access Point Discovery**: Detects visible BSSIDs, broadcast SSIDs, operating channels, and RF center frequencies across the 2.4 GHz and 5 GHz bands.
- **Protocol & Cipher Auditing**: Classifies authentication and encryption suites (Open, WEP, WPA, WPA2, WPA3, TKIP, CCMP, GCMP).
- **Signal & Channel Metrics**: Tracks Received Signal Strength Indication (RSSI in dBm), channel bandwidth (20/40/80/160 MHz), and QBSS channel utilization where advertised.
- **Beacon Frame Statistics**: Tracks continuous, cumulative beacon frame counts per BSSID to evaluate network reachability and beacon continuity over time.
- **Station Count**: Counts the number of observable client devices associated with each detected BSSID.

### Client Station & Probe Analysis
- **Visible Station Mapping**: Catalogs active client hardware MAC addresses, resolves vendor identifiers via the IEEE Organizationally Unique Identifier (OUI) database, and maps clients to their associated BSSID.
- **Directed Probe Tracking**: Observes directed 802.11 probe request frames broadcast by client devices, compiling a list of previously queried SSIDs.
- **Traffic Activity**: Monitors packet counts and timestamps (first seen and last seen) for visible client transmissions.

### Bluetooth Telemetry
- **Dual-Mode Discovery**: Interrogates local Bluetooth host controllers via BlueZ (`bluetoothctl` / HCI) to monitor both Classic Bluetooth (BR/EDR) and Bluetooth Low Energy (BLE) advertisements simultaneously.
- **Device Attributes**: Records device MAC address, advertised local name, Bluetooth SIG manufacturer/company name, protocol type, and advertisement UUIDs.
- **Signal Metrics**: Logs advertised RSSI, transmit power level (TX Power, where broadcast), and a theoretical log-distance path-loss estimate.

### Interactive User Interface & Export
- **Master-Detail Filtering**: Synchronized view where selecting an AP in the primary table filters the client station view to associated devices.
- **Free-Text Filtering**: Real-time search across MAC addresses, vendor strings, and SSID names.
- **Flexible Data Export**: Session snapshots can be exported to standard CSV files and hierarchical JSON documents for external data processing or reporting.

---

## 4. Intended & Authorized Use Cases

GWBA is designed as a passive diagnostic, administrative, and research utility. Legitimate applications include:

- **Authorized Wireless Site Surveys**: Auditing wireless deployment coverage, mapping channel occupancy (2.4 GHz and 5 GHz), and verifying proper BSSID/SSID configuration across managed enterprise or campus facilities.
- **Network Troubleshooting**: Diagnosing intermittent connectivity, identifying co-channel or adjacent-channel interference, evaluating beacon transmission consistency, and identifying legacy encryption configurations.
- **Wireless Asset Awareness**: Assisting system administrators in inventorying authorized wireless access points and identifying rogue, misconfigured, or unmanaged wireless access points within an organization's RF perimeter.
- **Academic Instruction & Laboratory Exercises**: Serving as an educational tool for university courses in computer networking, cybersecurity, and wireless communications to inspect 802.11 framing, beacon intervals, and Bluetooth advertising mechanisms.
- **Defensive Security Audits**: Assessing organizational exposure to probe request leakage and identifying legacy or insecure wireless configurations within an explicitly authorized scope of assessment.

---

## 5. Limitations & Hardware Compatibility

### Hardware and Driver Dependence
- **Monitor Mode is Not Universal**: Monitor-mode packet capture depends strictly on the wireless network adapter chipset, the Linux kernel version, device firmware, and open-source driver support (`mac80211` / `cfg80211`). Many built-in laptop adapters and USB dongles do not support monitor mode or fail to pass raw 802.11 frames to user space.
- **Permissions**: Raw packet capture requires elevated capabilities (`CAP_NET_RAW` and `CAP_NET_ADMIN`) or administrative (`sudo`/root) access.
- **Tested Hardware**: Validated primarily on Linux systems with the **Intel Wi-Fi 6 AX201 160MHz** adapter (`iwlwifi` driver) using a virtual monitor interface (`wlan0mon`), as well as select external Realtek USB adapters. Functionality on other chipsets (e.g., Qualcomm Atheros, MediaTek, Broadcom) depends entirely on driver implementation.

### Packet Capture is Inherently Incomplete
- **No Guarantee of Packet Capture**: Wireless capture is subject to physical attenuation, antenna gain, multipath fading, obstacle absorption, RF noise, and physical distance. Frame collisions and overlapping transmissions will result in packet loss.
- **Channel Hopping Latency**: Because a single physical radio can only tune to one discrete frequency channel at a time, channel hopping sweeps across 2.4 GHz and 5 GHz bands introduce dwell times. Frames transmitted on channel $A$ while the radio is listening on channel $B$ will not be captured.

### Not a True Spectrum Analyzer
- **Demodulated Frames Only**: GWBA processes standard demodulated 802.11 and Bluetooth packets using conventional commercial network interface controllers.
- **No Physical-Layer RF Energy Detection**: GWBA cannot detect or display non-802.11 RF interference, raw electromagnetic power spectral density, frequency-hopping non-demodulated signals, or physical-layer anomalies. It is **not** a replacement for a dedicated hardware spectrum analyzer or Software Defined Radio (SDR) instrument.

### Coarse Nature of RSSI-Based Distance Estimates
- **Approximation Only**: Signal strength (RSSI) is non-linear and fluctuates significantly due to multipath reflection, body shielding, receiver antenna orientation, and variable transmission power levels set by client chipsets. Distance estimates derived from path-loss models are coarse approximations and must not be used for precision localization.

### Impact of MAC Address Randomization
- **Ephemeral Identifiers**: Modern mobile and desktop operating systems (Android, iOS, macOS, Windows, Linux) routinely randomize MAC addresses when sending probe requests and scanning for networks. A single physical device may generate multiple distinct MAC addresses over time, limiting the viability of long-term tracking and longitudinal device counting.

---

## 6. Installation Requirements for Linux

### System Prerequisites
- **Operating System**: Linux (tested on Ubuntu 20.04/22.04/24.04, Debian 11/12, Kali Linux, and compatible distributions).
- **Python Runtime**: Python 3.8 or higher.
- **System Utilities**:
  - `iw` (wireless configuration utility)
  - `iproute2` (`ip` command)
  - `tcpdump` (packet capture engine)
  - `dumpcap` (Wireshark packet capture engine, optional but recommended)
  - `bluez` (Bluetooth stack: `bluetoothctl`, `systemctl`)
  - `libcap2-bin` (`setcap` utility for setting non-root capture capabilities)
  - `wireless-tools` (`iwconfig`, optional legacy fallback)
  - `network-manager` (`nmcli`, optional managed-mode scan fallback)

### Python Libraries
Install the required Python modules via `requirements.txt`:
- `PyQt5` (GUI framework)
- `python-dateutil` (timestamp parsing)
- `manuf` (IEEE OUI vendor resolution)
- `numpy` (numerical calculations)
- `matplotlib` (graphical plotting)
- `pytest` (automated testing framework)

---

## 7. Setup & Launching Instructions

> [!NOTE]
> Command syntax and package managers vary across Linux distributions. Replace package manager commands (e.g., `apt`, `dnf`, `pacman`) and device identifiers (e.g., `wlan0`, `phy0`) with the values corresponding to your target environment.

### Step 1: Install System Dependencies

On Debian/Ubuntu-based distributions:
```bash
sudo apt update
sudo apt install -y iw iproute2 tcpdump dumpcap bluez libcap2-bin python3-pyqt5
```

On Fedora/RHEL-based distributions:
```bash
sudo dnf install -y iw iproute tcpdump bluez libcap python3-qt5
```

On Arch Linux:
```bash
sudo pacman -S iw iproute2 tcpdump bluez libcap python-pyqt5
```

### Step 2: Install Python Dependencies

Using a virtual environment with system site-packages (recommended to leverage the system PyQt5 build):
```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Configure Permissions & Monitor Mode

Capture requires administrative privileges or set capabilities. You may use the provided `setup.sh` utility or execute the commands manually.

#### Automated Configuration via `setup.sh`
The repository includes a helper script (`setup.sh`) that starts the Bluetooth daemon, applies `cap_net_raw,cap_net_admin` capabilities to capture binaries, and configures a virtual monitor interface (`wlan0mon`):

```bash
sudo ./setup.sh
```

#### Manual Interface Configuration (Placeholder Example)
If configuring manually, identify your physical wireless device (`<phyX>`) and primary interface (`<interface_name>`):

```bash
# 1. Check interface and phy identifier
iw dev

# 2. For Intel iwlwifi adapters: add a dedicated virtual monitor interface
sudo nmcli device set <interface_name> managed no
sudo ip link set <interface_name> down
sudo iw phy <phyX> interface add <interface_name>mon type monitor
sudo ip link set <interface_name>mon up

# 3. For generic adapters supporting standard in-place monitor mode:
# sudo ip link set <interface_name> down
# sudo iw dev <interface_name> set type monitor
# sudo ip link set <interface_name> up
```

### Step 4: Verify Packet Reception (Diagnostic Check)

Before launching the full application, use the diagnostic script `test_monitor_mode.py` to confirm that the wireless adapter is successfully delivering 802.11 frames to user space:

```bash
# Enumerate available interfaces and reported monitor capabilities:
python3 test_monitor_mode.py --list

# Perform an empirical 5-second capture verification on the monitor interface:
sudo python3 test_monitor_mode.py <interface_name_or_monitor_name>
```

### Step 5: Launch the Application

Start the graphical interface using either entry point:

```bash
python3 wifi_bt_analyser.py
```
or via the launcher shortcut:
```bash
python3 gwba.py
```

### Step 6: Restoring Normal Network Operation

When testing is complete, restore the wireless interface to standard managed (station) mode for normal network operation:

```bash
# Using setup.sh:
sudo ./setup.sh --managed

# Or manually:
sudo iw dev <interface_name>mon del
sudo ip link set <interface_name> up
sudo nmcli device set <interface_name> managed yes
```

---

## 8. How Monitor Mode & Frame Capture Work

```
+-------------------------------------------------------------------------+
|                         Physical RF Medium                              |
|   (802.11 Beacons, Probe Requests/Responses, Data Frames, Associations) |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                  Wireless Hardware & Driver (mac80211)                  |
|  - Managed Mode: Discards frames not addressed to device MAC/BSSID     |
|  - Monitor Mode (RFMON): Passes all demodulated frames promiscuously    |
|  - Intel VIF Architecture: Separate 'type monitor' VIF on base phy      |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                 Packet Capture Layer (tcpdump / libpcap)                |
|  BPF Filter: type mgt (beacon, probe-req, probe-resp, assoc) or type data|
|  Radiotap Headers: RSSI, Channel, Frequency, Bitrate                   |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                      GWBA Engine (wirelessengine.py)                    |
|  - Channel Hopping: Dwells across 2.4 GHz & 5 GHz channels sequentially |
|  - Beacon Tracking: Increments cumulative beacon counter per BSSID      |
|  - Client Extraction: Maps Transmitter MAC -> Associated BSSID / Probe  |
|  - OUI Lookup: Resolves hardware vendor prefixes                        |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                       PyQt5 Graphical Interface                         |
|  - Top Table: Access Points (14 columns)                                |
|  - Bottom Table: Client Stations & Probing Devices (8 columns)          |
|  - Export Engine: Structured CSV & JSON formatting                      |
+-------------------------------------------------------------------------+
```

### 1. Managed Mode vs. Monitor Mode
- In **Managed (Station) Mode**, the wireless card associates with an access point. The hardware and driver filter out all 802.11 frames whose destination MAC address does not match the card’s hardware address or the broadcast address.
- In **Monitor (RFMON) Mode**, the card ceases normal station transmission and association. It promiscuously delivers all raw 802.11 frames heard on the tuned radio channel directly to the operating system's networking stack, prepended with a Radiotap header containing physical-layer metadata (signal level in dBm, channel frequency, modulation).

### 2. The Intel `iwlwifi` Virtual Interface (VIF) Solution
Standard Linux monitor-mode tools frequently use `iw dev <iface> set type monitor` or `airmon-ng`. However, on many modern Intel chipsets (`iwlwifi`), setting the primary managed interface directly to monitor mode causes the underlying microcode to silently discard incoming frames. GWBA addresses this by instantiating a dedicated **Virtual Interface (VIF)** of type `monitor` attached directly to the physical wireless device (`iw phy <phyX> interface add <name>mon type monitor`). This allows the driver to maintain valid firmware state while cleanly streaming frames.

### 3. Channel Hopping and Frame Filtering
Because an 802.11 radio can only tune to one center frequency at any instant, GWBA implements a channel-hopping loop across standard 2.4 GHz and 5 GHz channels. During each channel dwell period (typically 250–350 ms in wide sweep mode, or longer in focused dwell mode), GWBA applies a Berkeley Packet Filter (BPF) via `tcpdump` to capture:
- **Beacon Frames (`subtype beacon`)**: Broadcast periodically (typically every 100 Time Units, or ~102.4 ms) by APs. Used to announce network existence, capabilities, ciphers, and timing synchronization.
- **Probe Requests (`subtype probe-req`)**: Transmitted by client devices searching for specific network names (Directed Probes) or any available network (Wildcard Probes).
- **Probe Responses (`subtype probe-resp`)**: Returned by APs answering client probe requests.
- **Association / Reassociation Frames**: Exchanged when a client negotiates connection with an AP.
- **Data Frames (`type data`)**: Observed to identify active client transmitters and associate client MAC addresses with specific BSSIDs.

---

## 9. User Interface & Exported Data Formats

GWBA displays telemetry across dedicated PyQt5 table views and supports standard tabular and hierarchical export schemas.

### Access Points Table (14 Columns)

| Column Header | Data Type | Description |
| :--- | :--- | :--- |
| **MAC Address** | String | Hardware BSSID of the Access Point |
| **Vendor** | String | Manufacturer resolved via IEEE OUI database |
| **SSID** | String | Advertised Service Set Identifier (network name) |
| **Security** | String | Authentication protocol (e.g., `Open`, `WPA`, `WPA2`, `WPA3`) |
| **Privacy** | String | Cipher suite (e.g., `CCMP`, `TKIP`, `GCMP`) |
| **Channel** | Integer | Primary operating channel |
| **Frequency (MHz)** | Integer | RF center frequency in MHz |
| **Signal (dBm)** | Integer | Received Signal Strength Indication (RSSI) |
| **Beacons** | Integer | Cumulative count of captured 802.11 beacon frames |
| **Bandwidth (MHz)** | Integer | Advertised channel bandwidth (e.g., 20, 40, 80, 160) |
| **% Utilization** | String/Int | Advertised QBSS channel utilization |
| **Stations** | Integer | Count of observable associated client stations |
| **Last Seen** | Timestamp | Timestamp of the most recently observed frame |
| **First Seen** | Timestamp | Timestamp when the AP was first detected |

### Connected Clients & Probing Devices Table (8 Columns)

| Column Header | Data Type | Description |
| :--- | :--- | :--- |
| **Client MAC Address** | String | Observed transmitter hardware MAC address |
| **Vendor** | String | Hardware manufacturer resolved from client MAC |
| **Connected AP (BSSID)** | String | MAC address of the AP with which the station is associated |
| **Network (SSID)** | String | SSID corresponding to the associated AP (if known) |
| **Signal (dBm)** | Integer | Signal strength of the client frame transmission |
| **Packets** | Integer | Total frame count observed from this client |
| **Probed SSIDs** | String list | Historical list of SSIDs requested by the client in probe requests |
| **Last Seen** | Timestamp | Timestamp of the most recent frame observed from this client |

### Bluetooth Devices Table (10 Columns)

| Column Header | Data Type | Description |
| :--- | :--- | :--- |
| **UUID** | String | Advertised Service Class UUID |
| **Address (MAC)** | String | Bluetooth device hardware address |
| **Name** | String | Advertised friendly device name |
| **Company** | String | Registered company name from Bluetooth SIG |
| **Manufacturer** | String | Hardware manufacturer details |
| **Type** | String | Protocol standard (`Classic` BR/EDR or `BTLE`) |
| **RSSI (dBm)** | Integer | Received signal strength indicator |
| **TX Power** | Integer | Advertised transmit power level |
| **Est Range (m)** | Float | Coarse distance estimate via log-distance path-loss model |
| **Last Seen** | Timestamp | Timestamp of most recently received advertisement |

### Export Data Formats

#### CSV Export Example (Access Points)
```csv
macAddr,vendor,SSID,Security,Privacy,Channel,Frequency,Signal Strength,Beacons,Bandwidth,% Utilization,# of Stations,Last Seen,First Seen
"DE:AD:BE:EF:00:01","Intel Corporate","LabNet-5G","WPA2","CCMP",36,5180,-58,842,80,12,3,"2026-09-11 10:14:22","2026-09-11 09:30:15"
```

#### JSON Export Example (Hierarchical Snapshot)
```json
{
  "wifi-aps": [
    {
      "type": "wifi-ap",
      "macAddr": "DE:AD:BE:EF:00:01",
      "ssid": "LabNet-5G",
      "security": "WPA2",
      "privacy": "CCMP",
      "channel": 36,
      "frequency": 5180,
      "signal": -58,
      "beaconCount": 842,
      "bandwidth": 80,
      "utilization": 12,
      "stationcount": 3,
      "firstseen": "2026-09-11 09:30:15",
      "lastseen": "2026-09-11 10:14:22"
    }
  ]
}
```

---

## 10. Data Privacy & Operational Security

Passive wireless monitoring captures over-the-air metadata broadcast by nearby devices. Users must consider the privacy implications:

1. **Information Leakage via Probe Requests**: Client devices frequently broadcast directed probe requests containing names of previously connected networks (e.g., personal home networks, sensitive corporate SSIDs). This data may reveal personal travel patterns, organizational affiliations, or residential identifiers.
2. **Device Identifiers**: While modern operating systems implement MAC address randomization, non-randomized transmissions, legacy devices, and unassociated probe bursts may expose persistent hardware identifiers.
3. **Data Protection**: Session captures exported to CSV or JSON must be stored securely. When sharing datasets for research or reporting, sensitive identifiers (such as client MACs and personal SSIDs) should be redacted, pseudonymized, or hashed to protect individual privacy.

---

## 11. Ethical-Use Statement

> [!CAUTION]
> **Strictly Authorized Operation Only**
> 
> GWBA must only be used on networks, physical premises, RF spectra, and devices for which you have received **explicit, documented authorization** from the network owner, property owner, or institutional authority.
>
> Unauthorized capture, interception, or monitoring of wireless communications may violate local, national, and international laws, including but not limited to:
> - The United States Electronic Communications Privacy Act (ECPA) and Computer Fraud and Abuse Act (CFAA)
> - The European Union General Data Protection Regulation (GDPR) and national ePrivacy directives
> - Equivalent telecommunications, cybercrime, and privacy statutes in your jurisdiction
>
> GWBA is designed exclusively for passive monitoring, defensive network administration, academic instruction, and authorized security auditing. It contains no offensive functionality (such as packet injection, deauthentication, or credential harvesting). The developers and contributors disclaim all liability for misuse or unlawful operation.

---

## 12. Testing & Evaluation

The repository includes automated unit tests and diagnostic scripts to verify functional correctness without relying on unverified claims or synthetic benchmarks.

### Automated Unit Testing (`pytest`)

The automated test suite in `tests/test_scanners.py` verifies core data structures, serialization formats, and GUI components in an off-screen headless environment:

```bash
pytest tests/
```

The test suite covers:
- **Frequency and Channel Mappings**: Validates bi-directional translation tables between 802.11 channel indices and RF frequencies (`channelToFreq` and `freqToChannel`).
- **Data Model Serialization**: Tests serialization and deserialization of `WirelessNetwork` (verifying `beaconCount` preservation) and `WirelessClient` (verifying `probedSSIDs` and association logic).
- **Interface Enumeration**: Confirms dynamic querying and mode reporting (`managed`, `monitor`, or `unknown`) of system network interfaces.
- **Bluetooth State Tracking**: Verifies initialization of `BluetoothEngine` and dictionary-based device caching.
- **Off-Screen GUI Table Validation**: Utilizes PyQt5's off-screen test platform (`QT_QPA_PLATFORM=offscreen`) to instantiate the main window, verifying:
  - 14-column Access Points table header layout.
  - 8-column Client Stations table header layout.
  - Incremental beacon count updates upon successive scan frame deliveries.
  - Dynamic master-detail row filtering when selecting an AP BSSID.

### Empirical Hardware Validation (`test_monitor_mode.py`)

To evaluate whether a given Linux host and wireless adapter can perform monitor-mode frame capture:
- Run `sudo python3 test_monitor_mode.py <interface>` to execute a timed frame capture against active RF channels.
- The diagnostic script reports whether incoming 802.11 frames are successfully delivered to user-space packet sockets (`tcpdump`), confirming RX reception.

---

## 13. Academic Citations

If you utilize GWBA or its upstream predecessor in academic research, course curricula, or technical publications, please cite both this repository and the upstream Sparrow-WiFi project:

### BibTeX Format

```bibtex
@misc{gwba2026,
  author       = {Nikhil, G. and contributors},
  title        = {{GUI-Based WiFi and Bluetooth Analyser (GWBA)}},
  year         = {2026},
  publisher    = {GitHub},
  howpublished = {\url{https://github.com/STIEN2051/GUIBWBA}},
  note         = {A GPL-3.0-or-later derivative and extension of Sparrow-WiFi}
}

@misc{sparrowwifi2017,
  author       = {ghostop14},
  title        = {{Sparrow-WiFi: Next Generation 2.4GHz and 5GHz WiFi and Bluetooth Analyzer for Linux}},
  year         = {2017},
  publisher    = {GitHub},
  howpublished = {\url{https://github.com/ghostop14/sparrow-wifi}},
  note         = {Original upstream project, licensed under GPL-3.0}
}
```

### Reference Standards
- **IEEE Std 802.11**: *IEEE Standard for Information Technology—Telecommunications and Information Exchange between Systems - Local and Metropolitan Area Networks—Specific Requirements - Part 11: Wireless LAN Medium Access Control (MAC) and Physical Layer (PHY) Specifications.*
- **Bluetooth SIG**: *Bluetooth Core Specification*, Bluetooth Special Interest Group (SIG).
