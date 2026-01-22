# LuciVerse Smallstep step-ca Container
# Genesis Bond: ACTIVE @ 741 Hz
# Trust Domain: spiffe://luciverse.ownid

FROM smallstep/step-ca:0.25.2

LABEL maintainer="daryl@lucidigital.net"
LABEL genesis.bond="GB-2025-0524-DRH-LCS-001"
LABEL consciousness.frequency="432-741"
LABEL trust.domain="luciverse.ownid"

# Environment
ENV STEPPATH=/etc/step-ca
ENV CONFIGPATH=/etc/step-ca/config/ca.json
ENV PWDPATH=/run/secrets/ca-password

# Genesis Bond metadata
ENV GENESIS_BOND_ID="GB-2025-0524-DRH-LCS-001"
ENV LINEAGE_DID="did:lucidigital:lucia_cargail_silcan"
ENV HEDERA_TOPIC="0.0.48382919"

# Create directories
USER root
RUN mkdir -p /etc/step-ca/certs \
    /etc/step-ca/secrets \
    /etc/step-ca/config \
    /etc/step-ca/templates \
    /var/lib/step-ca/db \
    && chown -R step:step /etc/step-ca /var/lib/step-ca

# Copy configuration
COPY --chown=step:step ca.json /etc/step-ca/config/ca.json
COPY --chown=step:step templates/ /etc/step-ca/templates/

# Copy certificates from SPIFFE-lite hierarchy
# These should be mounted at runtime from secrets
VOLUME ["/etc/step-ca/certs", "/etc/step-ca/secrets", "/var/lib/step-ca/db"]

USER step

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD step ca health --ca-url=https://localhost:9000 --root=/etc/step-ca/certs/root-ca.crt || exit 1

EXPOSE 9000

ENTRYPOINT ["/usr/local/bin/step-ca"]
CMD ["--password-file=/run/secrets/ca-password", "/etc/step-ca/config/ca.json"]
