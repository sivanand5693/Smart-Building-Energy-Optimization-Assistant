import { useEffect, useState } from "react";
import {
  explainRecommendation,
  getLatestRecommendations,
  listBuildings,
} from "../../services/api";
import type { ExplanationResponse } from "../../services/api";
import type { BuildingSummary, SetpointRecommendation } from "../../types";

export default function ExplainPage() {
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const [buildingId, setBuildingId] = useState<number | null>(null);
  const [recommendations, setRecommendations] = useState<SetpointRecommendation[]>([]);
  const [recommendationId, setRecommendationId] = useState<number | null>(null);
  const [response, setResponse] = useState<ExplanationResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [missingInputs, setMissingInputs] = useState<string[]>([]);
  const [serverError, setServerError] = useState<string | null>(null);

  // Initial load: buildings + ?recommendation_id= query param.
  useEffect(() => {
    listBuildings().then((list) => {
      setBuildings(list);
      if (list.length > 0) setBuildingId(list[0].id);
    });
  }, []);

  // Whenever a building is chosen, refresh the recommendation list.
  useEffect(() => {
    setResponse(null);
    setMissingInputs([]);
    setServerError(null);
    if (buildingId == null) {
      setRecommendations([]);
      setRecommendationId(null);
      return;
    }
    getLatestRecommendations(buildingId).then((rows) => {
      setRecommendations(rows);
      const queried = new URLSearchParams(window.location.search).get(
        "recommendation_id",
      );
      const queriedId = queried != null ? Number(queried) : NaN;
      if (
        !Number.isNaN(queriedId) &&
        rows.some((r) => r.id === queriedId)
      ) {
        setRecommendationId(queriedId);
      } else if (rows.length > 0) {
        setRecommendationId(rows[0].id);
      } else {
        setRecommendationId(null);
      }
    });
  }, [buildingId]);

  useEffect(() => {
    setResponse(null);
    setMissingInputs([]);
    setServerError(null);
  }, [recommendationId]);

  const handleSubmit = async () => {
    if (recommendationId == null) return;
    setRunning(true);
    setMissingInputs([]);
    setServerError(null);
    setResponse(null);
    const res = await explainRecommendation(recommendationId);
    if (res.ok) {
      setResponse(res.data);
    } else if (res.status === 400) {
      setMissingInputs(res.missingInputs);
    } else {
      setServerError(res.message ?? "Server error");
    }
    setRunning(false);
  };

  return (
    <div className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Explain Recommendation</h1>

      <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-3 md:items-end">
        <div>
          <label className="block text-sm font-medium">Building</label>
          <select
            data-testid="explain-building-selector"
            value={buildingId ?? ""}
            onChange={(e) => setBuildingId(Number(e.target.value))}
            className="mt-1 w-full rounded border px-3 py-2"
          >
            {buildings.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium">Recommendation</label>
          <select
            data-testid="explain-recommendation-selector"
            value={recommendationId ?? ""}
            onChange={(e) => setRecommendationId(Number(e.target.value))}
            className="mt-1 w-full rounded border px-3 py-2"
          >
            {recommendations.map((r) => (
              <option key={r.id} value={r.id}>
                {`#${r.id} — zone ${r.zone_id} Δ${r.setpoint_delta_f}°F`}
              </option>
            ))}
          </select>
        </div>
        <button
          data-testid="explain-run-button"
          onClick={handleSubmit}
          disabled={running || recommendationId == null}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {running ? "Explaining..." : "Explain"}
        </button>
      </div>

      {response && (
        <div
          data-testid="explain-success-banner"
          className="mb-4 flex items-center gap-2 rounded border border-green-300 bg-green-50 p-3 text-sm text-green-800"
        >
          <span>Explanation generated.</span>
          <span
            data-testid="explain-model-version"
            className="rounded bg-green-200 px-2 py-0.5 text-xs"
          >
            {response.model_version}
          </span>
          {response.cached && (
            <span
              data-testid="explain-cached-pill"
              className="rounded bg-blue-200 px-2 py-0.5 text-xs text-blue-900"
            >
              cached
            </span>
          )}
        </div>
      )}

      {missingInputs.length > 0 && (
        <div
          data-testid="explain-error-banner"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          Missing inputs:{" "}
          <span data-testid="explain-missing-inputs">
            {missingInputs.join(", ")}
          </span>
        </div>
      )}

      {serverError && missingInputs.length === 0 && (
        <div
          data-testid="explain-error-banner"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          {serverError}
        </div>
      )}

      {response && (
        <div className="space-y-4">
          <div
            data-testid="explain-text"
            className="rounded border border-gray-200 bg-white p-4 text-sm leading-6"
          >
            {response.text}
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div className="rounded border border-gray-200 bg-white p-3">
              <div className="text-xs font-semibold uppercase text-gray-500">
                Energy
              </div>
              <div data-testid="explain-factor-energy" className="mt-1 text-sm">
                {response.factors.energy ?? ""}
              </div>
            </div>
            <div className="rounded border border-gray-200 bg-white p-3">
              <div className="text-xs font-semibold uppercase text-gray-500">
                Comfort
              </div>
              <div data-testid="explain-factor-comfort" className="mt-1 text-sm">
                {response.factors.comfort ?? ""}
              </div>
            </div>
            <div className="rounded border border-gray-200 bg-white p-3">
              <div className="text-xs font-semibold uppercase text-gray-500">
                Occupancy
              </div>
              <div data-testid="explain-factor-occupancy" className="mt-1 text-sm">
                {response.factors.occupancy ?? ""}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
