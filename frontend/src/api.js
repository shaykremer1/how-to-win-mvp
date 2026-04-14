function normalizeApiBase(v) {
  if (v == null || v === "") return "/api";
  const s = String(v).trim().replace(/\/+$/, "");
  return s || "/api";
}

const API_BASE_RAW = import.meta.env.VITE_API_BASE || import.meta.env.VITE_BACKEND_URL || "";
export const API_BASE = normalizeApiBase(API_BASE_RAW);
export const API_BASE_SOURCE = API_BASE_RAW ? "env" : "default";

async function safeFetch(url, options, timeoutMs = 15000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...(options || {}), signal: controller.signal });
  } catch (e) {
    if (e?.name === "AbortError") {
      throw new Error(`Request timeout after ${timeoutMs}ms: ${url}`);
    }
    throw new Error(`Network error calling ${url}: ${e.message}`);
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchJsonWithDebug(url, options = {}, label = "request") {
  const res = await safeFetch(url, options);
  const text = await res.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch (_) {
    json = null;
  }

  console.debug(`[API:${label}]`, { url, status: res.status, ok: res.ok, bodyPreview: text.slice(0, 400) });
  if (!res.ok) {
    throw new Error(
      `Failed ${label} (${res.status}) from ${url}. ` +
        (text ? `Response: ${text.slice(0, 300)}` : "No response body.")
    );
  }
  if (json == null) {
    throw new Error(`Invalid JSON response from ${url}`);
  }
  return json;
}

export async function fetchMatches() {
  const url = `${API_BASE}/matches`;
  return fetchJsonWithDebug(url, {}, "matches");
}

export async function fetchOpponents() {
  if (API_BASE === "/api" && typeof window !== "undefined" && window.location.hostname.includes("vercel.app")) {
    console.warn("[API] Running on Vercel with default /api base; set VITE_API_BASE to your backend URL.");
  }
  const url = `${API_BASE}/opponents`;
  return fetchJsonWithDebug(url, {}, "opponents");
}

export async function fetchLiveRecommendation(payload) {
  const url = `${API_BASE}/live/recommendation`;
  const res = await safeFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to get recommendation (${res.status}) from ${url}`);
  }
  return res.json();
}

export async function fetchAvailablePlayers(matchId) {
  const url = `${API_BASE}/live/available-players?match_id=${encodeURIComponent(matchId)}`;
  const res = await safeFetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load available players (${res.status}) from ${url}`);
  }
  return res.json();
}

export async function fetchTrainingOverview(matchId, overallMinSeconds = 180, displayMode = "numbers") {
  const url = `${API_BASE}/training/overview?match_id=${encodeURIComponent(
    matchId
  )}&overall_min_seconds=${encodeURIComponent(overallMinSeconds)}&display_mode=${encodeURIComponent(displayMode)}`;
  const res = await safeFetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load training overview (${res.status}) from ${url}`);
  }
  return res.json();
}

export async function fetchOpponentLineups(matchId, minBSeconds = 120) {
  const url = `${API_BASE}/training/opponent-lineups?match_id=${encodeURIComponent(
    matchId
  )}&min_b_seconds=${encodeURIComponent(minBSeconds)}`;
  const res = await safeFetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load opponent lineups (${res.status}) from ${url}`);
  }
  return res.json();
}

export async function fetchResponsesVsLineup(matchId, bKey, minRespSeconds = 60, displayMode = "numbers") {
  const url = `${API_BASE}/training/responses?match_id=${encodeURIComponent(
    matchId
  )}&b_key=${encodeURIComponent(bKey)}&min_resp_seconds=${encodeURIComponent(
    minRespSeconds
  )}&display_mode=${encodeURIComponent(displayMode)}`;
  const res = await safeFetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load responses (${res.status}) from ${url}`);
  }
  return res.json();
}

export async function fetchPlayersAnalytics(mode = "single", matchId = null) {
  const qs = new URLSearchParams({ mode });
  if (matchId) qs.set("match_id", String(matchId));
  const url = `${API_BASE}/players/analytics?${qs.toString()}`;
  const res = await safeFetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load players analytics (${res.status}) from ${url}`);
  }
  return res.json();
}

export async function fetchTeamInsights(
  matchId,
  overallMinSeconds = 180,
  opponentMinSeconds = 120,
  matchupMinSeconds = 60,
  displayMode = "numbers",
  lineupScope = "all",
  lineupMatchId = null
) {
  const qs = new URLSearchParams({
    match_id: String(matchId),
    overall_min_seconds: String(overallMinSeconds),
    opponent_min_seconds: String(opponentMinSeconds),
    matchup_min_seconds: String(matchupMinSeconds),
    display_mode: displayMode,
    lineup_scope: lineupScope,
  });
  if (lineupScope === "single" && lineupMatchId != null && lineupMatchId !== "") {
    qs.set("lineup_match_id", String(lineupMatchId));
  }
  const url = `${API_BASE}/insights/team?${qs.toString()}`;
  const res = await safeFetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load team insights (${res.status}) from ${url}`);
  }
  return res.json();
}
