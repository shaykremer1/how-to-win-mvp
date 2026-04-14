import React, { useEffect, useMemo, useState } from "react";
import { API_BASE, fetchAvailablePlayers, fetchLiveRecommendation } from "../api";
import DebugPanel from "../components/DebugPanel";
import LineupCard from "../components/LineupCard";
import { useMatchContext } from "../context/MatchContext";

function normalizeLivePayload(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return { valid: false, recommendations: [], not_recommended: null };
  }
  return {
    valid: true,
    recommendations: Array.isArray(raw.recommendations) ? raw.recommendations : [],
    not_recommended: raw.not_recommended && typeof raw.not_recommended === "object" ? raw.not_recommended : null,
    overlap: Number(raw.overlap || 0),
    input_n: Number(raw.input_n || 0),
    chosen_b_key: raw.chosen_b_key || "",
    related_match_ids: Array.isArray(raw.related_match_ids) ? raw.related_match_ids : [],
    sample_match_count: Number(raw.sample_match_count || 0),
    previous_match_count: Number(raw.previous_match_count || 0),
    sample_context_message: raw.sample_context_message || "",
    opponent_name: raw.opponent_name || "",
    overlap_label: raw.overlap_label || "",
    used_fallback: Boolean(raw.used_fallback),
  };
}

