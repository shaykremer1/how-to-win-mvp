import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { API_BASE, API_BASE_SOURCE, fetchMatches, fetchOpponents } from "../api";

const MatchContext = createContext(null);

function groupSimpleOpponents(rows) {
  const groups = new Map();
  rows.forEach((r) => {
    const oppName = String(r?.opponent_name || "").trim();
    if (!oppName) return;
    const mid = Number(r?.match_id);
    if (!Number.isInteger(mid)) return;
    const key = oppName.toLowerCase();
    if (!groups.has(key)) {
      groups.set(key, { opponent_key: key, opponent_name: oppName, history: [] });
    }
    groups.get(key).history.push({
      match_id: mid,
      match_date: r?.match_date || null,
      match_name: null,
      final_score: null,
      point_diff: 0,
      result: "N/A",
    });
  });

  return [...groups.values()]
    .map((g) => {
      const history = [...g.history].sort((a, b) => {
        const da = a.match_date || "";
        const db = b.match_date || "";
        if (da !== db) return da < db ? 1 : -1;
        return Number(b.match_id) - Number(a.match_id);
      });
      return {
        opponent_key: g.opponent_key,
        opponent_name: g.opponent_name,
        sample_match_count: history.length,
        representative_match_id: history[0]?.match_id || 0,
        history,
      };
    })
    .sort((a, b) => a.opponent_name.localeCompare(b.opponent_name));
}

function normalizeOpponentsResponse(data) {
  if (!Array.isArray(data)) return [];
  if (data.length === 0) return [];
  const first = data[0] || {};
  if ("opponent_key" in first && "sample_match_count" in first) {
    return data;
  }
  if ("opponent_name" in first && "match_id" in first) {
    return groupSimpleOpponents(data);
  }
  return [];
}

export function MatchProvider({ children }) {
  const [opponents, setOpponents] = useState([]);
  const [selectedOpponentKey, setSelectedOpponentKey] = useState("");
  const [matchesStatus, setMatchesStatus] = useState("idle");
  const [matchesError, setMatchesError] = useState("");
  const [opponentsRawResponse, setOpponentsRawResponse] = useState(null);
  const [opponentsFetchMeta, setOpponentsFetchMeta] = useState(null);
  const [matchesProbe, setMatchesProbe] = useState({ status: "idle", count: 0, error: "" });

  useEffect(() => {
    setMatchesStatus("loading");
    setMatchesError("");
    setOpponentsRawResponse(null);
    setOpponentsFetchMeta({
      api_base: API_BASE,
      api_base_source: API_BASE_SOURCE,
      opponents_url: `${API_BASE}/opponents`,
      matches_url: `${API_BASE}/matches`,
      host: typeof window !== "undefined" ? window.location.host : "",
    });

    setMatchesProbe({ status: "loading", count: 0, error: "" });
    fetchMatches()
      .then((rows) => {
        setMatchesProbe({ status: "success", count: Array.isArray(rows) ? rows.length : 0, error: "" });
      })
      .catch((e) => {
        setMatchesProbe({ status: "error", count: 0, error: e.message });
      });

    fetchOpponents()
      .then((data) => {
        setOpponentsRawResponse(data);
        const normalized = normalizeOpponentsResponse(data);
        if (!normalized.length && Array.isArray(data) && data.length > 0) {
          setOpponents([]);
          setMatchesStatus("unexpected");
          setMatchesError("Invalid opponents response format.");
          return;
        }
        setOpponents(normalized);
        setMatchesStatus("success");
        if (normalized.length > 0) {
          setSelectedOpponentKey(String(normalized[0].opponent_key));
        }
      })
      .catch((e) => {
        setOpponents([]);
        setMatchesStatus("error");
        setMatchesError(e.message);
        setOpponentsRawResponse({ error: e.message });
      });
  }, []);

  const selectedOpponent = useMemo(
    () => opponents.find((o) => String(o.opponent_key) === String(selectedOpponentKey)) || null,
    [opponents, selectedOpponentKey]
  );

  const selectedMatchId = selectedOpponent ? String(selectedOpponent.representative_match_id) : "";

  const value = useMemo(
    () => ({
      opponents,
      selectedOpponentKey,
      setSelectedOpponentKey,
      selectedOpponent,
      selectedMatchId,
      matchesStatus,
      matchesError,
      opponentsRawResponse,
      opponentsFetchMeta,
      matchesProbe,
    }),
    [
      opponents,
      selectedOpponentKey,
      selectedOpponent,
      selectedMatchId,
      matchesStatus,
      matchesError,
      opponentsRawResponse,
      opponentsFetchMeta,
      matchesProbe,
    ]
  );

  return <MatchContext.Provider value={value}>{children}</MatchContext.Provider>;
}

export function useMatchContext() {
  const ctx = useContext(MatchContext);
  if (!ctx) {
    throw new Error("useMatchContext must be used inside MatchProvider");
  }
  return ctx;
}
