function normalizeApiBase(v) {
  if (v == null || v === "") return "/api";
  const s = String(v).trim().replace(/\/+$/, "");
  return s || "/api";
}

export const API_BASE = normalizeApiBase(import.meta.env.VITE_API_BASE);

async function safeFetch(url, options) {
  try {
    return await fetch(url, options);
  } catch (e) {
    throw new Error(`Network error calling ${url}: ${e.message}`);
  }
}

export async function fetchMatches() {
  const url = `${API_BASE}/matches`;
  const res = await safeFetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load matches (${res.status}) from ${url}`);
  }
  return res.json();
}

export async function fetchOpponents() {
  const url = `${API_BASE}/opponents`;
  const res = await safeFetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load opponents (${res.status}) from ${url}`);
  }
  return res.json();
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
