import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { fetchOpponents } from "../api";

const MatchContext = createContext(null);

export function MatchProvider({ children }) {
  const [opponents, setOpponents] = useState([]);
  const [selectedOpponentKey, setSelectedOpponentKey] = useState("");
  const [matchesStatus, setMatchesStatus] = useState("idle");
  const [matchesError, setMatchesError] = useState("");

  useEffect(() => {
    setMatchesStatus("loading");
    fetchOpponents()
      .then((data) => {
        if (!Array.isArray(data)) {
          setOpponents([]);
          setMatchesStatus("unexpected");
          setMatchesError("Invalid opponents response format.");
          return;
        }
        setOpponents(data);
        setMatchesStatus("success");
        if (data.length > 0) {
          setSelectedOpponentKey(String(data[0].opponent_key));
        }
      })
      .catch((e) => {
        setOpponents([]);
        setMatchesStatus("error");
        setMatchesError(e.message);
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
    }),
    [opponents, selectedOpponentKey, selectedOpponent, selectedMatchId, matchesStatus, matchesError]
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