export default function LivePage() {
  const { selectedMatchId, selectedOpponent, matchesStatus } = useMatchContext();
  const [opponentOptions, setOpponentOptions] = useState([]);
  const [selectedOpponentPlayers, setSelectedOpponentPlayers] = useState([]);
  const [availableOptions, setAvailableOptions] = useState([]);
  const [availableToday, setAvailableToday] = useState([]);
  const [displayMode, setDisplayMode] = useState("numbers");
  const [minSeconds, setMinSeconds] = useState(90);
  const [loading, setLoading] = useState(false);
  const [loadingPlayers, setLoadingPlayers] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const [playersStatus, setPlayersStatus] = useState("idle");
  const [recommendationStatus, setRecommendationStatus] = useState("idle");
  const [hasSubmittedOnce, setHasSubmittedOnce] = useState(false);

  useEffect(() => {
    if (!selectedMatchId) {
      setOpponentOptions([]);
      setSelectedOpponentPlayers([]);
      setAvailableOptions([]);
      setAvailableToday([]);
      setResult(null);
      return;
    }
    setLoadingPlayers(true);
    setPlayersStatus("loading");
    fetchAvailablePlayers(Number(selectedMatchId))
      .then((data) => {
        const ourDetails = Array.isArray(data?.players_details)
          ? data.players_details
          : (Array.isArray(data?.players) ? data.players : []).map((p) => ({
              number: p,
              label_numbers: String(p),
              label_names: String(p),
              label_both: String(p),
            }));
        const ourPlayers = ourDetails.map((d) => Number(d.number)).filter((n) => Number.isInteger(n));

        const oppDetails = Array.isArray(data?.opponent_players_details)
          ? data.opponent_players_details
          : (Array.isArray(data?.opponent_players) ? data.opponent_players : []).map((p) => ({
              number: p,
              label_numbers: String(p),
              label_names: String(p),
              label_both: String(p),
            }));

        setAvailableOptions(ourDetails);
        setOpponentOptions(oppDetails);
        setAvailableToday(ourPlayers);
        setSelectedOpponentPlayers([]);
        setHasSubmittedOnce(false);
        setResult(null);
        setPlayersStatus("success");
      })
      .catch((e) => {
        setPlayersStatus("error");
        setAvailableOptions([]);
        setOpponentOptions([]);
        setAvailableToday([]);
        setSelectedOpponentPlayers([]);
        setError(e.message);
      })
      .finally(() => setLoadingPlayers(false));
  }, [selectedMatchId]);

  const canRecommend = useMemo(() => {
    return Boolean(selectedMatchId) && selectedOpponentPlayers.length >= 3 && selectedOpponentPlayers.length <= 5 && availableToday.length >= 5;
  }, [selectedMatchId, selectedOpponentPlayers, availableToday]);

  const onToggleOpponentPlayer = (player) => {
    setSelectedOpponentPlayers((prev) => {
      if (prev.includes(player)) {
        return prev.filter((x) => x !== player);
      }
      if (prev.length >= 5) {
        return prev;
      }
      return [...prev, player].sort((a, b) => a - b);
    });
  };

  const onToggleAvailable = (player) => {
    setAvailableToday((prev) =>
      prev.includes(player) ? prev.filter((x) => x !== player) : [...prev, player].sort((a, b) => a - b)
    );
  };

  const playerLabelByMode = (playerObj) => {
    if (displayMode === "names") return playerObj.label_names || playerObj.label_numbers;
    if (displayMode === "both") return playerObj.label_both || playerObj.label_numbers;
    return playerObj.label_numbers;
  };

  const runRecommendation = async ({ clearResult = false } = {}) => {
    setError("");
    if (clearResult) {
      setResult(null);
    }
    setRecommendationStatus("loading");

    if (!selectedMatchId) {
      setError("בחר יריבה.");
      setRecommendationStatus("error");
      return;
    }
    if (selectedOpponentPlayers.length < 3 || selectedOpponentPlayers.length > 5) {
      setError("יש לבחור 3 עד 5 שחקני יריבה.");
      setRecommendationStatus("error");
      return;
    }
    if (availableToday.length < 5) {
      setError("יש לבחור לפחות 5 שחקנים זמינים אצלנו.");
      setRecommendationStatus("error");
      return;
    }

    setLoading(true);
    try {
      const raw = await fetchLiveRecommendation({
        match_id: Number(selectedMatchId),
        opponent_players: selectedOpponentPlayers,
        available_today: availableToday,
        min_seconds: Number(minSeconds),
        display_mode: displayMode,
      });
      const normalized = normalizeLivePayload(raw);
      setResult(normalized);
      if (!normalized.valid) {
        setError("פורמט ההמלצה שהתקבל אינו תקין.");
        setRecommendationStatus("error");
      } else {
        setRecommendationStatus("success");
      }
    } catch (e2) {
      setError(e2.message);
      setRecommendationStatus("error");
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setHasSubmittedOnce(true);
    runRecommendation({ clearResult: true });
  };

  useEffect(() => {
    if (!hasSubmittedOnce || !canRecommend) return;
    const timer = setTimeout(() => {
      runRecommendation();
    }, 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [minSeconds]);

  return (
    <>
      <DebugPanel
        lines={[
          { label: "Matches API status", value: matchesStatus },
          { label: "Available players status", value: playersStatus },
          { label: "Recommendation status", value: recommendationStatus },
          { label: "API base", value: API_BASE },
          { label: "Selected opponent", value: selectedOpponent?.opponent_name || "none" },
          { label: "Sample games", value: selectedOpponent?.sample_match_count || 0 },
          { label: "Opponent selected", value: selectedOpponentPlayers.length },
          { label: "Available selected", value: availableToday.length },
          { label: "Last error", value: error || "none" },
        ]}
      />

      {!selectedMatchId ? (
        <div className="empty-state">No selected opponent yet. Choose an opponent in Game Context above.</div>
      ) : null}

      <form className="panel" onSubmit={onSubmit}>
        <h2 className="section-title">🎮 Live Recommendation</h2>
        <label className="field-label">תצוגה לחמישיות שלנו</label>
        <select className="input" value={displayMode} onChange={(e) => setDisplayMode(e.target.value)}>
          <option value="numbers">Numbers</option>
          <option value="names">Names</option>
          <option value="both">Number + Name</option>
        </select>

        <label className="field-label">שחקני יריבה (בחר 3 עד 5)</label>
        <div className="chips-wrap">
          {loadingPlayers && <div className="empty">טוען שחקני יריבה...</div>}
          {!loadingPlayers &&
            opponentOptions.map((p) => {
              const num = Number(p.number);
              const selected = selectedOpponentPlayers.includes(num);
              const disabled = !selected && selectedOpponentPlayers.length >= 5;
              return (
                <button
                  key={`opp-${p.number}`}
                  type="button"
                  className={`chip ${selected ? "chip-active" : ""} ${disabled ? "chip-disabled" : ""}`}
                  disabled={disabled}
                  onClick={() => onToggleOpponentPlayer(num)}
                >
                  {p.label_numbers || p.number}
                </button>
              );
            })}
        </div>
        <div className="hint-text">Selected: {selectedOpponentPlayers.length}/5</div>

        <label className="field-label">שחקנים זמינים אצלנו</label>
        <div className="chips-wrap">
          {loadingPlayers && <div className="empty">טוען שחקנים...</div>}
          {!loadingPlayers &&
            availableOptions.map((p) => (
              <button
                key={p.number}
                type="button"
                className={`chip ${availableToday.includes(Number(p.number)) ? "chip-active" : ""}`}
                onClick={() => onToggleAvailable(Number(p.number))}
              >
                {playerLabelByMode(p)}
              </button>
            ))}
        </div>

        <button className="button" type="submit" disabled={loading || !canRecommend}>
          {loading ? "מחשב המלצה..." : "Get Recommendation"}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      {result && result.valid && (
        <>
          <section className="section">
            <h2>✅ Recommended Lineups</h2>
            <p className="sample-basis">
              Based on {result.sample_match_count || selectedOpponent?.sample_match_count || 0} game
              {(result.sample_match_count || selectedOpponent?.sample_match_count || 0) === 1 ? "" : "s"} vs this
              opponent
            </p>
            {result.recommendations.length ? (
              result.recommendations.map((item, idx) => (
                <LineupCard key={`${item.lineup}-${idx}`} item={item} tone="good" title={`Option ${idx + 1}`} />
              ))
            ) : (
              <p className="empty">לא נמצאו חמישיות מומלצות תחת הסינון הנוכחי.</p>
            )}
          </section>

          <section className="section">
            <h2>❌ Bad Lineup</h2>
            {result.not_recommended ? (
              <LineupCard
                item={result.not_recommended}
                tone="bad"
                title="Avoid This Option"
                subtitle="המערכת זיהתה חמישייה עם ביצועים חלשים מול ההרכב הזה."
              />
            ) : (
              <div className="empty-state">
                No statistically bad lineup was found under the current sample / filters.
              </div>
            )}
          </section>

          <section className="section">
            <h2>📌 Recommendation Context</h2>
            <div className="insight-box">
              <div>Opponent: {result.opponent_name || "-"}</div>
              <div>Matches in sample: {result.sample_match_count || result.related_match_ids.length}</div>
              <div>Previous meetings used: {result.previous_match_count}</div>
              <div>{result.sample_context_message || "-"}</div>
              <div>Opponent lineup matched: {result.chosen_b_key || "-"}</div>
              <div>
                Overlap quality: {result.overlap_label || `${result.overlap}/${result.input_n}`}
              </div>
              {result.used_fallback ? (
                <div className="warn-text">
                  Recommendation uses closest observed opponent lineup fallback.
                </div>
              ) : null}
            </div>
          </section>

          <section className="section">
            <h2>🎚️ Sample Tuning</h2>
            <p className="empty">Adjust minimum sample seconds after results load. Recommendations refresh automatically.</p>
            <label className="field-label">Minimum sample seconds</label>
            <input
              className="input"
              type="number"
              min={0}
              max={600}
              step={15}
              value={minSeconds}
              onChange={(e) => setMinSeconds(e.target.value)}
            />
          </section>
        </>
      )}
    </>
  );
}
