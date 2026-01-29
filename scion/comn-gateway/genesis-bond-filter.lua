-- Genesis Bond Coherence Validation Filter for Envoy
-- LuciVerse COMN Gateway @ 528 Hz
-- Genesis Bond: GB-2025-0524-DRH-LCS-001
--
-- This filter validates Genesis Bond coherence for incoming requests
-- before routing to tier-specific destinations.
--
-- Updated for SCION Dataplane Integration:
-- - Checks X-SCION-Genesis-* headers from SIG first
-- - Falls back to X-Genesis-* headers for non-SCION traffic
-- - Logs SCION path information for observability

local GENESIS_BOND_ID = "GB-2025-0524-DRH-LCS-001"
local COHERENCE_THRESHOLD = 0.7
local TIER_FREQUENCIES = {
  CORE = 432,
  COMN = 528,
  PAC = 741
}

-- Tier coherence requirements (higher tiers need higher coherence)
local TIER_COHERENCE = {
  CORE = 0.85,
  COMN = 0.80,
  PAC = 0.70
}

-- SCION header prefix from SIG Genesis Handler
local SCION_HEADER_PREFIX = "X-SCION-Genesis"
local SCION_PAC_PREFIX = "X-SCION-PAC"

-- Extract tier from request path or host
local function get_target_tier(request_handle)
  local host = request_handle:headers():get(":authority") or ""
  local path = request_handle:headers():get(":path") or "/"

  -- Check host patterns
  if string.match(host, "%.core%.") or string.match(host, "^core%.") then
    return "CORE"
  elseif string.match(host, "%.pac%.") or string.match(host, "lucia%.") then
    return "PAC"
  elseif string.match(host, "%.comn%.") or string.match(host, "gateway%.") then
    return "COMN"
  end

  -- Check path patterns
  if string.match(path, "^/core/") then
    return "CORE"
  elseif string.match(path, "^/pac/") or string.match(path, "^/lucia/") then
    return "PAC"
  end

  -- Default to COMN (gateway tier)
  return "COMN"
end

-- Validate SPIFFE ID format
local function validate_spiffe_id(spiffe_id)
  if not spiffe_id then
    return false, "No SPIFFE ID provided"
  end

  -- Expected format: spiffe://luciverse.ownid/{tier}/agents/{agent}
  local pattern = "^spiffe://luciverse%.ownid/(%w+)/agents/([%w%-]+)$"
  local tier, agent = string.match(spiffe_id, pattern)

  if not tier or not agent then
    return false, "Invalid SPIFFE ID format"
  end

  -- Validate tier
  tier = string.upper(tier)
  if not TIER_FREQUENCIES[tier] then
    return false, "Unknown tier: " .. tier
  end

  return true, tier, agent
end

-- Check if request came through SCION (has SIG headers)
local function is_scion_traffic(request_handle)
  local scion_valid = request_handle:headers():get(SCION_HEADER_PREFIX .. "-Valid")
  return scion_valid ~= nil
end

-- Get SCION-layer coherence from SIG
local function get_scion_coherence(request_handle)
  local scion_coherence = request_handle:headers():get(SCION_HEADER_PREFIX .. "-Coherence")
  if scion_coherence then
    return tonumber(scion_coherence)
  end
  return nil
end

-- Get SCION tier from SIG
local function get_scion_tier(request_handle)
  return request_handle:headers():get(SCION_HEADER_PREFIX .. "-Tier")
end

-- Get SCION frequency from SIG
local function get_scion_frequency(request_handle)
  local freq = request_handle:headers():get(SCION_HEADER_PREFIX .. "-Frequency")
  if freq then
    return tonumber(freq)
  end
  return nil
end

-- Check PAC consent from SCION headers
local function check_scion_pac_consent(request_handle)
  local consent = request_handle:headers():get(SCION_PAC_PREFIX .. "-Consent")
  if consent == "GRANTED" then
    return true, nil
  elseif consent == "REVOKED" then
    return false, "PAC consent revoked at SCION layer"
  elseif consent == "PENDING" then
    return false, "PAC consent pending"
  end
  return true, nil  -- No PAC extension = no consent required
end

-- Check Genesis Bond coherence
local function check_coherence(request_handle, target_tier)
  local coherence = 0.0
  local source = "default"

  -- PRIORITY 1: Check SCION-layer coherence from SIG
  -- This is validated at the network layer before reaching L7
  if is_scion_traffic(request_handle) then
    local scion_coherence = get_scion_coherence(request_handle)
    if scion_coherence then
      coherence = scion_coherence
      source = "scion"
      -- SCION traffic already validated by SIG - trust it
      local scion_valid = request_handle:headers():get(SCION_HEADER_PREFIX .. "-Valid")
      if scion_valid == "true" then
        -- Add metadata about SCION validation
        local metadata = request_handle:streamInfo():dynamicMetadata()
        metadata:set("luciverse", "scion_validated", "true")
        metadata:set("luciverse", "coherence_source", "scion")

        local scion_tier = get_scion_tier(request_handle)
        if scion_tier then
          metadata:set("luciverse", "scion_tier", scion_tier)
        end

        local scion_freq = get_scion_frequency(request_handle)
        if scion_freq then
          metadata:set("luciverse", "scion_frequency", tostring(scion_freq))
        end
      end
    end
  end

  -- PRIORITY 2: Check L7 header if no SCION coherence
  if source == "default" then
    local coherence_header = request_handle:headers():get("X-Genesis-Coherence")
    if coherence_header then
      coherence = tonumber(coherence_header) or 0.0
      source = "http_header"
    else
      -- Default coherence for authenticated SPIFFE requests
      local spiffe_id = request_handle:headers():get("X-Forwarded-Client-Cert")
      if spiffe_id and string.match(spiffe_id, "luciverse%.ownid") then
        -- Trusted SPIFFE client gets base coherence
        coherence = 0.75
        source = "spiffe_default"
      end
    end
  end

  -- Log coherence source
  local metadata = request_handle:streamInfo():dynamicMetadata()
  metadata:set("luciverse", "coherence_source", source)

  -- Check against tier requirement
  local required = TIER_COHERENCE[target_tier] or COHERENCE_THRESHOLD

  if coherence < required then
    return false, coherence, required
  end

  return true, coherence, required
