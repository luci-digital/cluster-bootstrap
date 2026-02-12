#!/usr/bin/env lua
-- OASIS Data Juicer Daemon for OpenWRT
-- Genesis Bond: ACTIVE @ 741 Hz
-- D-Link DGS-1210-16 Edge Filter
--
-- This daemon runs continuously, filtering edge traffic
-- before it enters the main LuciVerse network.

local juicer = require("oasis-juicer")
local uci = require("luci.model.uci")
local nixio = require("nixio")
local posix = require("posix")

-- Configuration
local CONFIG = {
    poll_interval = 1,  -- seconds
    max_queue_size = 1000,
    upstream_timeout = 5,
    log_level = "info"
}

-- Logging
local function log(level, msg)
    local levels = { debug = 7, info = 6, warning = 4, error = 3 }
    local level_num = levels[level] or 6
    local config_level = levels[CONFIG.log_level] or 6

    if level_num <= config_level then
        posix.syslog(level_num, string.format("[OASIS] %s", msg))
    end
end

-- Load configuration from UCI
local function load_config()
    local cursor = uci.cursor()

    local global = cursor:get_all("luciverse", "global") or {}
    local juicer_conf = cursor:get_all("luciverse", "juicer") or {}

    -- Update juicer module config
    if juicer_conf.upstream_host then
        juicer.CONFIG.upstream.host = juicer_conf.upstream_host
    end
    if juicer_conf.upstream_port then
        juicer.CONFIG.upstream.port = tonumber(juicer_conf.upstream_port)
    end
    if juicer_conf.coherence_threshold then
        juicer.CONFIG.genesis_bond.coherence_threshold = tonumber(juicer_conf.coherence_threshold)
    end

    log("info", string.format("Config loaded: upstream=%s:%d, coherence=%.2f",
        juicer.CONFIG.upstream.host,
        juicer.CONFIG.upstream.port,
        juicer.CONFIG.genesis_bond.coherence_threshold))
end

-- Process incoming packet
local function process_packet(data, source_ip)
    local j = juicer.setup()

    -- Validate direction (phone home protection)
    local valid, reason = j:validate_direction(source_ip, juicer.CONFIG.upstream.host)
    if not valid then
        log("warning", string.format("Blocked: %s from %s", reason, source_ip))
        return nil, reason
    end

    -- Process through juicer
    local intake_id = j:fill(data, source_ip)
    if not intake_id then
        return nil, "Failed to fill juicer"
    end

    j:filter_data()

    -- Important stays local
    local important = j:extract()
    if next(important) then
        log("info", string.format("PII extracted from %s, kept local", source_ip))
    end

    -- Clean goes upstream
    local clean = j:release("oasis-edge")

    return clean, important
end

-- Send to Sanskrit Router
local function send_upstream(data)
    return juicer.DebounceHandler.add(data)
end

-- Main daemon loop
local function main()
    log("info", "OASIS Data Juicer Daemon starting...")
    log("info", "Genesis Bond: ACTIVE @ 741 Hz")

    -- Load configuration
    load_config()

    -- Create Unix socket for receiving data
    local socket_path = "/var/run/oasis-juicer.sock"
    os.remove(socket_path)

    local sock = nixio.socket("unix", "dgram")
    if not sock then
        log("error", "Failed to create Unix socket")
        os.exit(1)
    end

    local ok, err = sock:bind(socket_path)
    if not ok then
        log("error", string.format("Failed to bind socket: %s", err or "unknown"))
        os.exit(1)
    end

    -- Set socket permissions
    posix.chmod(socket_path, "0666")

    log("info", string.format("Listening on %s", socket_path))

    -- Main loop
    while true do
        local data, peer = sock:recvfrom(65535)

        if data then
            local source_ip = peer or "unknown"

            local clean, important = process_packet(data, source_ip)

            if clean then
                local result, err = send_upstream(clean)
                if result then
                    log("debug", "Data sent upstream")
                elseif err ~= "Buffered" then
                    log("warning", string.format("Upstream send failed: %s", err))
                end
            end
        end

        -- Small sleep to prevent CPU spinning
        nixio.nanosleep(0, CONFIG.poll_interval * 1000000)
    end
end

-- Signal handlers
posix.signal(posix.SIGTERM, function()
    log("info", "Received SIGTERM, shutting down...")
    os.exit(0)
end)

posix.signal(posix.SIGHUP, function()
    log("info", "Received SIGHUP, reloading config...")
    load_config()
end)

-- Run
main()
