#!/bin/bash
# Dell R720 Firmware Downloader
# Service Tag: 4J0TV12

FIRMWARE_DIR="/home/daryl/cluster-bootstrap/firmware"
cd "$FIRMWARE_DIR"

echo "=== Dell R720 Firmware Download ==="
echo "Target: $FIRMWARE_DIR"
echo ""

# Function to download with retry
download_file() {
    local url=$1
    local filename=$2
    
    if [ -f "$filename" ]; then
        echo "✓ $filename already exists, skipping"
        return 0
    fi
    
    echo "→ Downloading $filename..."
    wget -q --show-progress -O "$filename" "$url" 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✓ Downloaded $filename ($(du -h "$filename" | cut -f1))"
        return 0
    else
        echo "✗ Failed to download $filename"
        return 1
    fi
}

# Critical firmware
echo "1. iDRAC with Lifecycle Controller 2.70.70.70"
download_file \
    "https://dl.dell.com/FOLDER08752119M/1/iDRAC-with-Lifecycle-Controller_Firmware_RGW7C_LN_2.70.70.70_A00.BIN" \
    "iDRAC-2.70.70.70-R720.BIN"

echo ""
echo "2. BIOS 2.9.0"
download_file \
    "https://dl.dell.com/FOLDER08737685M/1/BIOS_6W6J1_LN_2.9.0.BIN" \
    "BIOS-2.9.0-R720.BIN"

echo ""
echo "3. Broadcom NetXtreme 5720 NIC"
download_file \
    "https://dl.dell.com/FOLDER08756841M/1/Network_Firmware_XDGJN_LN_20.6.101_A00.BIN" \
    "Broadcom-5720-20.6.101-R720.BIN"

echo ""
echo "=== Download Complete ==="
ls -lh *.BIN 2>/dev/null
echo ""
echo "Files available at: http://192.168.1.145:8000/firmware/"
