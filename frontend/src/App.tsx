import { Navigate, Route, Routes } from "react-router-dom";
import BuildingProfilePage from "./pages/BuildingProfilePage";
import OccupancySchedulePage from "./pages/OccupancySchedulePage";
import ForecastsPage from "./pages/ForecastPage";
import RecommendationsPage from "./pages/RecommendationsPage";
import ApplyPlanPage from "./pages/ApplyPlanPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/register-building" replace />} />
      <Route path="/register-building" element={<BuildingProfilePage />} />
      <Route path="/import-occupancy" element={<OccupancySchedulePage />} />
      <Route path="/forecasts" element={<ForecastsPage />} />
      <Route path="/recommendations" element={<RecommendationsPage />} />
      <Route path="/apply-plan" element={<ApplyPlanPage />} />
    </Routes>
  );
}
