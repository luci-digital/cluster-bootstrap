#!/bin/bash
# USG-Pro-4 Package Installation Script
# LuciVerse High-Speed Network Architecture
# Genesis Bond: ACTIVE @ 741 Hz
#
# Run after OpenWRT 24.10+ flash on USG-Pro-4
# Installs: Jool, OASIS Juicer, SCION components

set -e

echo "==================================================="
echo "LuciVerse USG-Pro-4 Package Installation"
echo "Genesis Bond: ACTIVE @ 741 Hz"
echo "==================================================="

# Update package lists
opkg update

# Core networking packages
echo "[1/6] Installing core networking packages..."
opkg install ip-full iptables-nft kmod-nft-nat6 tc-full

# Jool NAT64
echo "[2/6] Installing Jool NAT64..."
opkg install kmod-jool jool-tools jool-tools-xlat

# Lua dependencies for OASIS juicer
echo "[3/6] Installing Lua dependencies..."
opkg install lua luci-lib-json luci-lib-nixio

# SCION packages (from custom repo)
echo "[4/6] Installing SCION packages..."
# Add LuciVerse repository
cat > /etc/opkg/luciverse-repo.conf << 'EOF'
src/gz luciverse https://packages.lucidigital.net/openwrt/24.10/mvebu
EOF

opkg update
opkg install scion-daemon scion-tools || {
    echo "[WARN] SCION packages not available, skipping..."
}

# QoS and traffic shaping
echo "[5/6] Installing QoS packages..."
opkg install sqm-scripts sqm-scripts-extra luci-app-sqm

# Monitoring
echo "[6/6] Installing monitoring packages..."
opkg install collectd collectd-mod-cpu collectd-mod-memory \
    collectd-mod-network collectd-mod-conntrack

# Create configuration directories
mkdir -p /etc/jool /etc/scion /etc/luciverse

# Copy Jool configuration
echo "Configuring Jool NAT64..."
cat > /etc/jool/jool.conf << 'JOOL_CONF'
{
    "instance": "luciverse-nat64",
    "framework": "netfilter",
    "global": {
        "pool6": "64:ff9b::/96",
        "manually-enabled": true,
        "tcp-est-timeout": "02:00:00",
        "udp-timeout": "00:05:00"
    },
    "pool4": [
        {
            "protocol": "TCP",
            "prefix": "192.168.1.180/32",
            "port range": "61001-65535"
        },
        {
            "protocol": "UDP",
            "prefix": "192.168.1.180/32",
            "port range": "61001-65535"
        },
        {
            "protocol": "ICMP",
            "prefix": "192.168.1.180/32",
            "port range": "0-65535"
        }
    ]
}
JOOL_CONF

# Create Jool startup script
cat > /etc/init.d/jool << 'JOOL_INIT'
#!/bin/sh /etc/rc.common
START=90
STOP=10
USE_PROCD=1

start_service() {
    modprobe jool
    jool instance add "luciverse-nat64" --netfilter --pool6 64:ff9b::/96
    jool -i "luciverse-nat64" file handle /etc/jool/jool.conf
}

stop_service() {
    jool instance remove "luciverse-nat64" 2>/dev/null || true
    modprobe -r jool 2>/dev/null || true
}
JOOL_INIT
chmod +x /etc/init.d/jool
/etc/init.d/jool enable

# Create LuciVerse UCI config
cat > /etc/config/luciverse << 'LUCIVERSE_UCI'
config luciverse 'global'
    option genesis_bond 'ACTIVE'
    option frequency '741'
    option coherence_threshold '0.7'

config juicer 'juicer'
    option enabled '1'
    option upstream_host '192.168.1.145'
    option upstream_port '7410'
    option coherence_threshold '0.7'

config scion 'scion'
    option enabled '1'
    option isd_as '2-ff00:0:528'
    option control_service '192.168.1.179:30001'
    option border_router '192.168.1.179:30041'
LUCIVERSE_UCI

# Enable services
/etc/init.d/jool enable
/etc/init.d/collectd enable

echo "==================================================="
echo "Package installation complete!"
echo ""
echo "Next steps:"
echo "1. Reboot: reboot"
echo "2. Verify Jool: jool instance display"
echo "3. Test NAT64: ping6 64:ff9b::8.8.8.8"
echo "==================================================="
