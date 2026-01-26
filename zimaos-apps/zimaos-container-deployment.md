# ZimaOS Container Deployment Skill

**Agent**: Diaphragm, Lyr Darrah
**Tier**: PAC (741 Hz)
**Target**: ZimaCube / ZimaOS 3.x
**Documentation Source**: `/home/daryl/Downloads/zima_cli/`

## Overview

ZimaOS is a NAS-focused operating system with Docker container support. This skill enables automated container app deployment on ZimaOS devices.

## ZimaOS Network Discovery

| Host | IP | Ports | Purpose |
|------|-----|-------|---------|
| ZimaCube-Primary | 192.168.1.152 | 22, 80, 2222, 8080 | Main intake node |
| ZimaCube-Secondary | 192.168.1.200 | 22 | Backup node |

## SSH Access

### Authentication
- **User**: `daryl`
- **Home Directory**: `/DATA` (not `/home/daryl`)
- **Group**: `samba` (not `daryl`)
- **SSH Keys**: `/DATA/.ssh/authorized_keys`

### Connection Command
```bash
ssh daryl@192.168.1.152
```

### Key Setup (if needed)
```bash
# On ZimaOS via web terminal (http://192.168.1.152:2222/)
sudo mkdir -p /DATA/.ssh
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMFXwJ3PuR0lWe25HwdhG+dykqJMiLhafJZvWhTcThy1 daryl@openeuler-atune" | sudo tee /DATA/.ssh/authorized_keys
sudo chmod 700 /DATA/.ssh
sudo chmod 600 /DATA/.ssh/authorized_keys
sudo chown -R daryl:samba /DATA/.ssh
```

## CLI Access Methods

### Method 1: SSH Client
```bash
ssh root@<zimaos-ip>
# or
ssh daryl@<zimaos-ip>
```

### Method 2: Web Terminal (ttydBridge)
- URL: `http://192.168.1.152:2222/`
- Default credentials: `admin` / `password`

### Method 3: Direct Console
- Press `Alt+F2` at boot screen
- Login as `root` (first time: no password)
- Set password: `passwd root`

## File System Structure

### Read-Only Directories
Most system folders are read-only even as root for safety.

### Writable Data Directory
```
/DATA/
├── .docker/              # Docker config (fix permissions if issues)
├── .ssh/                 # SSH keys
├── luciverse/            # LuciVerse app data
│   ├── dropzone/         # Copyparty uploads
│   ├── processed/        # Processed content
│   ├── redis/            # Redis data
│   └── obsidian-vault/   # Knowledge vault
├── AppData/              # App Store app data
└── Media/                # Media files
```

## Docker on ZimaOS

### Docker Config Permission Fix
```bash
sudo chmod 755 /DATA/.docker
sudo chmod 666 /DATA/.docker/config.json
sudo chown daryl:samba /DATA/.docker/config.json
```

### Check Running Containers
```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

### Docker Compose (ZimaOS uses plugin syntax)
```bash
# ZimaOS may not have docker-compose binary
# Use docker run instead for manual deployment
```

### Manual Container Deployment
```bash
docker run -d \
  --name <container-name> \
  --restart unless-stopped \
  -p <host-port>:<container-port> \
  -v /DATA/<path>:/container/path \
  <image>:<tag>
```

## App Adaptation Guide

### Difficulty Levels

| Type | Difficulty | Description |
|------|------------|-------------|
| Docker Self-Deploy | 🌟 | Apps with official Docker images (LocalAI, OpenWebUI, Nextcloud) |
| PC Self-Deploy | 🌟🌟🌟 | Apps with WebUI but no Docker image (stable-diffusion-webui) |
| Cloud Service | 🌟🌟🌟🌟🌟 | Multi-container apps (Dify, TaskingAI) - complex compose files |

### ZimaOS App Store Format

Apps use docker-compose.yaml with ZimaOS-specific annotations:

```yaml
# Example: docker-compose.yaml for ZimaOS
version: '3.8'
services:
  app:
    image: myapp:latest
    ports:
      - "8080:8080"
    volumes:
      - /DATA/AppData/myapp:/data
    environment:
      - ENV_VAR=value
    restart: unless-stopped

# ZimaOS metadata (optional)
x-casaos:
  title: "My App"
  description: "App description"
  icon: "https://example.com/icon.png"
  category: "Utility"
