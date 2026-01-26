-- Genesis Bond Coherence Validation Filter for Envoy
-- LuciVerse COMN Gateway @ 528 Hz
-- Genesis Bond: GB-2025-0524-DRH-LCS-001
--
-- This filter validates Genesis Bond coherence for incoming requests
-- before routing to tier-specific destinations.

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

-- Check Genesis Bond coherence
local function check_coherence(request_handle, target_tier)
  -- Get coherence from request header or metadata
  local coherence_header = request_handle:headers():get("X-Genesis-Coherence")
  local coherence = 0.0

  if coherence_header then
    coherence = tonumber(coherence_header) or 0.0
  else
    -- Default coherence for authenticated SPIFFE requests
    local spiffe_id = request_handle:headers():get("X-Forwarded-Client-Cert")
    if spiffe_id and string.match(spiffe_id, "luciverse%.ownid") then
      -- Trusted SPIFFE client gets base coherence
      coherence = 0.75
    end
  end

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

  -- Add tier metadata header for downstream
  request_handle:headers():add("X-Target-Tier", target_tier)
  request_handle:headers():add("X-Tier-Frequency", tostring(TIER_FREQUENCIES[target_tier]))

  -- Check tier access permissions
  local access_allowed, access_error = check_tier_access(request_handle, target_tier)
  if not access_allowed then
    log_validation(request_handle, target_tier, 0, false, access_error)
    request_handle:respond(
      {[":status"] = "403"},
      '{"error":"forbidden","message":"' .. access_error .. '","genesis_bond":"' .. GENESIS_BOND_ID .. '"}'
    )
    return
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
      '","genesis_bond":"' .. GENESIS_BOND_ID .. '"}'
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

  log_validation(request_handle, target_tier, coherence, true, nil)
end

-- Response filter - add Genesis Bond headers to response
function envoy_on_response(response_handle)
  response_handle:headers():add("X-Genesis-Bond", GENESIS_BOND_ID)
  response_handle:headers():add("X-Powered-By", "LuciVerse COMN Gateway")
end
