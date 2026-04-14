import React, { useEffect, useMemo, useState } from "react";
import { API_BASE, fetchTeamInsights } from "../api";
import DebugPanel from "../components/DebugPanel";
import { useMatchContext } from "../context/MatchContext";

function minutesToClock(m) {
  const total = Math.round(Number(m || 0) * 60);
  const mm = Math.floor(total / 60);
  const ss = total % 60;
  return `${mm}:${String(ss).padStart(2, "0")}`;
}

function formatPts(v) {
  if (v == null) return "—";
  return Number(v).toFixed(0);
}

export default function TeamInsightsPage() {
  const { selectedMatchId, selectedOpponent } = useMatchContext();
  const [overallMinSeconds, setOverallMinSeconds] = useState(180);
  const [opponentMinSeconds, setOpponentMinSeconds] = useState(120);
  const [matchupMinSeconds, setMatchupMinSeconds] = useState(60);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lineupSort, setLineupSort] = useState({ key: "pts_for", dir: "desc" });
  const [lineupScope, setLineupScope] = useState("all");
  const [lineupSingleMatchId, setLineupSingleMatchId] = useState("");
  const [lineupSide, setLineupSide] = useState("our");

  const opponentHistory = Array.isArray(selectedOpponent?.history) ? selectedOpponent.history : [];
  const hasMultipleOpponentGames = Number(selectedOpponent?.sample_match_count || 0) > 1;

  useEffect(() => {
    const history = Array.isArray(selectedOpponent?.history) ? selectedOpponent.history : [];
    if (!history.length) {
      setLineupSingleMatchId("");
      return;
    }
    setLineupSingleMatchId((prev) => {
      if (prev && history.some((g) => String(g.match_id) === String(prev))) {
        return prev;
      }
      if (selectedMatchId && history.some((g) => String(g.match_id) === String(selectedMatchId))) {
        return String(selectedMatchId);
      }
      return String(history[0].match_id);
    });
  }, [selectedOpponent, selectedMatchId]);

  const loadInsights = async () => {
    if (!selectedMatchId) return;
    setLoading(true);
    setError("");
    try {
      const lineupMatchParam =
        lineupScope === "single" && lineupSingleMatchId ? Number(lineupSingleMatchId) : null;
      const payload = await fetchTeamInsights(
        Number(selectedMatchId),
        Number(overallMinSeconds),
        Number(opponentMinSeconds),
        Number(matchupMinSeconds),
        "numbers",
        lineupScope,
        lineupMatchParam
      );
      setData(payload);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedMatchId) loadInsights();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMatchId, lineupScope, lineupSingleMatchId]);

  const lineupRowsRaw = useMemo(() => {
    if (lineupSide === "our") {
      return Array.isArray(data?.lineup_table_our) ? data.lineup_table_our : [];
    }
    return Array.isArray(data?.lineup_table_opponent) ? data.lineup_table_opponent : [];
  }, [data, lineupSide]);

  const sortedLineupTable = useMemo(() => {
    const rows = [...lineupRowsRaw];
    const { key, dir } = lineupSort;
    const mult = dir === "desc" ? -1 : 1;
    const val = (row) => {
      switch (key) {
        case "minutes":
          return Number(row.minutes || 0);
        case "pts_for":
          return row.pts_for == null ? (dir === "desc" ? -1e12 : 1e12) : Number(row.pts_for);
        case "pts_against":
          return row.pts_against == null ? (dir === "desc" ? -1e12 : 1e12) : Number(row.pts_against);
        case "fg2_attempts":
          return Number(row.fg2_attempts || 0);
        case "fg3_attempts":
          return Number(row.fg3_attempts || 0);
        case "plus_minus":
          return Number(row.plus_minus || 0);
        case "efficiency":
          return Number(row.efficiency || 0);
        case "lineup_display":
          return String(row.lineup_display || "");
        default:
          return row.pts_for == null ? (dir === "desc" ? -1e12 : 1e12) : Number(row.pts_for);
      }
    };
    rows.sort((a, b) => {
      const va = val(a);
      const vb = val(b);
      if (typeof va === "string" && typeof vb === "string") {
        const c = va.localeCompare(vb);
        if (c !== 0) return mult * c;
      } else if (va !== vb) {
        return mult * (va < vb ? -1 : 1);
      }
      return String(a.lineup_key || "").localeCompare(String(b.lineup_key || ""));
    });
    return rows;
  }, [lineupRowsRaw, lineupSort]);

  const toggleLineupSort = (key) => {
    setLineupSort((prev) => {
      if (prev.key === key) {
        return { key, dir: prev.dir === "desc" ? "asc" : "desc" };
      }
      return { key, dir: key === "lineup_display" ? "asc" : "desc" };
    });
  };

  const thSort = (key, label, extraClass = "") => {
    const active = lineupSort.key === key;
    const arrow = active ? (lineupSort.dir === "desc" ? " ▼" : " ▲") : "";
    return (
      <th
        scope="col"
        className={`lineups-th sortable ${active ? "sorted-col" : ""} ${extraClass}`.trim()}
        onClick={() => toggleLineupSort(key)}
      >
        {label}
        {arrow}
      </th>
    );
  };

  return (
    <>
      <DebugPanel
        lines={[
          { label: "API base", value: API_BASE },
          { label: "Selected opponent", value: selectedOpponent?.opponent_name || "none" },
          { label: "Sample games", value: selectedOpponent?.sample_match_count || 0 },
          { label: "Lineups (our)", value: data?.lineup_table_our?.length || 0 },
          { label: "Lineups (opp)", value: data?.lineup_table_opponent?.length || 0 },
          { label: "PBP for lineups", value: data?.lineup_table_pbp_available ? "yes" : "no" },
          { label: "Lineup scope", value: `${lineupScope}${lineupScope === "single" ? ` #${lineupSingleMatchId}` : ""}` },
          { label: "Last error", value: error || "none" },
        ]}
      />

      {!selectedMatchId ? (
        <div className="empty-state">No selected opponent yet. Choose an opponent in Game Context above.</div>
      ) : null}

      <div className="panel">
        <h2 className="section-title">🏀 Team / Matchup Insights</h2>
        <div className="grid">
          <div>
            <label className="field-label">Overall Min Seconds</label>
            <input
              className="input"
              type="number"
              min={0}
              step={30}
              value={overallMinSeconds}
              onChange={(e) => setOverallMinSeconds(e.target.value)}
            />
          </div>
          <div>
            <label className="field-label">Opponent Min Seconds</label>
            <input
              className="input"
              type="number"
              min={0}
              step={15}
              value={opponentMinSeconds}
              onChange={(e) => setOpponentMinSeconds(e.target.value)}
            />
          </div>
        </div>

        <label className="field-label">Matchup Min Seconds</label>
        <input
          className="input"
          type="number"
          min={0}
          step={15}
          value={matchupMinSeconds}
          onChange={(e) => setMatchupMinSeconds(e.target.value)}
        />

        <button className="button" onClick={loadInsights} disabled={loading || !selectedMatchId}>
          {loading ? "Loading..." : "Refresh Team Insights"}
        </button>
      </div>

      {error ? <div className="error">{error}</div> : null}

      <section className="section lineups-section">
        <h2 className="lineups-section-title">Lineups</h2>

        <div className="lineups-toolbar">
          <div className="lineups-toolbar-row">
            <label className="field-label">Matchup</label>
            <select
              className="input"
              value={lineupScope}
              onChange={(e) => setLineupScope(e.target.value)}
              disabled={loading || !selectedMatchId}
            >
              <option value="all">All matchups vs this opponent</option>
              <option value="single">Single game</option>
            </select>
          </div>
          {lineupScope === "single" ? (
            <div className="lineups-toolbar-row">
              {hasMultipleOpponentGames && opponentHistory.length > 1 ? (
                <>
                  <label className="field-label">Game vs selected opponent</label>
                  <select
                    className="input"
                    value={lineupSingleMatchId}
                    onChange={(e) => setLineupSingleMatchId(e.target.value)}
                    disabled={loading || !selectedMatchId}
                  >
                    {opponentHistory.map((g) => (
                      <option key={g.match_id} value={g.match_id}>
                        {(g.match_date || "-") +
                          " | " +
                          (g.final_score || "N/A") +
                          " | " +
                          (g.result || "") +
                          ` | #${g.match_id}`}
                      </option>
                    ))}
                  </select>
                </>
              ) : (
                <div className="hint-text">
                  {opponentHistory.length === 1
                    ? `Single game in sample: #${opponentHistory[0].match_id}`
                    : hasMultipleOpponentGames
                      ? "Multiple games detected, but history details are still loading."
                      : "No games found for selected opponent."}
                </div>
              )}
            </div>
          ) : null}
        </div>

        <div className="lineups-side-tabs">
          <button
            type="button"
            className={`lineups-side-tab ${lineupSide === "our" ? "active" : ""}`}
            onClick={() => setLineupSide("our")}
          >
            Our lineups
          </button>
          <button
            type="button"
            className={`lineups-side-tab ${lineupSide === "opponent" ? "active" : ""}`}
            onClick={() => setLineupSide("opponent")}
          >
            Opponent lineups
          </button>
        </div>

        <p className="section-hint">
          {lineupScope === "all"
            ? "Totals across every game in the opponent sample that matches Game Context."
            : "Totals for the selected game only."}{" "}
          Only units with at least &quot;Overall Min Seconds&quot; on the floor are listed (same cutoff as Best Overall
          Lineups). Minutes, +/-, and EFF come from stint totals. PTS, OPP, and FGA come from play-by-play when{" "}
          <code className="inline-code">{"pbp_debug_{match_id}.csv"}</code> exists for games in this view.
        </p>
        {!data?.lineup_table_pbp_available && lineupRowsRaw.length ? (
          <p className="probe">
            PBP files missing for this scope — minutes, +/-, and EFF still shown; PTS / OPP / FGA are unavailable.
          </p>
        ) : null}
        {lineupRowsRaw.length ? (
          <div className="lineups-table-wrap">
            <table className="lineups-table">
              <thead>
                <tr>
                  {thSort("lineup_display", "Lineup", "lineup-col")}
                  {thSort("minutes", "MIN")}
                  {thSort("pts_for", "PTS")}
                  {thSort("pts_against", "OPP")}
                  {thSort("fg2_attempts", "2PA")}
                  {thSort("fg3_attempts", "3PA")}
                  {thSort("plus_minus", "+/-")}
                  {thSort("efficiency", "EFF")}
                </tr>
              </thead>
              <tbody>
                {sortedLineupTable.map((row) => (
                  <tr key={row.lineup_key}>
                    <td
                      className={`lineups-td lineup-cell ${lineupSort.key === "lineup_display" ? "sorted-cell" : ""}`}
                    >
                      <div className="lineup-chip-row">
                        {(row.player_numbers || []).map((n) => (
                          <span
                            key={n}
                            className={`lineup-chip ${lineupSide === "opponent" ? "lineup-chip-opp" : ""}`}
                          >
                            {n}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className={`lineups-td num ${lineupSort.key === "minutes" ? "sorted-cell" : ""}`}>
                      {minutesToClock(row.minutes)}
                    </td>
                    <td className={`lineups-td num ${lineupSort.key === "pts_for" ? "sorted-cell" : ""}`}>
                      {formatPts(row.pts_for)}
                    </td>
                    <td className={`lineups-td num ${lineupSort.key === "pts_against" ? "sorted-cell" : ""}`}>
                      {formatPts(row.pts_against)}
                    </td>
                    <td className={`lineups-td num ${lineupSort.key === "fg2_attempts" ? "sorted-cell" : ""}`}>
                      {row.fg2_attempts ?? 0}
                    </td>
                    <td className={`lineups-td num ${lineupSort.key === "fg3_attempts" ? "sorted-cell" : ""}`}>
                      {row.fg3_attempts ?? 0}
                    </td>
                    <td className={`lineups-td num ${lineupSort.key === "plus_minus" ? "sorted-cell" : ""}`}>
                      {Number(row.plus_minus).toFixed(0)}
                    </td>
                    <td className={`lineups-td num ${lineupSort.key === "efficiency" ? "sorted-cell" : ""}`}>
                      {Number(row.efficiency).toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="empty">No lineup rows for this threshold — try lowering overall min seconds.</p>
        )}
      </section>
    </>
  );
}
