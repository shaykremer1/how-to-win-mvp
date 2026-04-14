import React, { useEffect, useState } from "react";
import { API_BASE, fetchPlayersAnalytics } from "../api";
import DebugPanel from "../components/DebugPanel";
import { useMatchContext } from "../context/MatchContext";

function formatValueByColumn(column, raw) {
  if (raw === null || raw === undefined || raw === "") return "";

  const num = Number(raw);
  if (!Number.isFinite(num)) return String(raw);

  const keepOneDecimalCols = new Set([
    "נקודות למשחק",
    "ריבאונד למשחק",
    "אסיסטים למשחק",
    "איבודים למשחק",
    "חטיפות למשחק",
    "חסימות למשחק",
    "מדד למשחק",
    "יעילות למשחק",
    "+/- למשחק",
  ]);
  const keepTwoDecimalCols = new Set(["נקודות לדקה", "מדד לדקה", "השפעה לדקה"]);

  if (keepTwoDecimalCols.has(column)) {
    return Number.isInteger(num) ? String(num) : num.toFixed(2);
  }
  if (keepOneDecimalCols.has(column)) {
    return Number.isInteger(num) ? String(num) : num.toFixed(1);
  }

  return Number.isInteger(num) ? String(num) : num.toFixed(2);
}

function formatPlayerIdentity(row) {
  const name = String(row?.["שחקן"] || "").trim();
  const num = Number(row?.["מספר"]);
  const hasValidNumber = Number.isInteger(num) && num > 0;
  if (hasValidNumber) {
    if (/^\d+\s*-\s*/.test(name)) return name;
    if (!name || name === "-") return String(num);
    return `${num} - ${name}`;
  }
  return name || "-";
}

