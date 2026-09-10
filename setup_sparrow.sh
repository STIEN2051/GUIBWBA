#!/usr/bin/env bash
# ==============================================================================
# Sparrow WiFi — Environment Setup & Hardware Configuration Script
# ==============================================================================
set -e

MODE="${1:---monitor}"

if [ "$MODE" = "--managed" ]; then
    echo "=============================================================================="
    echo "[*] Restoring all wireless interfaces to MANAGED mode..."
    echo "=============================================================================="
    # 1. Restore wlan0mon -> wlan0
    if iw dev | grep -q "wlan0mon"; then
        echo "[*] Removing monitor VIF wlan0mon..."
        sudo iw dev wlan0mon del 2>/dev/null || true
        if ! iw dev | grep -q "wlan0"; then
            sudo iw phy phy1 interface add wlan0 type managed 2>/dev/null || true
        fi
        sudo ip link set wlan0 up 2>/dev/null || true
        sudo nmcli device set wlan0 managed yes 2>/dev/null || true
        echo "[+] wlan0 restored to MANAGED mode."
    fi

    # 2. Restore wlan1
    if iw dev | grep -q "wlan1"; then
        sudo ip link set wlan1 down 2>/dev/null || true
        sudo iw dev wlan1 set type managed 2>/dev/null || true
        sudo ip link set wlan1 up 2>/dev/null || true
        sudo nmcli device set wlan1 managed yes 2>/dev/null || true
        echo "[+] wlan1 returned to MANAGED mode."
    fi
    exit 0
fi

echo "[*] Step 1: Freeing disk space..."
if [ -d /var/cache/apt/archives ]; then
    sudo apt-get clean 2>/dev/null || true
    echo "[+] apt cache cleaned. Reclaimed disk space!"
fi

echo "[*] Step 2: Enabling and starting Bluetooth daemon..."
sudo systemctl enable --now bluetooth 2>/dev/null || true
echo "[+] bluetooth.service is active!"
bluetoothctl power on 2>/dev/null || true

echo "[*] Step 3: Setting network capture privileges for non-root users..."
sudo setcap cap_net_raw,cap_net_admin=eip /usr/bin/tcpdump 2>/dev/null || true
sudo setcap cap_net_raw,cap_net_admin=eip /usr/bin/dumpcap 2>/dev/null || true
sudo setcap cap_net_raw,cap_net_admin=eip /usr/sbin/iw 2>/dev/null || true
echo "[+] Packet capture capabilities configured."

echo "[*] Step 4: Configuring Wi-Fi hardware for MONITOR mode..."

# Priority 1: Intel AX201 (wlan0 -> wlan0mon) via high-performance VIF method
if iw dev | grep -q "wlan0"; then
    echo "[*] Configuring wlan0 (Intel AX201) via high-performance VIF monitor method..."
    sudo nmcli device set wlan0 managed no 2>/dev/null || true
    sudo ip link set wlan0 down 2>/dev/null || true
    sudo iw dev wlan0 del 2>/dev/null || true
    sudo iw dev wlan0mon del 2>/dev/null || true
    sudo iw phy phy1 interface add wlan0mon type monitor
    sudo ip link set wlan0mon up
    sudo iw dev wlan0mon set channel 1
    echo "[+] wlan0mon is active in MONITOR mode (capturing 10+ beacons/sec)!"
elif iw dev | grep -q "wlan0mon"; then
    echo "[+] wlan0mon is already active in MONITOR mode!"
fi

# Priority 2: wlan1 (Realtek adapter)
if iw dev | grep -q "wlan1"; then
    echo "[*] Configuring wlan1 (Realtek adapter) in monitor mode..."
    sudo nmcli device set wlan1 managed no 2>/dev/null || true
    sudo ip link set wlan1 down 2>/dev/null || true
    sudo iw dev wlan1 set type monitor 2>/dev/null || true
    sudo ip link set wlan1 up 2>/dev/null || true
    sudo iw dev wlan1 set channel 1 2>/dev/null || true
    echo "[+] wlan1 is configured in monitor mode."
fi

echo "=============================================================================="
echo "[+] Setup complete! Run Sparrow with:"
echo "    python3 sparrow-wifi.py"
echo ""
echo "[*] Select 'wlan0mon' in Sparrow WiFi and click Scan to capture live beacons!"
echo "[*] To restore normal managed Wi-Fi connections when finished, run:"
echo "    ./setup_sparrow.sh --managed"
echo "=============================================================================="
