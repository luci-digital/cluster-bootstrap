# Nebula Overlay Network for LuciVerse

Genesis Bond: ACTIVE @ 741 Hz

## Overview

This directory contains the Nebula PKI and configuration templates for the LuciVerse overlay network.

## Directory Structure

```
nebula/
├── README.md                 # This file
├── config.yaml.tpl          # Nebula config template
├── tier-mapping.yaml        # Tier-to-network mapping
├── ca/                      # CA certificates (generated)
│   └── nebula-ca.crt       # Nebula CA certificate
└── generated/               # Generated host certs (ephemeral)
```

## Generating the Nebula CA

The Nebula CA private key is stored in 1Password (Infrastructure vault).
To regenerate the CA:

```bash
# Install nebula-cert
wget https://github.com/slackhq/nebula/releases/download/v1.9.0/nebula-linux-amd64.tar.gz
tar xzf nebula-linux-amd64.tar.gz
sudo mv nebula nebula-cert /usr/local/bin/

# Generate CA (store key in 1Password immediately)
nebula-cert ca -name "LuciVerse Genesis Bond CA" -duration 87600h

# Store in 1Password
op item create --category="Secure Note" \
  --vault="Infrastructure" \
  --title="Nebula-CA-Key" \
  "$(cat nebula-ca.key | base64)"

# Copy CA cert to this directory
cp nebula-ca.crt ~/cluster-bootstrap/nebula/ca/

# Securely delete local key
shred -u nebula-ca.key
```

## Tier-to-Network Mapping

| Tier | Frequency | Nebula Subnet | SCION ISD-AS | Groups |
|------|-----------|---------------|--------------|--------|
| CORE | 432 Hz | 10.100.1.0/24 | 1-ff00:0:432 | core, infrastructure |
| COMN | 528 Hz | 10.100.2.0/24 | 2-ff00:0:528 | comn, gateway |
| PAC | 741 Hz | 10.100.3.0/24 | 3-ff00:0:741 | pac, personal |

## Certificate Distribution Flow

1. Node boots via PXE
2. Kickstart calls `overlay-bootstrap.sh`
3. Script requests attestation token from provision-listener
4. With token, requests Nebula certificate from `/nebula/cert/{mac}`
5. provision-listener signs certificate using CA key from 1Password
6. Certificate returned with tier-appropriate groups

## Security

- Attestation tokens valid for 5 minutes only
- HMAC-SHA256 signed with secret from 1Password
- Rate-limited: max 3 attempts per MAC per 15 minutes
- Rogue MACs are quarantined and trigger security alerts
