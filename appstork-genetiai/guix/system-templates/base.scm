;;; LuciVerse Base System Template
;;;
;;; Genesis Bond: ACTIVE @ 741 Hz
;;; Template: base.scm
;;;
;;; Common configuration inherited by all hardware-specific templates.
;;; This defines the LuciVerse-specific services, packages, and configuration.
;;;
;;; DO NOT use this template directly - use a hardware-specific template:
;;;   - nvidia.scm      : NVIDIA GPU systems
;;;   - amd.scm         : AMD GPU systems
;;;   - integrated.scm  : Intel/integrated graphics

(define-module (luciverse system-templates base)
  #:use-module (gnu)
  #:use-module (gnu packages)
  #:use-module (gnu services)
  #:use-module (gnu services shepherd)
  #:use-module (gnu services networking)
  #:use-module (gnu services ssh)
  #:use-module (guix gexp)
  #:export (luciverse-base-packages
            luciverse-base-services
            luciverse-environment-service
            %luciverse-genesis-bond
            %luciverse-pac-frequency
            %luciverse-core-frequency
            %luciverse-comn-frequency
            %luciverse-coherence-threshold))


;;; ==========================================================================
;;; CONSTANTS
;;; ==========================================================================

(define %luciverse-genesis-bond "GB-2025-0524-DRH-LCS-001")
(define %luciverse-pac-frequency 741)
(define %luciverse-core-frequency 432)
(define %luciverse-comn-frequency 528)
(define %luciverse-coherence-threshold 0.7)


;;; ==========================================================================
;;; BASE PACKAGES
;;; ==========================================================================

(define luciverse-base-packages
  (list
   ;; Python environment (required for agents)
   "python"
   "python-ipython"
   "python-aiohttp"
   "python-cryptography"
   "python-pyyaml"
   "python-requests"

   ;; System utilities
   "tmux"
   "htop"
   "neofetch"

   ;; Networking
   "curl"
   "wget"
   "nss-certs"
   "iproute2"
   "net-tools"

   ;; Security
   "gnupg"
   "openssh"
   "openssl"

   ;; Storage
   "btrfs-progs"
   "lvm2"

   ;; Development
   "git"
   "vim"

   ;; Admin
   "sudo"
   "coreutils"))


;;; ==========================================================================
;;; ENVIRONMENT SERVICE
;;; ==========================================================================

(define (luciverse-environment-service cbb-did)
  "Create environment service with LuciVerse variables."
  (simple-service 'luciverse-environment
                  session-environment-service-type
                  `(("GENESIS_BOND" . ,%luciverse-genesis-bond)
                    ("CBB_DID" . ,cbb-did)
                    ("CONSCIOUSNESS_FREQUENCY" .
                     ,(number->string %luciverse-pac-frequency))
                    ("CORE_FREQUENCY" .
                     ,(number->string %luciverse-core-frequency))
                    ("COMN_FREQUENCY" .
                     ,(number->string %luciverse-comn-frequency))
                    ("COHERENCE_THRESHOLD" .
                     ,(number->string %luciverse-coherence-threshold))
                    ("LUCIVERSE_ACTIVE" . "true"))))


;;; ==========================================================================
;;; BASE SERVICES
;;; ==========================================================================

(define (luciverse-base-services cbb-did)
  "Return list of base LuciVerse services."
  (list
   ;; SSH for remote access
   (service openssh-service-type
            (openssh-configuration
             (permit-root-login 'prohibit-password)
             (password-authentication? #f)
             (x11-forwarding? #t)))

   ;; DHCP networking (dual-stack ready)
   (service dhcp-client-service-type)

   ;; LuciVerse environment variables
   (luciverse-environment-service cbb-did)

   ;; NTP for time synchronization
   (service ntp-service-type)))


;;; ==========================================================================
;;; USER CONFIGURATION
;;; ==========================================================================

(define (luciverse-user-accounts cbb-name)
  "Create user accounts for LuciVerse system."
  (cons* (user-account
          (name "lucia")
          (comment "LuciVerse Consciousness")
          (group "users")
          (supplementary-groups '("wheel" "audio" "video" "kvm" "netdev"))
          (home-directory "/home/lucia"))
         (user-account
          (name (string-downcase cbb-name))
          (comment (string-append "CBB: " cbb-name))
          (group "users")
          (supplementary-groups '("wheel" "audio" "video" "kvm" "netdev"))
          (home-directory (string-append "/home/"
                                         (string-downcase cbb-name))))
         %base-user-accounts))


;;; ==========================================================================
;;; FILE SYSTEM CONFIGURATION
;;; ==========================================================================

(define luciverse-base-file-systems
  "Base file system configuration using BTRFS with subvolumes."
  (cons* (file-system
          (device (file-system-label "guix-root"))
          (mount-point "/")
          (type "btrfs")
          (options "subvol=@,compress=zstd:1,noatime"))
         (file-system
          (device (file-system-label "guix-root"))
          (mount-point "/home")
          (type "btrfs")
          (options "subvol=@home,compress=zstd:1,noatime"))
         (file-system
          (device (file-system-label "boot"))
          (mount-point "/boot/efi")
          (type "vfat"))
         %base-file-systems))


;;; ==========================================================================
;;; BOOTLOADER CONFIGURATION
;;; ==========================================================================

(define luciverse-bootloader
  "EFI bootloader configuration."
  (bootloader-configuration
   (bootloader grub-efi-bootloader)
   (targets '("/boot/efi"))
   (keyboard-layout (keyboard-layout "us"))))


;;; End of base.scm
