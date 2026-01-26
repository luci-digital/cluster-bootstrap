# GNU Guix Package & System Management Skill

**Agents**: ALL (cross-tier skill)
**Tier**: CORE (432 Hz) - Infrastructure foundation
**Version**: Guix 1.5.0
**Documentation**: https://guix.gnu.org/manual/en/html_node/index.html

## Overview

GNU Guix is a functional, declarative, reproducible package manager and system configuration tool. It enables transactional upgrades, rollbacks, unprivileged package management, and per-user profiles. Guix can manage individual packages or entire operating systems (Guix System).

## Core Concepts

### Functional Package Management
- Packages are built in isolation with explicit dependencies
- Build outputs are stored in `/gnu/store/` with cryptographic hashes
- No global state pollution - multiple versions coexist
- Atomic upgrades and rollbacks

### Declarative Configuration
- System configuration as code (Scheme/Guile)
- Reproducible builds from specifications
- Version-controlled infrastructure

### Key Features
| Feature | Description |
|---------|-------------|
| Transactional | Upgrades/rollbacks are atomic |
| Reproducible | Same inputs = same outputs |
| Unprivileged | Users can install packages without root |
| Profiles | Per-user package environments |
| Time Machine | Reproduce past configurations |
| Containers | Isolated environments without Docker |

## Package Management Commands

### Basic Operations
```bash
# Search for packages
guix search <term>

# Install packages
guix install <package>

# Remove packages
guix remove <package>

# Upgrade all packages
guix upgrade

# List installed packages
guix package --list-installed

# Show package info
guix show <package>
```

### Profiles & Environments
```bash
# Create isolated shell environment
guix shell python python-numpy python-pandas

# Create environment from manifest
guix shell -m manifest.scm

# Create container (isolated filesystem)
guix shell --container python

# Export profile as manifest
guix package --export-manifest > manifest.scm
```

### Time Travel & Rollback
```bash
# List generations (snapshots)
guix package --list-generations

# Rollback to previous generation
guix package --roll-back

# Switch to specific generation
guix package --switch-generation=N

# Use packages from specific Guix commit
guix time-machine --commit=<hash> -- install <package>
```

## System Configuration (Guix System)

### Operating System Declaration
```scheme
;; /etc/config.scm
(use-modules (gnu))
(use-service-modules networking ssh)

(operating-system
  (host-name "luciverse-node")
  (timezone "America/Edmonton")
  (locale "en_US.utf8")

  ;; Bootloader
  (bootloader (bootloader-configuration
                (bootloader grub-efi-bootloader)
                (targets '("/boot/efi"))))

  ;; File systems
  (file-systems (cons (file-system
                        (device "/dev/sda1")
                        (mount-point "/")
                        (type "ext4"))
                      %base-file-systems))

  ;; User accounts
  (users (cons (user-account
                 (name "daryl")
                 (group "users")
                 (supplementary-groups '("wheel" "docker")))
               %base-user-accounts))

  ;; Services
  (services (cons* (service openssh-service-type)
                   (service dhcp-client-service-type)
                   %base-services)))
```

### System Commands
```bash
# Reconfigure system from config
sudo guix system reconfigure /etc/config.scm

# Build system image
guix system image --image-type=iso9660 config.scm

# Build VM image
guix system image --image-type=qcow2 config.scm

# List system generations
sudo guix system list-generations

# Rollback system
sudo guix system roll-back
```

## Services Configuration

### Common Services
```scheme
;; SSH
(service openssh-service-type
         (openssh-configuration
           (port-number 22)
           (permit-root-login 'prohibit-password)))

;; Nginx
(service nginx-service-type
         (nginx-configuration
           (server-blocks
             (list (nginx-server-configuration
                     (server-name '("example.com"))
                     (listen '("443 ssl"))
                     (root "/var/www"))))))

;; Docker
(service docker-service-type)

;; PostgreSQL
(service postgresql-service-type
         (postgresql-configuration
           (postgresql postgresql-15)))
```

