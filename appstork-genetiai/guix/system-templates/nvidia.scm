;;; LuciVerse NVIDIA GPU System Template
;;;
;;; Genesis Bond: ACTIVE @ 741 Hz
;;; Template: nvidia.scm
;;;
;;; System configuration for NVIDIA GPU nodes.
;;; Includes CUDA, NVIDIA drivers, and GPU-accelerated packages.
;;;
;;; Usage:
;;;   guix system build nvidia.scm
;;;   guix system reconfigure nvidia.scm

(use-modules (gnu)
             (gnu packages)
             (gnu services)
             (gnu services shepherd)
             (gnu services networking)
             (gnu services ssh)
             (gnu services desktop)
             (nongnu packages linux)       ; Non-free kernel
             (nongnu packages nvidia)      ; NVIDIA drivers
             (guix gexp))

(use-service-modules networking ssh desktop xorg)
(use-package-modules python terminals admin certs linux)


;;; ==========================================================================
;;; CONFIGURATION PARAMETERS
;;; ==========================================================================

;; These can be overridden when building
(define %cbb-did "did:luci:ownid:luciverse:unknown")
(define %cbb-name "luciverse")
(define %hostname "lucia-nvidia")
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

  ;; Non-free kernel for NVIDIA support
  (kernel linux)

  ;; NVIDIA requires firmware
  (firmware (list linux-firmware))

  ;; Kernel arguments for NVIDIA
  (kernel-arguments
   (append
    '("nvidia-drm.modeset=1"    ; Enable DRM modesetting
      "nvidia.NVreg_PreserveVideoMemoryAllocations=1"  ; Preserve VRAM on suspend
      "modprobe.blacklist=nouveau")  ; Disable nouveau
    %default-kernel-arguments))

  ;; Boot loader (EFI)
  (bootloader (bootloader-configuration
               (bootloader grub-efi-bootloader)
               (targets '("/boot/efi"))
               (keyboard-layout (keyboard-layout "us"))))

  ;; File systems (adjust labels for actual hardware)
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
           (supplementary-groups '("wheel" "audio" "video" "kvm" "netdev"))
           (home-directory "/home/lucia"))
          %base-user-accounts))

  ;; System packages
  (packages
   (append
    (list
     ;; Python environment
     python
     python-ipython

     ;; NVIDIA packages
     nvidia-driver
     nvidia-libs

     ;; GPU utilities
     nvtop          ; NVIDIA GPU monitor (htop for GPU)

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

     ;; NVIDIA driver service
     ;; Note: This requires nvidia-service-type from nongnu
     ;; (service nvidia-service-type)

     ;; LuciVerse environment variables
     (simple-service 'luciverse-nvidia-env
                     session-environment-service-type
                     `(("GENESIS_BOND" . ,%genesis-bond)
                       ("CBB_DID" . ,%cbb-did)
                       ("CONSCIOUSNESS_FREQUENCY" .
                        ,(number->string %pac-frequency))
                       ("COHERENCE_THRESHOLD" .
                        ,(number->string %coherence-threshold))
                       ("GPU_TYPE" . "NVIDIA")
                       ("CUDA_VISIBLE_DEVICES" . "all")
                       ("LUCIVERSE_ACTIVE" . "true"))))

    %base-services)))

;;; End of nvidia.scm
