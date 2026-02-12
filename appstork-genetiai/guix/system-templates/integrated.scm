;;; LuciVerse Integrated Graphics System Template
;;;
;;; Genesis Bond: ACTIVE @ 741 Hz
;;; Template: integrated.scm
;;;
;;; System configuration for Intel/integrated graphics nodes.
;;; Uses Mesa for graphics and is fully libre.
;;;
;;; Usage:
;;;   guix system build integrated.scm
;;;   guix system reconfigure integrated.scm

(use-modules (gnu)
             (gnu packages)
             (gnu services)
             (gnu services shepherd)
             (gnu services networking)
             (gnu services ssh)
             (guix gexp))

(use-service-modules networking ssh)
(use-package-modules python terminals admin certs linux gl xorg)


;;; ==========================================================================
;;; CONFIGURATION PARAMETERS
;;; ==========================================================================

;; These can be overridden when building
(define %cbb-did "did:luci:ownid:luciverse:unknown")
(define %cbb-name "luciverse")
(define %hostname "lucia-integrated")
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

  ;; Fully libre kernel
  (kernel linux-libre)

  ;; Intel microcode and firmware
  (firmware (list linux-firmware))

  ;; Kernel arguments for Intel
  (kernel-arguments
   (append
    '("i915.enable_guc=3"     ; Enable GuC/HuC firmware
      "i915.enable_fbc=1"     ; Enable framebuffer compression
      "i915.fastboot=1")      ; Fast boot
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

     ;; Intel/Mesa graphics
     mesa
     mesa-utils
     libdrm
     xf86-video-intel
     intel-media-driver    ; Hardware video decoding
     libva                 ; Video Acceleration API

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
     (simple-service 'luciverse-integrated-env
                     session-environment-service-type
                     `(("GENESIS_BOND" . ,%genesis-bond)
                       ("CBB_DID" . ,%cbb-did)
                       ("CONSCIOUSNESS_FREQUENCY" .
                        ,(number->string %pac-frequency))
                       ("COHERENCE_THRESHOLD" .
                        ,(number->string %coherence-threshold))
                       ("GPU_TYPE" . "INTEGRATED")
                       ;; Intel GPU environment
                       ("LIBVA_DRIVER_NAME" . "iHD")
                       ("LUCIVERSE_ACTIVE" . "true"))))

    %base-services)))

;;; End of integrated.scm