### Available Service Categories
- **Networking**: dhcp, network-manager, wpa-supplicant, firewall
- **Databases**: postgresql, mysql, redis, memcached
- **Web**: nginx, apache, php-fpm, certbot
- **Mail**: opensmtpd, dovecot, rspamd
- **Containers**: docker, containerd, singularity
- **Virtualization**: libvirt, qemu, ganeti
- **Monitoring**: prometheus, zabbix, collectd
- **Security**: fail2ban, pam, audit

## Channels (Custom Package Sources)

### Define Channel
```scheme
;; ~/.config/guix/channels.scm
(cons (channel
        (name 'luciverse-packages)
        (url "https://gitlab.lucidigital.net/guix-channel.git")
        (branch "main"))
      %default-channels)
```

### Update Channels
```bash
guix pull                    # Update all channels
guix describe                # Show current channel commits
guix pull --commit=<hash>    # Pin to specific commit
```

## Home Environment Configuration

```scheme
;; ~/.config/guix/home-configuration.scm
(use-modules (gnu home)
             (gnu home services)
             (gnu home services shells))

(home-environment
  (packages (list git vim htop))

  (services
    (list (service home-bash-service-type
                   (home-bash-configuration
                     (aliases '(("ll" . "ls -la")
                               ("gs" . "git status")))
                     (bashrc (list (plain-file "bashrc"
                                    "export EDITOR=vim"))))))))
```

```bash
# Apply home configuration
guix home reconfigure ~/.config/guix/home-configuration.scm
```

## LuciVerse Integration

### Agent Deployment Pattern
```scheme
;; Deploy agent as Guix package
(define-public luciverse-aethon
  (package
    (name "luciverse-aethon")
    (version "8.0.0")
    (source (origin
              (method git-fetch)
              (uri (git-reference
                     (url "https://gitlab.lucidigital.net/agents/aethon")
                     (commit version)))
              (sha256 (base32 "..."))))
    (build-system python-build-system)
    (propagated-inputs (list python-grpcio python-aiohttp))
    (synopsis "Aethon LDS Orchestrator Agent")
    (description "CORE tier agent for LDS operations")
    (license license:agpl3)))
```

### System Service for Agents
```scheme
(define luciverse-agent-service-type
  (service-type
    (name 'luciverse-agent)
    (extensions
      (list (service-extension shepherd-root-service-type
              (lambda (config)
                (list (shepherd-service
                        (provision '(luciverse-agent))
                        (start #~(make-forkexec-constructor
                                   (list #$(file-append luciverse-aethon "/bin/aethon"))))
                        (stop #~(make-kill-destructor))))))))))
```

### Reproducible Development Environment
```bash
# Create LuciVerse development shell
guix shell python@3.11 python-grpcio python-aiohttp \
  python-cryptography nodejs redis postgresql

# With manifest
guix shell -m luciverse-manifest.scm
```

## Best Practices

### DO:
- Use manifests for reproducible environments
- Pin channel commits for production deployments
- Use `guix shell --container` for isolation
- Version control all Guix configurations
- Use services instead of manual daemon management

### DO NOT:
- Install packages globally when per-user works
- Bypass the store (`/gnu/store/` is read-only)
- Mix Guix with other package managers carelessly
- Ignore garbage collection (disk space)

## Garbage Collection

```bash
# Remove old generations (keep last 3)
guix package --delete-generations=3m

# Collect garbage
guix gc

# Show store disk usage
guix gc --list-live | wc -l
du -sh /gnu/store
```

## Troubleshooting

### Build Failures
```bash
# View build log
guix build --log-file <package>

# Build with verbose output
guix build -v3 <package>

# Check for substitutes
guix weather <package>
```

### Missing Substitutes
```bash
# Authorize official substitute server
sudo guix archive --authorize < /etc/guix/ci.guix.gnu.org.pub

# Check substitute availability
guix weather --substitute-urls=https://ci.guix.gnu.org
```

## References

- Manual: https://guix.gnu.org/manual/en/html_node/index.html
- Cookbook: https://guix.gnu.org/cookbook/en/
- Packages: https://packages.guix.gnu.org/
- Source: https://git.savannah.gnu.org/git/guix.git