export default function PlayersPage() {
  const { selectedMatchId, selectedOpponent } = useMatchContext();
  const [mode, setMode] = useState("single");
  const [singleMatchId, setSingleMatchId] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const opponentHistory = Array.isArray(selectedOpponent?.history) ? selectedOpponent.history : [];
  const hasMultipleOpponentGames = Number(selectedOpponent?.sample_match_count || 0) > 1;

  useEffect(() => {
    if (!opponentHistory.length) {
      setSingleMatchId("");
      return;
    }
    setSingleMatchId((prev) => {
      if (prev && opponentHistory.some((g) => String(g.match_id) === String(prev))) {
        return prev;
      }
      return String(opponentHistory[0].match_id);
    });
  }, [selectedOpponent, opponentHistory.length]);

  const loadPlayers = async () => {
    setLoading(true);
    setError("");
    try {
      let requestMode = mode;
      let requestMatchId = null;
      if (mode === "single") {
        requestMatchId = Number(singleMatchId || selectedMatchId);
      } else if (mode === "opponent_aggregate") {
        requestMatchId = Number(selectedMatchId);
      }
      const payload = await fetchPlayersAnalytics(requestMode, requestMatchId);
      setData(payload);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const modeHelpText =
    mode === "single"
      ? "Single game: choose one specific game vs the selected opponent."
      : mode === "opponent_aggregate"
        ? "Aggregate vs this opponent: totals only across meetings vs selected opponent."
        : mode === "seasonal_aggregate"
          ? "Seasonal aggregate: totals across all available games."
          : "Average: per-game average metrics across available games.";

  const mvpMetric = mode === "average" ? "מדד למשחק" : "מדד";
  const mvpRow =
    Array.isArray(data?.rows) && data.rows.length
      ? [...data.rows].sort((a, b) => Number(b?.[mvpMetric] || 0) - Number(a?.[mvpMetric] || 0))[0]
      : null;
  const mvpName = mvpRow ? formatPlayerIdentity(mvpRow) : "-";
  const mvpValue = mvpRow ? formatValueByColumn(mvpMetric, mvpRow?.[mvpMetric]) : "-";

  useEffect(() => {
    if (mode === "single" && (singleMatchId || selectedMatchId)) {
      loadPlayers();
    } else if (mode === "opponent_aggregate" && selectedMatchId) {
      loadPlayers();
    } else if (mode === "seasonal_aggregate" || mode === "average") {
      loadPlayers();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, selectedMatchId, singleMatchId]);

  return (
    <>
      <DebugPanel
        lines={[
          { label: "Players mode", value: mode },
          { label: "API base", value: API_BASE },
          { label: "Selected opponent", value: selectedOpponent?.opponent_name || "none" },
          { label: "Sample games", value: selectedOpponent?.sample_match_count || 0 },
          { label: "Rows", value: data?.rows?.length || 0 },
          { label: "Leaders", value: data?.leaders?.length || 0 },
          { label: "Last error", value: error || "none" },
        ]}
      />

      {!selectedMatchId && (mode === "single" || mode === "opponent_aggregate") ? (
        <div className="empty-state">No selected opponent yet. Choose an opponent in Game Context above.</div>
      ) : null}

      <div className="panel">
        <h2 className="section-title">📊 Players Analytics</h2>
        <p className="empty">{modeHelpText}</p>
        <label className="field-label">Mode</label>
        <select className="input" value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="single">Single Match</option>
          <option value="opponent_aggregate">Aggregate vs This Opponent</option>
          <option value="seasonal_aggregate">Seasonal Aggregate</option>
          <option value="average">Average</option>
        </select>

        {mode === "single" ? (
          <>
            {hasMultipleOpponentGames && opponentHistory.length > 1 ? (
              <>
                <label className="field-label">Game vs selected opponent</label>
                <select className="input" value={singleMatchId} onChange={(e) => setSingleMatchId(e.target.value)}>
                  {opponentHistory.map((g) => (
                    <option key={g.match_id} value={g.match_id}>
                      {(g.match_date || "-") + " | " + (g.final_score || "N/A") + " | " + (g.result || "") + ` | #${g.match_id}`}
                    </option>
                  ))}
                </select>
              </>
            ) : (
              <div className="hint-text">
                {opponentHistory.length === 1
                  ? `Single game selected automatically: #${opponentHistory[0].match_id}`
                  : hasMultipleOpponentGames
                    ? "Multiple games detected, but history details are still loading."
                  : "No games found for selected opponent."}
              </div>
            )}
          </>
        ) : null}

        <button
          className="button"
          onClick={loadPlayers}
          disabled={
            loading ||
            (mode === "single" && !singleMatchId && !selectedMatchId) ||
            (mode === "opponent_aggregate" && !selectedMatchId)
          }
        >
          {loading ? "Loading..." : "Refresh Players Analytics"}
        </button>
      </div>

      {error ? <div className="error">{error}</div> : null}
      {!error && data?.calculation_note ? <div className="notice-box">{data.calculation_note}</div> : null}

      <section className="section">
        <h2>🏆 MVP</h2>
        {mvpRow ? (
          <div className="leader-card mvp-card">
            <div className="leader-stat">{mvpMetric}</div>
            <div className="leader-player">{mvpName}</div>
            <div className="leader-value">{mvpValue}</div>
          </div>
        ) : (
          <p className="empty">No MVP data available for current mode/sample.</p>
        )}
      </section>

      <section className="section">
        <h2>👥 Player Comparison</h2>
        {Array.isArray(data?.rows) && data.rows.length ? (
          <div className="table-wrap">
            <table className="stats-table">
              <thead>
                <tr>
                  {(data.columns || []).map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r, idx) => (
                  <tr key={`${r["שחקן"] || idx}-${idx}`}>
                    {(data.columns || []).map((c) => (
                      <td key={`${idx}-${c}`}>
                        {c === "שחקן" ? formatPlayerIdentity(r) : formatValueByColumn(c, r[c])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="empty">No player rows available for the current mode.</p>
        )}
      </section>
    </>
  );
}
