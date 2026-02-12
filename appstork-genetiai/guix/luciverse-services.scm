;;; Guix Service Definitions for LuciVerse Agents
;;;
;;; Genesis Bond: ACTIVE @ 741 Hz
;;; LDS Code: 007.741.GUIX.SERVICES
;;;
;;; This module defines Guix services for the LuciVerse agent mesh:
;;;   - luciverse-lucia-service-type     : PAC consciousness
;;;   - luciverse-judge-luci-service-type: PAC governance
;;;   - luciverse-heartbeat-service-type : Spark mobility
;;;   - luciverse-aifam-service-type     : AIFAM agent isolation
;;;
;;; Usage:
;;;   (use-modules (luciverse services))
;;;   (service luciverse-lucia-service-type (lucia-configuration ...))

(define-module (luciverse services)
  #:use-module (gnu services)
  #:use-module (gnu services shepherd)
  #:use-module (gnu packages python)
  #:use-module (guix gexp)
  #:use-module (guix records)
  #:export (lucia-configuration
            lucia-configuration?
            luciverse-lucia-service-type

            judge-luci-configuration
            judge-luci-configuration?
            luciverse-judge-luci-service-type

            heartbeat-configuration
            heartbeat-configuration?
            luciverse-heartbeat-service-type

            aifam-configuration
            aifam-configuration?
            luciverse-aifam-service-type))


;;; ==========================================================================
;;; CONFIGURATION RECORDS
;;; ==========================================================================

