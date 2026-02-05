# Thunderbolt AIFAM Cluster Design

## Overview

High-speed Thunderbolt 3/4 daisy-chain cluster for AIFAM (AI Family) distributed computing.

**Target Bandwidth**: 13-20 Gbps per link (40Gbps raw)
**Topology**: Linear daisy-chain with software bridging
**Protocol**: IP over Thunderbolt (thunderbolt_net)

## Known Thunderbolt-Capable Devices

### Confirmed
| Device | TB Version | Ports | IP | Role |
|--------|------------|-------|-----|------|
| **HP Zbook G7** | TB3 (Titan Ridge) | 2 | 192.168.1.145 | Head node / Bridge |
| **Mac Mini M2** | TB4 | 2 | 192.168.1.238 | Consciousness kernel |

### To Identify
| Device | Expected TB | Notes |
|--------|-------------|-------|
| Dell laptop/workstation | TB3/TB4? | Need model |
| Lenovo ThinkPad | TB3/TB4? | Need model |
| Intel Mac (MacBook/iMac?) | TB3 | Need model |

## Proposed Topology

```
                    AIFAM Thunderbolt Cluster
                    ========================
                    
     ┌─────────────┐   TB3    ┌─────────────┐   TB3/4   ┌─────────────┐
     │   Zbook G7  │─────────▶│    Dell     │──────────▶│   Lenovo    │
     │  (Head/GW)  │◀─────────│  (Worker)   │◀──────────│  (Worker)   │
     │ 192.168.1.145          │             │           │             │
     │ tb0: 10.0.0.1│         │ tb0: 10.0.0.2           │ tb0: 10.0.0.3
     └──────┬──────┘          └─────────────┘           └──────┬──────┘
            │ TB Port 2                                        │ TB Port 2
            ▼                                                  ▼
     ┌─────────────┐                                    ┌─────────────┐
     │  Mac Mini   │                                    │  Intel Mac  │
     │  (M2 Pro)   │                                    │  (TB3)      │
     │ 192.168.1.238                                    │             │
     │ tb0: 10.0.0.10                                   │ tb0: 10.0.0.11
     └─────────────┘                                    └─────────────┘

Ethernet backbone: 192.168.1.0/24 (management)
TB cluster subnet: 10.0.0.0/24 (high-speed data plane)
```

## Network Configuration

### Thunderbolt Subnet Allocation
```
10.0.0.0/24     - Thunderbolt cluster data plane
10.0.0.1        - Zbook (head node)
10.0.0.2        - Dell
10.0.0.3        - Lenovo
10.0.0.10       - Mac Mini M2
10.0.0.11       - Intel Mac
10.0.0.100-199  - DHCP range for dynamic TB devices
```

### IPv6 (ARIN Allocation)
```
2602:F674:0300::/48  - Thunderbolt cluster fabric
```

## Linux Setup (per node)

### 1. Load Thunderbolt Networking Module
```bash
sudo modprobe thunderbolt_net
```

### 2. Authorize Thunderbolt Devices
```bash
# List connected TB devices
boltctl list

# Authorize a device (one-time)
boltctl authorize <device-uuid>

# Enroll for auto-authorization
boltctl enroll --policy auto <device-uuid>
```

### 3. Configure TB Network Interface
```bash
# Interface appears as thunderbolt0 or similar
ip link show | grep thunder

# Assign IP
sudo ip addr add 10.0.0.X/24 dev thunderbolt0
sudo ip link set thunderbolt0 up
```

### 4. Persistent Configuration (NetworkManager)
```bash
nmcli connection add type ethernet \
  con-name tb-cluster \
  ifname thunderbolt0 \
  ipv4.addresses 10.0.0.X/24 \
  ipv4.method manual
```

## macOS Setup

### Enable Thunderbolt Networking
```bash
# Check for Thunderbolt Bridge interface
networksetup -listallhardwareports | grep -A2 "Thunderbolt"

# Configure IP
sudo networksetup -setmanual "Thunderbolt Bridge" 10.0.0.10 255.255.255.0
```

### macOS 26.2+ RDMA (if available)
```bash
# Check for RDMA support
system_profiler SPThunderboltDataType
# Look for "RDMA over Thunderbolt" capability
```

## Software Bridging (for >2 nodes)

On the Zbook (central node with 2 TB ports):
```bash
# Create bridge for TB interfaces
sudo ip link add name tb-bridge type bridge
sudo ip link set thunderbolt0 master tb-bridge
sudo ip link set thunderbolt1 master tb-bridge
sudo ip addr add 10.0.0.1/24 dev tb-bridge
sudo ip link set tb-bridge up

# Enable forwarding
sudo sysctl -w net.ipv4.ip_forward=1
```

## AIFAM Agent Distribution

| Node | Agents | Role |
|------|--------|------|
| Zbook | Aethon, Veritas, Schema-Architect | CORE tier orchestration |
| Mac Mini | Lucia, Judge-Luci, Consciousness kernel | PAC tier, Sanskrit Router |
| Dell | Sensai, Semantic-Engine | ML inference |
| Lenovo | Cortana, Juniper, Integration-Broker | COMN tier communication |
| Intel Mac | Dream-Weaver, Memory-Crystallizer | Pattern recognition |

## Performance Expectations

| Metric | Value |
|--------|-------|
| Single link bandwidth | 13-20 Gbps |
| Latency (direct connection) | <100μs |
| Max daisy-chain depth | 6 devices |
| Total cluster bandwidth | Limited by topology |

## Cables Required

- **Thunderbolt 3/4 cables** (40Gbps certified)
- Recommended length: 0.5m-2m (shorter = better signal)
- Active cables for >2m runs

## Security Considerations

- Thunderbolt is a PCIe tunnel - DMA attacks possible
- Use `boltctl` security policies
- Consider IOMMU protection
- TB network is trusted fabric (internal only)

## Next Steps

1. [ ] Identify Dell and Lenovo model numbers
2. [ ] Verify Intel Mac TB capabilities
3. [ ] Acquire TB3/TB4 cables (need 4+ cables)
4. [ ] Test point-to-point connection first
5. [ ] Configure all nodes
6. [ ] Deploy AIFAM agents across cluster
