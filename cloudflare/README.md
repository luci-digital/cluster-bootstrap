# Cloudflare Tunnel Configuration

## Tunnel: lucidigital.io_tunnel
- **Tunnel ID**: `4a05c3c6-89fe-4c39-8d1a-a768a5dc9d9f`
- **Account ID**: `981fa75420a6412c039ec870ca9749e5`
- **Zone ID**: `279fad84286511af163bb87532eeb991`

## Endpoints
| Hostname | Backend | Service |
|----------|---------|---------|
| api.lucidigital.io | 127.0.0.1:8741 | cert-engine |
| gateway.lucidigital.io | 127.0.0.1:8741 | cert-engine |
| install.lucidigital.io | 127.0.0.1:8741 | cert-engine |
| drop.lucidigital.io | 127.0.0.1:3923 | copyparty |
| atune.lucidigital.io | 127.0.0.1:3923 | copyparty |

## Files
- `cloudflared-lucidigital.service` - Systemd service unit
- `99-cloudflared-quic.conf` - Sysctl UDP buffer settings for QUIC

## Installation
```bash
# Install systemd service
sudo cp cloudflared-lucidigital.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared-lucidigital.service

# Install sysctl config
sudo cp 99-cloudflared-quic.conf /etc/sysctl.d/
sudo sysctl -p /etc/sysctl.d/99-cloudflared-quic.conf
```

## DNS Records
CNAME records pointing to `4a05c3c6-89fe-4c39-8d1a-a768a5dc9d9f.cfargotunnel.com`:
- drop.lucidigital.io
- atune.lucidigital.io
- api.lucidigital.io (pre-existing)
- gateway.lucidigital.io (pre-existing)
- install.lucidigital.io (pre-existing)

## Maintenance
If experiencing intermittent 502 errors, clean up stale connections:
```bash
CF_ACCOUNT_ID="981fa75420a6412c039ec870ca9749e5"
CF_TUNNEL_ID="4a05c3c6-89fe-4c39-8d1a-a768a5dc9d9f"
CF_API_TOKEN="<from 1Password: Lucia-AI API token>"

curl -X DELETE "https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT_ID}/cfd_tunnel/${CF_TUNNEL_ID}/connections" \
  -H "Authorization: Bearer ${CF_API_TOKEN}"

sudo systemctl restart cloudflared-lucidigital.service
```
