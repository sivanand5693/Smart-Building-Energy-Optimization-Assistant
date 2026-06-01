import { useEffect, useState } from "react";
import {
  getLatestRecommendations,
  listBuildings,
  runRecommendations,
} from "../../services/api";
import type { BuildingSummary, SetpointRecommendation } from "../../types";

export default function RecommendationsPage() {
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const [buildingId, setBuildingId] = useState<number | null>(null);
  const [rows, setRows] = useState<SetpointRecommendation[]>([]);
  const [running, setRunning] = useState(false);
  const [runOk, setRunOk] = useState(false);
  const [missingInputs, setMissingInputs] = useState<string[]>([]);
  const [genericError, setGenericError] = useState<string | null>(null);

  useEffect(() => {
    listBuildings().then((list) => {
      setBuildings(list);
      if (list.length > 0) setBuildingId(list[0].id);
    });
  }, []);

  useEffect(() => {
    if (buildingId == null) return;
    getLatestRecommendations(buildingId).then(setRows);
  }, [buildingId]);

  const handleRun = async () => {
    if (buildingId == null) return;
    setRunning(true);
    setRunOk(false);
    setMissingInputs([]);
    setGenericError(null);
    const res = await runRecommendations(buildingId);
    if (res.ok) {
      const sorted = [...res.data.recommendations].sort(
        (a, b) => a.rank - b.rank,
      );
      setRows(sorted);
      setRunOk(true);
    } else {
      if (res.missingInputs.length > 0) {
        setMissingInputs(res.missingInputs);
      } else {
        setGenericError(res.message ?? "Recommendation run failed");
      }
    }
    setRunning(false);
  };

  return (
    <div className="mx-auto max-w-4xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">HVAC Setpoint Recommendations</h1>

      <div className="mb-6 flex items-end gap-4">
        <div className="flex-1">
          <label className="block text-sm font-medium">Building</label>
          <select
            data-testid="recommendation-building-selector"
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
        <button
          data-testid="recommendation-run-button"
          onClick={handleRun}
          disabled={running || buildingId == null}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {running ? "Running..." : "Run recommendations"}
        </button>
      </div>

      {runOk && (
        <div
          data-testid="recommendation-run-success"
          className="mb-4 rounded border border-green-300 bg-green-50 p-3 text-sm text-green-800"
        >
          Recommendation run completed.
        </div>
      )}

      {missingInputs.length > 0 && (
        <div
          data-testid="recommendation-run-error"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          Missing inputs:{" "}
          <span data-testid="recommendation-missing-inputs">
            {missingInputs.join(", ")}
          </span>
        </div>
      )}

      {genericError && !missingInputs.length && (
        <div
          data-testid="recommendation-run-error"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          {genericError}
        </div>
      )}

      {rows.length > 0 && (
        <table data-testid="recommendation-table" className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b text-left">
              <th className="py-2">Rank</th>
              <th className="py-2">Zone</th>
              <th className="py-2">Setpoint Δ°F</th>
              <th className="py-2">Projected savings (kWh)</th>
              <th className="py-2">Comfort impact</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.rank}
                data-testid={`recommendation-row-${r.rank}`}
                className="border-b"
              >
                <td className="py-2">{r.rank}</td>
                <td
                  className="py-2"
                  data-testid={`recommendation-zone-name-${r.rank}`}
                >
                  {r.zone_name}
                </td>
                <td
                  className="py-2"
                  data-testid={`recommendation-setpoint-delta-${r.rank}`}
                >
                  {Number(r.setpoint_delta_f).toFixed(1)}
                </td>
                <td
                  className="py-2"
                  data-testid={`recommendation-projected-savings-${r.rank}`}
                >
                  {Number(r.projected_savings_kwh).toFixed(2)}
                </td>
                <td
                  className="py-2"
                  data-testid={`recommendation-comfort-impact-${r.rank}`}
                >
                  {r.comfort_impact}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
