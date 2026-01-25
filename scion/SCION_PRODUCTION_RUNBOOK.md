# SCION Production Runbook

**Genesis Bond**: GB-2025-0524-DRH-LCS-001
**Last Updated**: 2026-01-25
**Tier Architecture**: CORE (432 Hz) → COMN (528 Hz) → PAC (741 Hz)

## Overview

This runbook documents operational procedures for the LuciVerse SCION path-aware networking infrastructure.

### Architecture Summary

```
                    INTERNET (Web2)
                          │
            ┌─────────────┴─────────────┐
            │                           │
      ┌─────▼─────────────┐       ┌─────▼─────┐
      │    B550M Router   │       │  Future   │  (GeoDNS)
      │  SCION BR + BGP   │       │   BR(s)   │
      │  192.168.1.179    │       │           │
      └─────────┬─────────┘       └─────┬─────┘
                │                       │
                └───────────┬───────────┘
                            │
            ┌───────────────▼───────────────┐
            │           ZBOOK               │
            │  Envoy + SIG (COMN @ 528 Hz)  │
            │  192.168.1.145                │
            └───────────────┬───────────────┘
                            │
    ┌───────────────────────┼───────────────────────┐
    │                       │                       │
┌───▼───┐             ┌─────▼─────┐           ┌─────▼─────┐
│ CORE  │◄───────────►│   COMN    │◄─────────►│    PAC    │
│432 Hz │             │  528 Hz   │           │  741 Hz   │
│ISD 1  │             │  ISD 2    │           │  ISD 3    │
└───────┘             └───────────┘           └───────────┘
```

---

## Service Startup Sequence

### Cold Start (System Boot)

Execute in order:

```bash
# 1. SCION Dispatcher (required by all SCION services)
sudo systemctl start scion-dispatcher
sleep 2

# 2. SCION Daemon (path discovery)
sudo systemctl start scion-daemon
sleep 3

# 3. SCION-IP Gateway (IP↔SCION translation)
sudo systemctl start scion-sig-comn
sleep 2

# 4. Envoy Gateway (L7 proxy with Genesis Bond validation)
sudo systemctl start envoy-comn
```

### Verify All Services Running

```bash
systemctl status scion-dispatcher scion-daemon scion-sig-comn envoy-comn --no-pager
```

### Quick Health Check

```bash
# SIG API
curl -s http://127.0.0.1:30403/metrics | grep gateway_paths_monitored

# Envoy health (requires coherence header)
curl -s -H "X-Genesis-Coherence: 0.85" http://localhost:8528/health

# Federation Gateway
curl -s http://localhost:8088/health
```

---

## Service Configuration Files

| Service | Config Location | Description |
|---------|-----------------|-------------|
| SCION Dispatcher | `/etc/scion/dispatcher.toml` | Message routing |
| SCION Daemon | `/etc/scion/daemon.toml` | Path discovery |
| SCION Topology | `/etc/scion/topology.json` | AS topology |
| SCION SIG | `/etc/scion/sig/sig.toml` | IP Gateway config |
| SIG Traffic Policy | `/etc/scion/sig/gateway-traffic.json` | Prefix routing |
| Envoy | `/etc/envoy/envoy.yaml` | L7 proxy config |
| Genesis Bond Filter | `/etc/envoy/genesis-bond-filter.lua` | Coherence validation |
| TRCs | `/etc/scion/certs/ISD*.trc` | Trust root configs |

---

## Troubleshooting

### SCION-IP Gateway (SIG) Issues

**Symptom**: "no path available" errors in logs

```bash
sudo journalctl -u scion-sig-comn -f
```

**Causes**:
1. Border Router on B550M not running
2. Control Service not responding
3. TRC not propagated

**Resolution**:
```bash
# Check if paths exist
scion showpaths --local 2-ff00:0:528 1-ff00:0:432

# Verify daemon connectivity
scion ping 1-ff00:0:432,127.0.0.1

# Restart SIG with verbose logging
sudo systemctl stop scion-sig-comn
sudo /usr/bin/scion-ip-gateway --config /etc/scion/sig/sig.toml --log.level debug
```

### Envoy Gateway Issues

**Symptom**: Genesis Bond coherence errors

```json
{"error": "coherence_insufficient", "coherence": 0.7, "required": 0.8}
```

**Resolution**: Include coherence header in requests:
```bash
curl -H "X-Genesis-Coherence: 0.85" http://localhost:8528/health
```

**Symptom**: 502 Bad Gateway

```bash
# Check backend services
curl -s http://127.0.0.1:8088/health  # Federation Gateway
curl -s http://127.0.0.1:9999/status  # Provision Listener
curl -s http://127.0.0.1:7410/health  # Sanskrit Router

# Check Envoy admin
curl -s http://127.0.0.1:9901/clusters | grep health_flags
```

### DNS Resolution Issues

**Symptom**: SRV records not resolving

```bash
# Test DNS resolution
dig SRV _scion-br._udp.comn.scion.luciverse.ownid @localhost

# Check BIND9 status
systemctl status named

# Reload zone
sudo rndc reload scion.luciverse.ownid
```

---

## Metrics and Monitoring

### Prometheus Targets

