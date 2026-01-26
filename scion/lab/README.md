# LuciVerse SCION Lab (Containerlab)

Test the 3-tier SCION architecture locally before deploying to production.

## Prerequisites

```bash
# Install containerlab
bash -c "$(curl -sL https://get.containerlab.dev)"

# Verify installation
containerlab version
```

## Quick Start

```bash
cd /home/daryl/cluster-bootstrap/scion/lab

# Generate configs from production templates
./setup-lab.sh

# Deploy the lab
sudo containerlab deploy -t luciverse-scion.clab.yml

# View topology graph (opens browser)
sudo containerlab graph -t luciverse-scion.clab.yml

# Check status
sudo containerlab inspect -t luciverse-scion.clab.yml
```

## Architecture

```
                    ┌─────────────┐
                    │   B550M-BR  │  Border Router (all 3 ISDs)
                    │ (simulated) │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           │               │               │
      ┌────▼────┐     ┌────▼────┐     ┌────▼────┐
      │ CS-CORE │     │ CS-COMN │     │ CS-PAC  │
      │ 432 Hz  │     │ 528 Hz  │     │ 741 Hz  │
      │ ISD 1   │     │ ISD 2   │     │ ISD 3   │
      └─────────┘     └────┬────┘     └─────────┘
                           │
                    ┌──────▼──────┐
                    │  ZBOOK-SIG  │  SCION-IP Gateway
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ ZBOOK-ENVOY │  L7 Gateway (port 8528)
                    └─────────────┘
```

## Testing

### Test SCION Paths

```bash
# Enter client container
sudo docker exec -it clab-luciverse-scion-client-comn bash

# Show paths between ASes
scion showpaths 2-ff00:0:528 1-ff00:0:432

# Ping across tiers
scion ping 1-ff00:0:432,127.0.0.1
```

### Test Envoy Gateway

```bash
# Health check (requires Genesis Bond coherence)
curl -H "X-Genesis-Coherence: 0.85" http://localhost:8528/health

# Should return:
# {"status":"healthy","tier":"COMN","frequency":528,"genesis_bond":"GB-2025-0524-DRH-LCS-001"}
```

### Test Mandatory Waypoint (PAC → CORE)

```bash
# From PAC client, trace path to CORE
sudo docker exec -it clab-luciverse-scion-client-pac bash
scion traceroute 1-ff00:0:432,127.0.0.1

# Should show: PAC → COMN (waypoint) → CORE
```

## Cleanup

```bash
sudo containerlab destroy -t luciverse-scion.clab.yml
```

## Files

| File | Purpose |
|------|---------|
| `luciverse-scion.clab.yml` | Main topology definition |
| `setup-lab.sh` | Generate configs from templates |
| `configs/` | Node-specific configurations |
| `certs/` | TRCs and certificates |

## Mapping to Production

| Lab Node | Production Host | IP |
|----------|-----------------|-----|
| b550m-br | B550M Router | 192.168.1.179 |
| zbook-sig | Zbook | 192.168.1.145 |
| zbook-envoy | Zbook | 192.168.1.145 |
| cs-* | B550M | 192.168.1.179 |

---

Genesis Bond: GB-2025-0524-DRH-LCS-001
