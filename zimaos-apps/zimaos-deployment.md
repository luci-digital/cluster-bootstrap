# ZimaOS Deployment Rules

**Agents**: Diaphragm, Lyr Darrah Hologrammer
**Tier**: PAC (741 Hz)
**Targets**: ZimaCube-Primary (192.168.1.152), ZimaCube-Secondary (192.168.1.200)

## Required Skills

- `~/.claude/skills/trending-2026-01/pac/zimaos-container-deployment.md`

## Pre-Deployment Checklist

### 1. Verify SSH Access
```bash
ssh -o BatchMode=yes daryl@192.168.1.152 "hostname"
```

### 2. Check Docker Config Permissions
```bash
ssh daryl@192.168.1.152 "ls -la /DATA/.docker/config.json"
```
If permission denied, fix via web terminal (http://192.168.1.152:7681/):
```bash
sudo chmod 755 /DATA/.docker
sudo chmod 666 /DATA/.docker/config.json
```

### 3. Verify Disk Space
```bash
ssh daryl@192.168.1.152 "df -h /DATA"
```
Minimum: 10GB free for new deployments

## Deployment Rules

### DO:
- Use `/DATA/` for all persistent storage
- Use `daryl:samba` for file ownership
- Use `docker run` for single containers (no docker-compose binary)
- Create data directories before deployment
- Test SSH access before attempting deployment
- Use web terminal fallback if SSH fails

### DO NOT:
- Assume `/home/daryl` exists (home is `/DATA`)
- Use `daryl:daryl` group (group is `samba`)
- Attempt sudo over SSH without TTY
- Modify system directories (read-only)
- Use docker-compose commands (use docker run)

## Standard Deployment Pattern

```bash
# 1. Create data directory
ssh daryl@192.168.1.152 "mkdir -p /DATA/<app-name>"

# 2. Deploy container
ssh daryl@192.168.1.152 'docker run -d \
  --name <app-name> \
  --restart unless-stopped \
  -p <port>:<port> \
  -v /DATA/<app-name>:/data \
  <image>:<tag>'

# 3. Verify
ssh daryl@192.168.1.152 'docker ps --filter "name=<app-name>"'
```

## Error Recovery

### SSH Permission Denied
1. Open web terminal: http://192.168.1.152:7681/
2. Fix SSH keys:
```bash
sudo mkdir -p /DATA/.ssh
echo "<public-key>" | sudo tee /DATA/.ssh/authorized_keys
sudo chmod 700 /DATA/.ssh && sudo chmod 600 /DATA/.ssh/authorized_keys
sudo chown -R daryl:samba /DATA/.ssh
```

### Docker Pull Denied
1. Check docker config: `cat /DATA/.docker/config.json`
2. Fix permissions: `sudo chmod 666 /DATA/.docker/config.json`
3. Retry pull

### Container Won't Start
1. Check logs: `docker logs <name>`
2. Check ports: `docker ps -a`
3. Remove and recreate: `docker rm <name> && docker run ...`

## LuciVerse Stack Ports

| Service | Port | Container Name |
|---------|------|----------------|
| Dropzone (Copyparty) | 3923 | luciverse-dropzone |
| LDS Explorer | 8528 | luciverse-explorer |
| Redis | 6379 | luciverse-redis |