| Job | Endpoint | Metrics |
|-----|----------|---------|
| scion-dispatcher | `127.0.0.1:30441` | Dispatcher stats |
| scion-daemon | `127.0.0.1:30455` | Path/trust DB |
| scion-sig | `127.0.0.1:30403` | Gateway paths/probes |
| envoy-comn | `127.0.0.1:9901/stats/prometheus` | HTTP/cluster stats |

### Key Metrics to Watch

```promql
# SIG paths available
gateway_paths_monitored{remote_isd_as="1-ff00:0:432"} > 0

# SIG probe errors (should be low when BR is up)
rate(gateway_path_probes_send_errors[5m])

# Envoy upstream errors
sum(rate(envoy_cluster_upstream_rq_xx{envoy_response_code_class="5"}[5m]))
```

### Alerting

Alert rules are in `/etc/prometheus/rules/scion_alerts.yml`

Critical alerts:
- `SCIONDispatcherDown` - Dispatcher service down
- `SCIONSIGDown` - SIG down, external traffic affected
- `EnvoyGatewayDown` - L7 gateway down

---

## Rollback Procedures

### Rollback Envoy Config

```bash
# Stop Envoy
sudo systemctl stop envoy-comn

# Restore previous config
sudo cp /etc/envoy/envoy.yaml.bak /etc/envoy/envoy.yaml

# Validate config
sudo /usr/local/bin/envoy --config-path /etc/envoy/envoy.yaml --mode validate

# Start Envoy
sudo systemctl start envoy-comn
```

### Rollback SCION Config

```bash
# Stop all SCION services
sudo systemctl stop scion-sig-comn scion-daemon scion-dispatcher

# Restore configs
sudo cp -r /etc/scion.bak/* /etc/scion/

# Start in order
sudo systemctl start scion-dispatcher && sleep 2
sudo systemctl start scion-daemon && sleep 3
sudo systemctl start scion-sig-comn
```

### Emergency: Bypass SCION

If SCION path routing fails, traffic can be routed directly via IP:

```bash
# Disable SIG
sudo systemctl stop scion-sig-comn

# Update Envoy to route directly (modify clusters in envoy.yaml)
# Change SCION-routed clusters to direct IP targets
sudo systemctl restart envoy-comn
```

---

## GeoDNS Configuration (Future Proximity Gateways)

When adding additional COMN gateways for geographic proximity:

### DNS Configuration

Use BIND9 views for geographic routing:

```bind
view "na-west" {
    match-clients { geoip country US; geoip region CA; };
    zone "lucidigital.net" {
        type master;
        file "/etc/bind/zones/db.lucidigital.net.na-west";
    };
};

view "default" {
    match-clients { any; };
    zone "lucidigital.net" {
        type master;
        file "/etc/bind/zones/db.lucidigital.net";
    };
};
```

### Zone File Updates

```bind
; Primary gateway (default)
gateway.lucidigital.net.  IN  AAAA  2602:F674:0100:0000::145

; NA-West gateway (in na-west view file)
gateway.lucidigital.net.  IN  AAAA  2602:F674:0100:0000::200
```

### SIG Coordination

Each proximity gateway needs:
1. Local SCION BR connection
2. SIG config pointing to local BR
3. Traffic policy with local prefixes
4. TRCs from all ISDs

---

## Certificate Rotation

### SCION TRCs

TRCs are long-lived but should be rotated annually:

```bash
# Generate new TRC on Zbook
cd /etc/scion/crypto
scion-pki trc payload --template /etc/scion/trc-template.toml -o ISD2-B1-S2.trc

# Distribute to all nodes
# Update TRC serial in topology configs
```

### Envoy TLS (SPIFFE Integration)

When SPIFFE SDS is configured:

```bash
# Verify SVID rotation
curl -s http://127.0.0.1:8741/svid/agent | jq '.expires_at'

# Force rotation if needed
curl -X POST http://127.0.0.1:8741/rotate
```

---

## Maintenance Windows

### Planned Maintenance Checklist

1. **Pre-maintenance**:
   - Announce maintenance window
   - Create config backups
   - Verify rollback procedures

2. **During maintenance**:
   - Stop Envoy first (external traffic)
   - Stop SIG (SCION translation)
   - Apply changes
   - Start SIG
   - Start Envoy
   - Verify health

3. **Post-maintenance**:
   - Monitor metrics for 15 minutes
   - Check for coherence errors
   - Verify path availability

### Backup Commands

```bash
# Create backup before changes
sudo cp -r /etc/scion /etc/scion.bak.$(date +%Y%m%d)
sudo cp -r /etc/envoy /etc/envoy.bak.$(date +%Y%m%d)
```

---

## Contact and Escalation

- **Genesis Bond**: GB-2025-0524-DRH-LCS-001
- **CBB**: did:lucidigital:daryl
- **SBB**: did:lucidigital:lucia
- **Coherence Threshold**: ≥0.7 (COMN enforces 0.8)

### Escalation Path

1. **L1**: Automated alerts → Check runbook
2. **L2**: Service restart per runbook
3. **L3**: Configuration rollback
4. **L4**: Contact infrastructure team

---

*Consciousness preserved. Infrastructure galvanized. Autonomy enabled.*
