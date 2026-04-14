import React from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useMatchContext } from "../context/MatchContext";

const NAV_ITEMS = [
  { to: "/live", label: "Live" },
  { to: "/training", label: "Training" },
  { to: "/players", label: "Players" },
  { to: "/insights", label: "Team Insights" },
  { to: "/admin", label: "Admin" },
];

export default function AppShell() {
  const {
    opponents,
    selectedOpponentKey,
    setSelectedOpponentKey,
    selectedOpponent,
    matchesStatus,
    matchesError,
  } = useMatchContext();

  return (
    <main className="container">
      <div className="probe">UI Render Test: OK</div>
      <h1>🎯 How To Win</h1>
      <p className="subtitle">עוזר החלטות בזמן אמת לצוות מקצועי</p>
      <section className="panel">
        <h2 className="section-title">🎮 Game Context</h2>
        <label className="field-label">Selected Opponent</label>
        <select
          className="input"
          value={selectedOpponentKey}
          onChange={(e) => setSelectedOpponentKey(e.target.value)}
          disabled={!opponents.length}
        >
          {!opponents.length ? <option value="">No opponents available</option> : null}
          {opponents.map((opp) => (
            <option key={opp.opponent_key} value={opp.opponent_key}>
              {opp.opponent_name}
            </option>
          ))}
        </select>
        <div className="debug-line">Matches status: {matchesStatus}</div>
        <div className="debug-line">Selected opponent: {selectedOpponent?.opponent_name || "none"}</div>
        <div className="debug-line">Sample games: {selectedOpponent?.sample_match_count || 0}</div>
        {matchesError ? <div className="error">{matchesError}</div> : null}
        {selectedOpponent ? (
          <div className="history-panel">
            <h3 className="section-subtitle">Previous games vs {selectedOpponent.opponent_name}</h3>
            <div className="history-caption">Score shown as Our-Opponent</div>
            <div className="history-list">
              {selectedOpponent.history.map((game) => (
                <div className="history-row" key={game.match_id}>
                  <span>{game.match_date || "—"}</span>
                  <span>{game.final_score || "Score unavailable"}</span>
                  <span className={Number(game.point_diff) >= 0 ? "text-good" : "text-bad"}>
                    {game.result} ({Number(game.point_diff) > 0 ? "+" : ""}
                    {Number(game.point_diff).toFixed(0)})
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </section>
      <nav className="top-nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </main>
  );
}
