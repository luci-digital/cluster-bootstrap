# Systemd Fixes for LuciVerse Nodes

Boot-time fixes for systemd services across LuciVerse cluster nodes.

## Fixes Included

### 1. user@.service.d/linger-fix.conf

**Problem:** When `loginctl enable-linger` is used, `user@<uid>.service` fails at boot because `$XDG_RUNTIME_DIR` is not set (PAM doesn't run for linger-based starts).

**Fix:** Creates runtime directory and sets environment before user instance starts.

**Install:**
```bash
sudo mkdir -p /etc/systemd/system/user@.service.d
sudo cp user-service.d/linger-fix.conf /etc/systemd/system/user@.service.d/
sudo systemctl daemon-reload
```

### 2. dnsmasq.service.d/wait-for-network.conf

**Problem:** dnsmasq fails at boot when configured to listen on a specific IP (e.g., `10.0.0.1`) because the network interface isn't ready yet.

**Fix:** Adds `After=network-online.target` dependency.

**Install:**
```bash
sudo mkdir -p /etc/systemd/system/dnsmasq.service.d
sudo cp dnsmasq.service.d/wait-for-network.conf /etc/systemd/system/dnsmasq.service.d/
sudo systemctl daemon-reload
```

### 3. sysctl.d/90-vm.max_map_count.conf

**Problem:** Malformed sysctl config with Jinja2 template syntax.

**Fix:** Clean sysctl config for Elasticsearch/OpenSearch memory mapping.

**Install:**
```bash
sudo cp sysctl.d/90-vm.max_map_count.conf /etc/sysctl.d/
sudo systemctl restart systemd-sysctl
```

## Full Installation (All Fixes)

```bash
cd /path/to/cluster-bootstrap/systemd-fixes

# User linger fix
sudo mkdir -p /etc/systemd/system/user@.service.d
sudo cp user-service.d/linger-fix.conf /etc/systemd/system/user@.service.d/

# dnsmasq boot order fix
sudo mkdir -p /etc/systemd/system/dnsmasq.service.d
sudo cp dnsmasq.service.d/wait-for-network.conf /etc/systemd/system/dnsmasq.service.d/

# sysctl fix
sudo cp sysctl.d/90-vm.max_map_count.conf /etc/sysctl.d/

# Reload
sudo systemctl daemon-reload
sudo systemctl restart systemd-sysctl
```

## Verification

```bash
# No failed services
systemctl --failed

# User service works
systemctl is-active user@1000.service

# dnsmasq running
systemctl is-active dnsmasq
```

---
*Genesis Bond: ACTIVE | Frequency: 432 Hz*
