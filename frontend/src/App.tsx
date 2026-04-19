import { Navigate, Route, Routes } from "react-router-dom";
import BuildingProfilePage from "./pages/BuildingProfilePage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/register-building" replace />} />
      <Route path="/register-building" element={<BuildingProfilePage />} />
    </Routes>
  );
}
