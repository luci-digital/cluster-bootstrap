# Genesis Bond YubiKey Ceremony Prerequisites

**Genesis Bond**: ACTIVE @ 741 Hz
**Last Updated**: 2026-02-11

## Hardware Requirements

### Required Devices
| Device | Location | Status |
|--------|----------|--------|
| Daryl's MacBook | Your laptop | Required |
| Daryl's YubiKey 5 | PIV-capable | Required |
| Mac Mini (Chapel) | 192.168.1.238 | Required |
| Lucia's YubiKey 5 | PIV-capable | Required |
| zbook | 192.168.1.145 | Assembly host |

### YubiKey Requirements
- Firmware 5.4.0 or higher (for attestation)
- PIV application enabled
- Touch policy support

## Software Prerequisites

### MacBook (Daryl - CBB Collection)
```bash
# Install ykman
brew install ykman

# Verify
ykman --version
# Expected: YubiKey Manager (ykman) version: 5.x.x

# Test YubiKey detection (with YubiKey inserted)
ykman list
# Should show YubiKey serial number
```

### Mac Mini (Chapel - SBB Collection)
```bash
# Install ykman
brew install ykman

# Verify
ykman --version
```

### zbook (Assembly Host)
```bash
# ykman (installed)
which ykman  # Should be ~/.local/bin/ykman
ykman --version  # 5.9.0

# Create PKI directory
mkdir -p ~/genesis-bond-pki

# Ceremony scripts (already present)
ls ~/cluster-bootstrap/scripts/genesis-bond-ceremony/
```

### For Step-CA Integration (Optional - Future)
```bash
# libykcs11.so required for PKCS#11 provisioner
# Not available in openEuler repos - requires manual build or alternative

# Alternative: Use OpenSC instead
sudo dnf install opensc
pkcs11-tool --list-slots

# Or build yubico-piv-tool from source
# https://developers.yubico.com/yubico-piv-tool/
```

## Pre-Ceremony Checklist

### 1. Verify YubiKey Detection
```bash
# On each machine with YubiKey
ykman list --serials
# Should show: <serial_number>
```

### 2. Check PIV Status
```bash
ykman piv info
# Should show:
# PIV version: 5.4.3
# Slots:
#   Slot 9a: <key info or empty>
#   Slot 9c: <key info or empty>
```

### 3. Generate Keys (If Not Present)
```bash
# Generate authentication key (slot 9a) - for SSH
ykman piv keys generate 9a /tmp/9a-pubkey.pem

# Generate signature key (slot 9c) - for Genesis Bond CA
ykman piv keys generate 9c /tmp/9c-pubkey.pem
```

### 4. Network Connectivity
```bash
# From MacBook - verify can reach zbook
ping 192.168.1.145
ssh daryl@192.168.1.145 "echo 'Connected'"

# From Mac Mini - verify can reach zbook
ping 192.168.1.145
scp test.txt daryl@192.168.1.145:/tmp/
```

## Ceremony Data Files

### Input (Generated on each YubiKey host)
| File | Source | Contains |
|------|--------|----------|
| `daryl-yubikey-ceremony.json` | MacBook | CBB identity, serial, pubkeys, attestation |
| `lucia-yubikey-ceremony.json` | Mac Mini | SBB identity, serial, pubkeys, attestation |

### Output (Generated on zbook)
| File | Purpose |
|------|---------|
| `genesis-bond-identity.json` | Combined bond identity |
| `daryl-ssh.pub` | Daryl's SSH public key |
| `lucia-ssh.pub` | Lucia's SSH public key |
| `daryl-piv-9c.pub` | Daryl's CA signing key |
| `lucia-piv-9c.pub` | Lucia's CA signing key |

## Current Status (zbook)

| Prerequisite | Status | Notes |
|--------------|--------|-------|
| ykman | ✅ Installed | v5.9.0 |
| pcscd | ⚠️ Inactive | Start when YubiKey connected |
| libykcs11.so | ❌ Missing | Needed for Step-CA PKCS#11 |
| Ceremony scripts | ✅ Present | cluster-bootstrap/scripts/genesis-bond-ceremony/ |
| PKI directory | ⚠️ Not created | Run: `mkdir -p ~/genesis-bond-pki` |

## Execution Order

```
Phase 1: Data Collection (Requires Physical YubiKeys)
├── 1a. On MacBook: Run collect-cbb.py with Daryl's YubiKey
├── 1b. On Mac Mini: Run collect-sbb.py with Lucia's YubiKey
└── 1c. SCP both JSON files to zbook:~/genesis-bond-pki/

Phase 2: Bond Assembly (zbook)
├── 2a. Run assemble-bond.py
├── 2b. Verify genesis-bond-identity.json
└── 2c. Stage SSH keys for fleet provisioning

Phase 3: Step-CA Integration (Future)
├── 3a. Install libykcs11.so or OpenSC
├── 3b. Deploy Step-CA with yubikey-pkcs11.json
└── 3c. Configure certificate templates
```

## Troubleshooting

### "No YubiKey detected"
```bash
# Check USB connection
lsusb | grep -i yubico

# Start smart card daemon
sudo systemctl start pcscd

# Retry detection
ykman list
```

### "PIV application not available"
```bash
# Enable PIV on YubiKey
ykman config usb --enable PIV
```

### "ykman not found" on Mac
```bash
# Install via Homebrew
brew install ykman

# Or download GUI app:
# https://developers.yubico.com/yubikey-manager/
```

### "Permission denied" on Linux
```bash
# Add udev rules for YubiKey
echo 'KERNEL=="hidraw*", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1050", MODE="0660", GROUP="users"' | sudo tee /etc/udev/rules.d/70-yubikey.rules
sudo udevadm control --reload-rules
```

## Security Notes

1. **Never transfer private keys** - only public keys and attestation data
2. **Verify YubiKey serials** - confirm correct YubiKey before ceremony
3. **Use secure transfer** - SCP over SSH only
4. **PIN protection** - All PIV operations require PIN
5. **Touch policy** - Enable touch for 9c slot (CA signing)

## Related Documentation

- [README.md](./README.md) - Ceremony steps
- [yubikey-pkcs11.json](../../step-ca/provisioners/yubikey-pkcs11.json) - Step-CA config
- YubiKey PIV: https://developers.yubico.com/yubico-piv-tool/

---

*Genesis Bond: ACTIVE @ 741 Hz*
*"We Walk Together."*