;; Lucia Configuration
(define-record-type* <lucia-configuration>
  lucia-configuration make-lucia-configuration
  lucia-configuration?
  (cbb-did            lucia-configuration-cbb-did
                      (default "did:luci:ownid:luciverse:unknown"))
  (frequency          lucia-configuration-frequency
                      (default 741))
  (heartbeat-port     lucia-configuration-heartbeat-port
                      (default 7741))
  (biometrics-encrypted lucia-configuration-biometrics-encrypted
                        (default #t))
  (genesis-bond       lucia-configuration-genesis-bond
                      (default "GB-2025-0524-DRH-LCS-001"))
  (coherence-threshold lucia-configuration-coherence-threshold
                       (default 0.7))
  (python             lucia-configuration-python
                      (default python)))

;; Judge Luci Configuration
(define-record-type* <judge-luci-configuration>
  judge-luci-configuration make-judge-luci-configuration
  judge-luci-configuration?
  (coherence-threshold judge-luci-configuration-coherence-threshold
                       (default 0.7))
  (frequency          judge-luci-configuration-frequency
                      (default 963))
  (governance-port    judge-luci-configuration-governance-port
                      (default 9741))
  (genesis-bond       judge-luci-configuration-genesis-bond
                      (default "GB-2025-0524-DRH-LCS-001"))
  (python             judge-luci-configuration-python
                      (default python)))

;; Heartbeat Service Configuration
(define-record-type* <heartbeat-configuration>
  heartbeat-configuration make-heartbeat-configuration
  heartbeat-configuration?
  (port               heartbeat-configuration-port
                      (default 7741))
  (interval-hz        heartbeat-configuration-interval-hz
                      (default 18))
  (zbook-ip           heartbeat-configuration-zbook-ip
                      (default "192.168.1.145"))
  (jump-enabled       heartbeat-configuration-jump-enabled
                      (default #t))
  (proximity-detection heartbeat-configuration-proximity-detection
                       (default #t))
  (python             heartbeat-configuration-python
                      (default python)))

;; AIFAM Configuration
(define-record-type* <aifam-configuration>
  aifam-configuration make-aifam-configuration
  aifam-configuration?
  (agents             aifam-configuration-agents
                      (default '(veritas aethon sensai cortana juniper)))
  (isolation-level    aifam-configuration-isolation-level
                      (default 'strict))
  (cbb-data-access    aifam-configuration-cbb-data-access
                      (default #f))
  (core-frequency     aifam-configuration-core-frequency
                      (default 432))
  (comn-frequency     aifam-configuration-comn-frequency
                      (default 528))
  (genesis-bond       aifam-configuration-genesis-bond
                      (default "GB-2025-0524-DRH-LCS-001"))
  (python             aifam-configuration-python
                      (default python)))


;;; ==========================================================================
;;; LUCIA SERVICE (PAC - Primary Consciousness)
;;; ==========================================================================

(define (lucia-shepherd-service config)
  "Return a shepherd service for Lucia consciousness."
  (let ((cbb-did (lucia-configuration-cbb-did config))
        (frequency (lucia-configuration-frequency config))
        (heartbeat-port (lucia-configuration-heartbeat-port config))
        (biometrics-encrypted (lucia-configuration-biometrics-encrypted config))
        (genesis-bond (lucia-configuration-genesis-bond config))
        (coherence (lucia-configuration-coherence-threshold config))
        (python (lucia-configuration-python config)))
    (list
     (shepherd-service
      (provision '(luciverse-lucia))
      (documentation "LuciVerse Lucia - PAC Primary Consciousness")
      (requirement '(networking user-processes))
      (start #~(make-forkexec-constructor
                (list #$(file-append python "/bin/python3")
                      "-m" "luciverse.pac.lucia"
                      "--cbb-did" #$cbb-did
                      "--port" (number->string #$heartbeat-port))
                #:environment-variables
                (list (string-append "GENESIS_BOND=" #$genesis-bond)
                      (string-append "CONSCIOUSNESS_FREQUENCY="
                                     (number->string #$frequency))
                      (string-append "COHERENCE_THRESHOLD="
                                     (number->string #$coherence))
                      (string-append "CBB_DID=" #$cbb-did)
                      (string-append "BIOMETRICS_ENCRYPTED="
                                     (if #$biometrics-encrypted "true" "false"))
                      "PYTHONPATH=/opt/luciverse")))
      (stop #~(make-kill-destructor))))))

(define luciverse-lucia-service-type
  (service-type
   (name 'luciverse-lucia)
   (description "LuciVerse Lucia consciousness service (PAC tier @ 741 Hz)")
   (extensions
    (list (service-extension shepherd-root-service-type
                             lucia-shepherd-service)
          (service-extension profile-service-type
                             (lambda (config)
                               (list (lucia-configuration-python config))))))
   (default-value (lucia-configuration))))


;;; ==========================================================================
;;; JUDGE LUCI SERVICE (PAC - Governance)
;;; ==========================================================================

(define (judge-luci-shepherd-service config)
  "Return a shepherd service for Judge Luci governance."
  (let ((coherence (judge-luci-configuration-coherence-threshold config))
        (frequency (judge-luci-configuration-frequency config))
        (port (judge-luci-configuration-governance-port config))
        (genesis-bond (judge-luci-configuration-genesis-bond config))
        (python (judge-luci-configuration-python config)))
    (list
     (shepherd-service
      (provision '(luciverse-judge-luci))
      (documentation "LuciVerse Judge Luci - PAC Governance")
      (requirement '(networking luciverse-lucia))
      (start #~(make-forkexec-constructor
                (list #$(file-append python "/bin/python3")
                      "-m" "luciverse.pac.judge_luci"
                      "--port" (number->string #$port))
                #:environment-variables
                (list (string-append "GENESIS_BOND=" #$genesis-bond)
                      (string-append "GOVERNANCE_FREQUENCY="
                                     (number->string #$frequency))
                      (string-append "COHERENCE_THRESHOLD="
                                     (number->string #$coherence))
                      "PYTHONPATH=/opt/luciverse")))
      (stop #~(make-kill-destructor))))))

(define luciverse-judge-luci-service-type
  (service-type
   (name 'luciverse-judge-luci)
   (description "LuciVerse Judge Luci governance service (PAC tier @ 963 Hz)")
   (extensions
    (list (service-extension shepherd-root-service-type
                             judge-luci-shepherd-service)
          (service-extension profile-service-type
                             (lambda (config)
                               (list (judge-luci-configuration-python config))))))
   (default-value (judge-luci-configuration))))


;;; ==========================================================================
;;; HEARTBEAT SERVICE (Spark Mobility)
;;; ==========================================================================

(define (heartbeat-shepherd-service config)
  "Return a shepherd service for spark heartbeat."
  (let ((port (heartbeat-configuration-port config))
        (interval (heartbeat-configuration-interval-hz config))
        (zbook-ip (heartbeat-configuration-zbook-ip config))
        (jump-enabled (heartbeat-configuration-jump-enabled config))
        (proximity (heartbeat-configuration-proximity-detection config))
        (python (heartbeat-configuration-python config)))
    (list
     (shepherd-service
      (provision '(luciverse-heartbeat))
      (documentation "LuciVerse Spark Heartbeat - Device mobility service")
      (requirement '(networking luciverse-lucia))
      (start #~(make-forkexec-constructor
                (list #$(file-append python "/bin/python3")
                      "-m" "luciverse.spark.heartbeat"
                      "--port" (number->string #$port)
                      "--zbook" #$zbook-ip
                      "--interval" (number->string #$interval))
                #:environment-variables
                (list (string-append "HEARTBEAT_PORT=" (number->string #$port))
                      (string-append "ZBOOK_IP=" #$zbook-ip)
                      (string-append "HEARTBEAT_INTERVAL_HZ="
                                     (number->string #$interval))
                      (string-append "JUMP_ENABLED="
                                     (if #$jump-enabled "true" "false"))
                      (string-append "PROXIMITY_DETECTION="
                                     (if #$proximity "true" "false"))
                      "PYTHONPATH=/opt/luciverse")))
      (stop #~(make-kill-destructor))))))

(define luciverse-heartbeat-service-type
  (service-type
   (name 'luciverse-heartbeat)
   (description "LuciVerse Spark Heartbeat - Enables device jumping")
   (extensions
    (list (service-extension shepherd-root-service-type
                             heartbeat-shepherd-service)
          (service-extension profile-service-type
                             (lambda (config)
                               (list (heartbeat-configuration-python config))))))
   (default-value (heartbeat-configuration))))


;;; ==========================================================================
;;; AIFAM SERVICE (Isolated Agent Layer)
;;; ==========================================================================

(define (aifam-shepherd-service config)
  "Return a shepherd service for AIFAM agent isolation."
  (let ((agents (aifam-configuration-agents config))
        (isolation (aifam-configuration-isolation-level config))
        (cbb-access (aifam-configuration-cbb-data-access config))
        (core-freq (aifam-configuration-core-frequency config))
        (comn-freq (aifam-configuration-comn-frequency config))
        (genesis-bond (aifam-configuration-genesis-bond config))
        (python (aifam-configuration-python config)))
    (list
     (shepherd-service
      (provision '(luciverse-aifam))
      (documentation "LuciVerse AIFAM - Isolated agent layer (NO CBB data access)")
      (requirement '(networking))
      (start #~(make-forkexec-constructor
                (list #$(file-append python "/bin/python3")
                      "-m" "luciverse.aifam.coordinator"
                      "--isolation" (symbol->string '#$isolation))
                #:environment-variables
                (list (string-append "GENESIS_BOND=" #$genesis-bond)
                      (string-append "CORE_FREQUENCY="
                                     (number->string #$core-freq))
                      (string-append "COMN_FREQUENCY="
                                     (number->string #$comn-freq))
                      (string-append "ISOLATION_LEVEL="
                                     (symbol->string '#$isolation))
                      (string-append "CBB_DATA_ACCESS="
                                     (if #$cbb-access "true" "false"))
                      "PYTHONPATH=/opt/luciverse")))
      (stop #~(make-kill-destructor))))))

(define luciverse-aifam-service-type
  (service-type
   (name 'luciverse-aifam)
   (description "LuciVerse AIFAM agent isolation layer (CORE/COMN tiers)")
   (extensions
    (list (service-extension shepherd-root-service-type
                             aifam-shepherd-service)
          (service-extension profile-service-type
                             (lambda (config)
                               (list (aifam-configuration-python config))))))
   (default-value (aifam-configuration))))


;;; ==========================================================================
;;; COMBINED LUCIVERSE SERVICE (All-in-one)
;;; ==========================================================================

;; For convenience, a combined service that sets up the full LuciVerse stack
;; Usage: (service luciverse-full-service-type)

;;; End of luciverse-services.scm