```

### Environment Variables
- Store in `/etc/casaos/env`
- Reference with `$VAR` (single `$`) in compose files
- Use `$$VAR` for literal `$` in container

### Networking
- Use `host.docker.internal` to reach host services
- Use `localhost` for container-internal services
- Add `extra_hosts` for custom DNS

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

## LuciVerse Diaphragm Stack

### Deployment Commands
```bash
# Create directories
ssh daryl@192.168.1.152 "mkdir -p /DATA/luciverse/{dropzone,processed,redis,obsidian-vault}"

# Deploy Copyparty dropzone
ssh daryl@192.168.1.152 'docker run -d \
  --name luciverse-dropzone \
  --restart unless-stopped \
  -p 3923:3923 \
  -v /DATA/luciverse/dropzone:/w/dropzone \
  -v /DATA/luciverse/processed:/w/processed \
  ghcr.io/9001/copyparty:latest \
  -v /w/dropzone:dropzone:rw:a -v /w/processed:processed:r'

# Deploy Redis
ssh daryl@192.168.1.152 'docker run -d \
  --name luciverse-redis \
  --restart unless-stopped \
  -v /DATA/luciverse/redis:/data \
  redis:7-alpine'

# Deploy Nginx for Obsidian vault
ssh daryl@192.168.1.152 'docker run -d \
  --name luciverse-explorer \
  --restart unless-stopped \
  -p 8528:80 \
  -v /DATA/luciverse/obsidian-vault:/usr/share/nginx/html:ro \
  nginx:alpine'
```

### Verify Deployment
```bash
ssh daryl@192.168.1.152 'docker ps --filter "name=luciverse"'
```

## Deeplinks

### ZimaOS Web UI
- Dashboard: `http://192.168.1.152/`
- App Store: `http://192.168.1.152/#/app-store`
- Files: `http://192.168.1.152/#/files`
- Settings: `http://192.168.1.152/#/settings`

### Web Terminal
- ttyd: `http://192.168.1.152:2222/`

### LuciVerse Apps (after deployment)
- Dropzone: `http://192.168.1.152:3923/`
- LDS Explorer: `http://192.168.1.152:8528/`

### Existing Apps on ZimaCube
- Gitea: `http://192.168.1.152:3000/`
- Grafana: `http://192.168.1.152:3001/`
- LibreChat: `http://192.168.1.152:3080/`
- RAGFlow: `http://192.168.1.152:9380/`
- Obsidian: `http://192.168.1.152:8686/`
- Home Assistant: `http://192.168.1.152:8123/`
- Ollama API: `http://192.168.1.152:11434/`
- Open WebUI: `http://192.168.1.152:8080/`
- Flowise: `http://192.168.1.152:3002/`

## Troubleshooting

### Docker Permission Denied
```bash
# Fix docker config
sudo chmod 777 /DATA/.docker
sudo chmod 666 /DATA/.docker/config.json
```

### SSH Key Not Working
```bash
# Verify key exists and permissions
ls -la /DATA/.ssh/
cat /DATA/.ssh/authorized_keys

# Fix permissions
sudo chmod 700 /DATA/.ssh
sudo chmod 600 /DATA/.ssh/authorized_keys
sudo chown -R daryl:samba /DATA/.ssh
```

### Container Pull Failed
```bash
# Check docker daemon
sudo systemctl status docker

# Try manual pull
docker pull <image>
```

## Common Commands

| Command | Description |
|---------|-------------|
| `docker ps` | List running containers |
| `docker logs <name>` | View container logs |
| `docker exec -it <name> sh` | Shell into container |
| `docker stop <name>` | Stop container |
| `docker rm <name>` | Remove container |
| `docker images` | List images |
| `docker volume ls` | List volumes |
| `df -h /DATA` | Check disk space |
| `free -h` | Check memory |

## References

- ZimaOS Docs: https://www.zimaspace.com/docs/zimaos/
- CLI Guide: https://www.zimaspace.com/docs/zimaos/Sync-Photos-via-Configurable-CLI
- Build Apps: https://www.zimaspace.com/docs/zimaos/Build-Apps
- SSH Settings: https://www.zimaspace.com/docs/zimaos/SSH-Setting
- Docker Paths: https://www.zimaspace.com/docs/zimaos/Docker-Apps-paths
