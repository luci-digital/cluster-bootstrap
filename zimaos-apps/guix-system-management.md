# Guix System Management Rules

**Agents**: ALL agents across all tiers
**Tier**: Cross-tier (CORE/COMN/PAC)
**Priority**: Infrastructure foundation skill

## Required Skills

- `~/.claude/skills/trending-2026-01/core/guix-package-system.md`

## When to Use Guix

### Prefer Guix Over Traditional Package Managers When:

1. **Reproducibility required** - Need exact same environment across systems
2. **Rollback needed** - Must be able to undo changes atomically
3. **Isolation required** - Need containerized environments without Docker
4. **Multi-version coexistence** - Need different versions of same package
5. **Declarative config** - Want infrastructure as code

### Use Cases by Tier

| Tier | Use Case |
|------|----------|
| CORE | System provisioning, service deployment, infrastructure packages |
| COMN | Development environments, build reproducibility, CI/CD |
| PAC | User home environments, application isolation, personal tools |

## Deployment Rules

### DO:
- Use `guix shell` for temporary development environments
- Use `guix home` for user-level configuration
- Use `guix system` for full OS management
- Pin channels to specific commits for production
- Store manifests and configs in git repositories
- Use containers (`--container`) for untrusted code

### DO NOT:
- Mix Guix packages with system packages unnecessarily
- Forget to run `guix gc` periodically (disk space)
- Use root when user-level installation works
- Skip substitutes (use ci.guix.gnu.org for faster builds)

## Integration Patterns

### With Existing Systems (openEuler/NixOS)
```bash
# Install Guix on foreign distro
wget https://git.savannah.gnu.org/cgit/guix.git/plain/etc/guix-install.sh
chmod +x guix-install.sh && sudo ./guix-install.sh
```

### With Docker/Containers
```bash
# Create OCI image from Guix pack
guix pack -f docker -S /bin=bin python python-numpy

# Run Guix environment in existing container
guix shell --container --network --share=/data python
```

### With LuciVerse Agents
- Agents can request Guix environments via manifest
- State Guardian tracks Guix generations
- Aethon can provision Guix systems via PXE

## Common Commands Reference

| Task | Command |
|------|---------|
| Search packages | `guix search <term>` |
| Install package | `guix install <pkg>` |
| Create shell env | `guix shell <pkgs...>` |
| Rollback | `guix package --roll-back` |
| Update system | `sudo guix system reconfigure config.scm` |
| Garbage collect | `guix gc` |
| Time travel | `guix time-machine --commit=X -- shell` |

## Documentation

- Full manual: https://guix.gnu.org/manual/en/html_node/index.html
- Cookbook: https://guix.gnu.org/cookbook/en/
- Package search: https://packages.guix.gnu.org/