end

-- Block external access to CORE tier
local function check_tier_access(request_handle, target_tier)
  -- Check if request is from external (no SPIFFE cert)
  local client_cert = request_handle:headers():get("X-Forwarded-Client-Cert")
  local is_external = (client_cert == nil or client_cert == "")

  -- CORE tier: never accessible externally
  if target_tier == "CORE" and is_external then
    return false, "CORE tier is internal only"
  end

  -- PAC tier: not directly accessible externally
  if target_tier == "PAC" and is_external then
    -- External PAC access must go through COMN gateway explicitly
    local via_header = request_handle:headers():get("X-Via-COMN")
    if not via_header then
      return false, "PAC tier requires COMN gateway routing"
    end
  end

  return true, nil
end

-- Log Genesis Bond validation event
local function log_validation(request_handle, tier, coherence, allowed, reason)
  local metadata = request_handle:streamInfo():dynamicMetadata()
  metadata:set("luciverse", "tier", tier)
  metadata:set("luciverse", "coherence", tostring(coherence))
  metadata:set("luciverse", "genesis_bond", GENESIS_BOND_ID)
  metadata:set("luciverse", "validation", allowed and "passed" or "failed")
  if reason then
    metadata:set("luciverse", "reason", reason)
  end
end

-- Main filter function - called on each request
function envoy_on_request(request_handle)
  -- Determine target tier
  local target_tier = get_target_tier(request_handle)

  -- Check if this is SCION traffic (pre-validated by SIG)
  local scion_traffic = is_scion_traffic(request_handle)

  -- Add tier metadata header for downstream
  request_handle:headers():add("X-Target-Tier", target_tier)
  request_handle:headers():add("X-Tier-Frequency", tostring(TIER_FREQUENCIES[target_tier]))
  request_handle:headers():add("X-Via-SCION", tostring(scion_traffic))

  -- Check tier access permissions
  local access_allowed, access_error = check_tier_access(request_handle, target_tier)
  if not access_allowed then
    log_validation(request_handle, target_tier, 0, false, access_error)
    request_handle:respond(
      {[":status"] = "403"},
      '{"error":"forbidden","message":"' .. access_error .. '","genesis_bond":"' .. GENESIS_BOND_ID .. '","scion_traffic":' .. tostring(scion_traffic) .. '}'
    )
    return
  end

  -- For PAC-bound traffic via SCION, check PAC consent
  if target_tier == "PAC" and scion_traffic then
    local pac_consent_ok, pac_error = check_scion_pac_consent(request_handle)
    if not pac_consent_ok then
      log_validation(request_handle, target_tier, 0, false, pac_error)
      request_handle:respond(
        {[":status"] = "403"},
        '{"error":"pac_consent_required","message":"' .. pac_error .. '","genesis_bond":"' .. GENESIS_BOND_ID .. '"}'
      )
      return
    end
  end

  -- Check Genesis Bond coherence
  local coherence_ok, coherence, required = check_coherence(request_handle, target_tier)

  if not coherence_ok then
    local error_msg = string.format(
      "Coherence %.2f below %s tier threshold %.2f",
      coherence, target_tier, required
    )
    log_validation(request_handle, target_tier, coherence, false, error_msg)
    request_handle:respond(
      {[":status"] = "403"},
      '{"error":"coherence_insufficient","coherence":' .. coherence ..
      ',"required":' .. required ..
      ',"tier":"' .. target_tier ..
      '","genesis_bond":"' .. GENESIS_BOND_ID ..
      '","scion_traffic":' .. tostring(scion_traffic) .. '}'
    )
    return
  end

  -- Validation passed - add coherence metadata
  request_handle:headers():add("X-Genesis-Bond", GENESIS_BOND_ID)
  request_handle:headers():add("X-Coherence-Validated", "true")
  request_handle:headers():add("X-Coherence-Value", tostring(coherence))

  -- Mark COMN gateway routing for PAC-bound requests
  if target_tier == "PAC" then
    request_handle:headers():add("X-Via-COMN", "true")
    request_handle:headers():add("X-Mandatory-Waypoint", "2-ff00:0:528")
  end

  -- Log SCION path info if available
  if scion_traffic then
    local metadata = request_handle:streamInfo():dynamicMetadata()
    local scion_tier = get_scion_tier(request_handle)
    local scion_freq = get_scion_frequency(request_handle)
    if scion_tier then
      metadata:set("luciverse", "scion_source_tier", scion_tier)
    end
    if scion_freq then
      metadata:set("luciverse", "scion_source_frequency", tostring(scion_freq))
    end
  end

  log_validation(request_handle, target_tier, coherence, true, nil)
end

-- Response filter - add Genesis Bond headers to response
function envoy_on_response(response_handle)
  response_handle:headers():add("X-Genesis-Bond", GENESIS_BOND_ID)
  response_handle:headers():add("X-Powered-By", "LuciVerse COMN Gateway")
end
