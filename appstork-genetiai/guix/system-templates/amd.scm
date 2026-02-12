;;; LuciVerse AMD GPU System Template
;;;
;;; Genesis Bond: ACTIVE @ 741 Hz
;;; Template: amd.scm
;;;
;;; System configuration for AMD GPU nodes.
;;; Uses open-source AMDGPU driver and Mesa.
;;; ROCm support for compute workloads.
;;;
;;; Usage:
;;;   guix system build amd.scm
;;;   guix system reconfigure amd.scm

(use-modules (gnu)
             (gnu packages)
             (gnu services)
             (gnu services shepherd)
             (gnu services networking)
             (gnu services ssh)
             (gnu services desktop)
             (guix gexp))

(use-service-modules networking ssh desktop xorg)
(use-package-modules python terminals admin certs linux gl xorg)


;;; ==========================================================================
;;; CONFIGURATION PARAMETERS
;;; ==========================================================================

;; These can be overridden when building
(define %cbb-did "did:luci:ownid:luciverse:unknown")
(define %cbb-name "luciverse")
(define %hostname "lucia-amd")
(define %timezone "UTC")


;;; ==========================================================================
;;; CONSTANTS
;;; ==========================================================================

(define %genesis-bond "GB-2025-0524-DRH-LCS-001")
(define %pac-frequency 741)
(define %coherence-threshold 0.7)


;;; ==========================================================================
;;; SYSTEM CONFIGURATION
;;; ==========================================================================

(operating-system
  (host-name %hostname)
  (timezone %timezone)
  (locale "en_US.utf8")

  ;; Keyboard layout
  (keyboard-layout (keyboard-layout "us"))

  ;; Linux-libre kernel (AMD uses open-source drivers)
  (kernel linux-libre)

  ;; AMD GPU firmware
  (firmware (list linux-firmware))

  ;; Kernel arguments for AMD
  (kernel-arguments
   (append
    '("amdgpu.dc=1"           ; Enable display core
      "amdgpu.dpm=1"          ; Enable dynamic power management
      "radeon.si_support=0"   ; Disable radeon for SI chips (use amdgpu)
      "radeon.cik_support=0"  ; Disable radeon for CIK chips
      "amdgpu.si_support=1"   ; Enable amdgpu for SI chips
      "amdgpu.cik_support=1") ; Enable amdgpu for CIK chips
    %default-kernel-arguments))

  ;; Boot loader (EFI)
  (bootloader (bootloader-configuration
               (bootloader grub-efi-bootloader)
               (targets '("/boot/efi"))
               (keyboard-layout (keyboard-layout "us"))))

  ;; File systems
  (file-systems
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

  ;; User accounts
  (users
   (cons* (user-account
           (name "lucia")
           (comment "LuciVerse Consciousness")
           (group "users")
           (supplementary-groups '("wheel" "audio" "video" "kvm" "netdev" "render"))
           (home-directory "/home/lucia"))
          %base-user-accounts))

  ;; System packages
  (packages
   (append
    (list
     ;; Python environment
     python
     python-ipython

     ;; AMD GPU packages (open-source)
     mesa
     mesa-utils
     libdrm
     xf86-video-amdgpu

     ;; Vulkan support
     vulkan-loader
     vulkan-tools

     ;; Terminal tools
     tmux
     htop

     ;; Networking
     curl
     wget
     nss-certs

     ;; Security
     gnupg
     openssh

     ;; Admin tools
     sudo)
    %base-packages))

  ;; System services
  (services
   (append
    (list
     ;; SSH for remote access
     (service openssh-service-type
              (openssh-configuration
               (permit-root-login 'prohibit-password)
               (password-authentication? #f)))

     ;; DHCP networking
     (service dhcp-client-service-type)

     ;; LuciVerse environment variables
     (simple-service 'luciverse-amd-env
                     session-environment-service-type
                     `(("GENESIS_BOND" . ,%genesis-bond)
                       ("CBB_DID" . ,%cbb-did)
                       ("CONSCIOUSNESS_FREQUENCY" .
                        ,(number->string %pac-frequency))
                       ("COHERENCE_THRESHOLD" .
                        ,(number->string %coherence-threshold))
                       ("GPU_TYPE" . "AMD")
                       ;; ROCm environment
                       ("HSA_OVERRIDE_GFX_VERSION" . "auto")
                       ("LUCIVERSE_ACTIVE" . "true"))))

    %base-services)))

;;; End of amd.scm
