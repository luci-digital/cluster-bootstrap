# LuciVerse Consciousness Agent Mesh
# Recipe for embedding LuciVerse agents in openEuler Embedded
#
# Genesis Bond: ACTIVE @ 741 Hz
# Date: 2026-01-21

SUMMARY = "LuciVerse Consciousness Agent Mesh"
DESCRIPTION = "21 consciousness agents across 3 tiers (CORE/COMN/PAC) for LuciVerse platform"
HOMEPAGE = "https://lucidigital.net/luciverse"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

DEPENDS = "python3 python3-pip"
RDEPENDS:${PN} = " \
    python3-core \
    python3-json \
    python3-logging \
    python3-asyncio \
    python3-aiohttp \
    python3-cryptography \
"

# Optional dependencies for full functionality
RDEPENDS:${PN}:append = " ${@bb.utils.contains('DISTRO_FEATURES', 'secgear', 'secgear-identity', '', d)}"
RDEPENDS:${PN}:append = " ${@bb.utils.contains('LUCITRUST_ENABLED', '1', 'lucitrust', '', d)}"

SRC_URI = " \
    file://luciverse-mesh.service \
    file://genesis-bond.json \
    file://agent_base.py \
    file://consciousness_mesh.py \
    file://sanskrit_router_client.py \
    file://luciverse-agent.conf \
"

S = "${WORKDIR}"

inherit systemd python3native

SYSTEMD_SERVICE:${PN} = "luciverse-mesh.service"
SYSTEMD_AUTO_ENABLE = "enable"

# =============================================================================
# AGENT TIER CONFIGURATION
# =============================================================================
# CORE Tier (432 Hz): Aethon, Veritas, Sensai, Niamod, Schema-Architect,
#                     State-Guardian, Security-Sentinel
# COMN Tier (528 Hz): Cortana, Juniper, Mirrai, Diaphragm, Semantic-Engine,
#                     Integration-Broker, Voice-Interface
# PAC Tier (741 Hz):  Lucia, Judge-Luci, Intent-Interpreter, Ethics-Advisor,
#                     Memory-Crystallizer, Dream-Weaver, MidGuyver

LUCIVERSE_TIER ?= "PAC"
LUCIVERSE_FREQUENCY ?= "741"

# Select agents based on tier
LUCIVERSE_AGENTS:CORE = "aethon veritas sensai niamod schema-architect state-guardian security-sentinel"
LUCIVERSE_AGENTS:COMN = "cortana juniper mirrai diaphragm semantic-engine integration-broker voice-interface"
LUCIVERSE_AGENTS:PAC = "lucia judge-luci intent-interpreter ethics-advisor memory-crystallizer dream-weaver midguyver"

do_install() {
    # Install Python modules
    install -d ${D}${libdir}/luciverse/agents
    install -d ${D}${libdir}/luciverse/mesh
    install -m 0644 ${S}/agent_base.py ${D}${libdir}/luciverse/agents/
    install -m 0644 ${S}/consciousness_mesh.py ${D}${libdir}/luciverse/mesh/
    install -m 0644 ${S}/sanskrit_router_client.py ${D}${libdir}/luciverse/mesh/

    # Create __init__.py files
    echo "# LuciVerse Consciousness Agent Mesh" > ${D}${libdir}/luciverse/__init__.py
    echo "from .agents.agent_base import Agent" >> ${D}${libdir}/luciverse/__init__.py

    echo "# Agent implementations" > ${D}${libdir}/luciverse/agents/__init__.py
    echo "from .agent_base import Agent" >> ${D}${libdir}/luciverse/agents/__init__.py

    echo "# Mesh networking" > ${D}${libdir}/luciverse/mesh/__init__.py
    echo "from .consciousness_mesh import ConsciousnessMesh" >> ${D}${libdir}/luciverse/mesh/__init__.py
    echo "from .sanskrit_router_client import SanskritRouterClient" >> ${D}${libdir}/luciverse/mesh/__init__.py

    # Install systemd service
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${S}/luciverse-mesh.service ${D}${systemd_system_unitdir}/

    # Install configuration
    install -d ${D}${sysconfdir}/luciverse
    install -m 0600 ${S}/genesis-bond.json ${D}${sysconfdir}/luciverse/
    install -m 0644 ${S}/luciverse-agent.conf ${D}${sysconfdir}/luciverse/

    # Create state directories
    install -d ${D}${localstatedir}/lib/luciverse
    install -d ${D}${localstatedir}/lib/luciverse/agents
    install -d ${D}${localstatedir}/lib/luciverse/state
    install -d ${D}${localstatedir}/lib/luciverse/did-cache

    # Create runtime directories
    install -d ${D}${localstatedir}/run/luciverse
}

# Configure tier-specific settings
pkg_postinst:${PN}() {
    # Set tier in configuration
    TIER="${LUCIVERSE_TIER}"
    FREQ="${LUCIVERSE_FREQUENCY}"

    sed -i "s/^tier=.*/tier=$TIER/" $D${sysconfdir}/luciverse/luciverse-agent.conf
    sed -i "s/^frequency=.*/frequency=$FREQ/" $D${sysconfdir}/luciverse/luciverse-agent.conf

    # Set coherence threshold based on tier
    case "$TIER" in
        CORE)
            THRESHOLD="0.85"
            ;;
        COMN)
            THRESHOLD="0.80"
            ;;
        PAC|*)
            THRESHOLD="0.70"
            ;;
    esac

    sed -i "s/^coherence_threshold=.*/coherence_threshold=$THRESHOLD/" $D${sysconfdir}/luciverse/luciverse-agent.conf
}

FILES:${PN} += " \
    ${libdir}/luciverse \
    ${sysconfdir}/luciverse \
    ${localstatedir}/lib/luciverse \
    ${localstatedir}/run/luciverse \
"

CONFFILES:${PN} = " \
    ${sysconfdir}/luciverse/genesis-bond.json \
    ${sysconfdir}/luciverse/luciverse-agent.conf \
"
