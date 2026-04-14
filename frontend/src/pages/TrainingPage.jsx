import React, { useEffect, useMemo, useState } from "react";
import {
  API_BASE,
  fetchOpponentLineups,
  fetchResponsesVsLineup,
  fetchTrainingOverview,
} from "../api";
import DebugPanel from "../components/DebugPanel";
import LineupCard from "../components/LineupCard";
import { useMatchContext } from "../context/MatchContext";

export default function TrainingPage() {
  const { selectedMatchId, selectedOpponent } = useMatchContext();
  const [minBSeconds, setMinBSeconds] = useState(120);
  const [minRespSeconds, setMinRespSeconds] = useState(60);
  const [overallMinSeconds, setOverallMinSeconds] = useState(180);

  const [overview, setOverview] = useState(null);
  const [opponentLineups, setOpponentLineups] = useState([]);
  const [chosenB, setChosenB] = useState("");
  const [responses, setResponses] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [status, setStatus] = useState("idle");

  const selectedMatchIdNum = useMemo(() => Number(selectedMatchId), [selectedMatchId]);

  const loadTraining = async () => {
    if (!selectedMatchIdNum) {
      setError("בחר משחק");
      return;
    }
    setLoading(true);
    setError("");
    setNotice("");
    setStatus("loading");
    try {
      const [overviewData, lineupsData] = await Promise.all([
        fetchTrainingOverview(selectedMatchIdNum, Number(overallMinSeconds), "numbers"),
        fetchOpponentLineups(selectedMatchIdNum, Number(minBSeconds)),
      ]);

      const lineups = Array.isArray(lineupsData?.lineups) ? lineupsData.lineups : [];
      setOverview(overviewData || null);
      setOpponentLineups(lineups);

      let bKey = chosenB;
      if (!bKey && lineups.length > 0) {
        bKey = lineups[0].lineup;
        setChosenB(bKey);
      }

      if (bKey) {
        const responsesData = await fetchResponsesVsLineup(selectedMatchIdNum, bKey, Number(minRespSeconds), "numbers");
        setResponses(responsesData || null);
        setNotice(responsesData?.message || "");
      } else {
        setResponses(null);
        setNotice("לא נמצאה חמישיית יריבה מתאימה לפי הספים שנבחרו.");
      }
      setStatus("success");
    } catch (e) {
      setStatus("error");
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedMatchId) {
      loadTraining();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMatchId]);

  const onRefresh = (e) => {
    e.preventDefault();
    loadTraining();
  };

  const onSelectB = async (bKey) => {
    setChosenB(bKey);
    if (!selectedMatchIdNum) return;
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const responsesData = await fetchResponsesVsLineup(selectedMatchIdNum, bKey, Number(minRespSeconds), "numbers");
      setResponses(responsesData || null);
      setNotice(responsesData?.message || "");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const hasRealFailure = Boolean(error);
  const hasValidEmptyResponses =
    !hasRealFailure &&
    status === "success" &&
    responses &&
    Array.isArray(responses.best_responses) &&
    responses.best_responses.length === 0;

  const isFallbackSelectedSummary =
    !hasRealFailure &&
    responses?.selected_b_summary &&
    Number(responses.selected_b_summary.minutes || 0) === 0 &&
    Number(responses.selected_b_summary.diff_total || 0) === 0 &&
    Number(responses.selected_b_summary.diff_per_min || 0) === 0;

  return (
    <>
      <DebugPanel
        lines={[
          { label: "Training status", value: status },
          { label: "API base", value: API_BASE },
          { label: "Selected opponent", value: selectedOpponent?.opponent_name || "none" },
          { label: "Sample games", value: selectedOpponent?.sample_match_count || 0 },
          { label: "Opponent lineups count", value: opponentLineups.length },
          { label: "Has responses", value: responses ? "yes" : "no" },
          { label: "Valid empty responses", value: hasValidEmptyResponses ? "yes" : "no" },
          { label: "Last error", value: error || "none" },
          { label: "Notice", value: notice || "none" },
        ]}
      />

      {!selectedMatchId ? (
        <div className="empty-state">No selected opponent yet. Choose an opponent in Game Context above.</div>
      ) : null}

      <form className="panel" onSubmit={onRefresh}>
        <h2 className="section-title">🏋️ Training Flow</h2>
        <div className="grid">
          <div>
            <label className="field-label">מינ' זמן חמישיית יריבה</label>
            <input
              className="input"
              type="number"
              min={0}
              step={15}
              value={minBSeconds}
              onChange={(e) => setMinBSeconds(e.target.value)}
            />
          </div>
          <div>
            <label className="field-label">מינ' זמן תגובה שלנו</label>
            <input
              className="input"
              type="number"
              min={0}
              step={15}
              value={minRespSeconds}
              onChange={(e) => setMinRespSeconds(e.target.value)}
            />
          </div>
        </div>

        <label className="field-label">מינ' זמן לחמישייה הטובה הכוללת</label>
        <input
          className="input"
          type="number"
          min={0}
          step={30}
          value={overallMinSeconds}
          onChange={(e) => setOverallMinSeconds(e.target.value)}
        />

        <button className="button" type="submit" disabled={loading || !selectedMatchId}>
          {loading ? "מעדכן תובנות..." : "Refresh Training Insights"}
        </button>
      </form>

      {hasRealFailure && <div className="error">{error}</div>}
      {!hasRealFailure && notice && <div className="notice-box">{notice}</div>}

      <section className="section">
        <h2>⭐ Overall Best Lineup</h2>
        <p className="sample-basis">
          Based on {overview?.related_match_ids?.length || selectedOpponent?.sample_match_count || 0} game
          {(overview?.related_match_ids?.length || selectedOpponent?.sample_match_count || 0) === 1 ? "" : "s"} vs this
          opponent
        </p>
        {overview?.best_overall ? (
          <LineupCard
            item={overview.best_overall}
            tone="good"
            title="Best Overall"
            subtitle="לפי כלל המשחקים מול היריבה"
          />
        ) : (
          <p className="empty">לא נמצאה חמישייה כוללת שעומדת בסף הזמן.</p>
        )}
      </section>

      <section className="section">
        <h2>⚠️ Opponent Strongest Lineups</h2>
        {opponentLineups.length ? (
          <>
            <div className="chips-wrap">
              {opponentLineups.slice(0, 10).map((l) => (
                <button
                  key={l.lineup}
                  type="button"
                  className={`chip ${chosenB === l.lineup ? "chip-active" : ""}`}
                  onClick={() => onSelectB(l.lineup)}
                >
                  {l.lineup}
                </button>
              ))}
            </div>
            {opponentLineups.slice(0, 5).map((l, idx) => (
              <LineupCard
                key={`${l.lineup}-${idx}`}
                item={l}
                tone={l.diff_per_min < 0 ? "bad" : "neutral"}
                title={`Opponent #${idx + 1}`}
                subtitle="Diff שלילי אומר שהם עדיפים נגדנו"
              />
            ))}
          </>
        ) : (
          <p className="empty">לא נמצאו חמישיות יריבה בסף הזמן שנבחר.</p>
        )}
      </section>

      <section className="section">
        <h2>🎯 Best Responses vs Selected Opponent Lineup</h2>
        {responses?.selected_b_summary ? (
          <LineupCard
            item={responses.selected_b_summary}
            tone={responses.selected_b_summary.diff_per_min < 0 ? "bad" : "neutral"}
            title={`Selected Opponent: ${responses.selected_b_key}`}
            subtitle={
              isFallbackSelectedSummary
                ? "Sample summary unavailable for this lineup under current filters."
                : undefined
            }
          />
        ) : null}

        {Array.isArray(responses?.best_responses) && responses.best_responses.length ? (
          responses.best_responses.map((r, idx) => (
            <LineupCard
              key={`${r.lineup}-${idx}`}
              item={r}
              tone={r.diff_per_min > 0 ? "good" : "neutral"}
              title={`Response ${idx + 1}`}
            />
          ))
        ) : (
          <div className="empty-state">
            {hasRealFailure
              ? "לא ניתן לטעון תגובות כרגע בגלל שגיאת שרת."
              : notice || "אין תגובות מספיקות מול החמישייה שנבחרה בסף הזמן הנוכחי."}
          </div>
        )}
      </section>
    </>
  );
}
