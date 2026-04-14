import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import { MatchProvider } from "./context/MatchContext";
import LivePage from "./pages/LivePage";
import PlaceholderPage from "./pages/PlaceholderPage";
import PlayersPage from "./pages/PlayersPage";
import TeamInsightsPage from "./pages/TeamInsightsPage";
import TrainingPage from "./pages/TrainingPage";

export default function App() {
  return (
    <MatchProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/live" replace />} />
          <Route path="/live" element={<LivePage />} />
          <Route path="/training" element={<TrainingPage />} />
          <Route path="/players" element={<PlayersPage />} />
          <Route path="/insights" element={<TeamInsightsPage />} />
          <Route
            path="/admin"
            element={
              <PlaceholderPage
                title="⚙️ Admin / Data"
                description="Admin shell ready. Next pass will connect import/manage/export flows."
              />
            }
          />
        </Route>
      </Routes>
    </MatchProvider>
  );
}
