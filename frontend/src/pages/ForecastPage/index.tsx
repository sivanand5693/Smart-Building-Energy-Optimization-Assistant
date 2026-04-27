import { useEffect, useState } from "react";
import {
  getLatestForecasts,
  listBuildings,
  runForecast,
} from "../../services/api";
import type { BuildingSummary, ZoneForecast } from "../../types";

export default function ForecastsPage() {
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const [buildingId, setBuildingId] = useState<number | null>(null);
  const [forecasts, setForecasts] = useState<ZoneForecast[]>([]);
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
    getLatestForecasts(buildingId).then(setForecasts);
  }, [buildingId]);

  const handleRun = async () => {
    if (buildingId == null) return;
    setRunning(true);
    setRunOk(false);
    setMissingInputs([]);
    setGenericError(null);
    const res = await runForecast(buildingId);
    if (res.ok) {
      setForecasts(res.data.forecasts);
      setRunOk(true);
    } else {
      if (res.missingInputs.length > 0) {
        setMissingInputs(res.missingInputs);
      } else {
        setGenericError(res.message ?? "Forecast run failed");
      }
    }
    setRunning(false);
  };

  return (
    <div className="mx-auto max-w-4xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Zone Demand Forecasts</h1>

      <div className="mb-6 flex items-end gap-4">
        <div className="flex-1">
          <label className="block text-sm font-medium">Building</label>
          <select
            data-testid="forecast-building-selector"
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
          data-testid="run-forecast-button"
          onClick={handleRun}
          disabled={running || buildingId == null}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {running ? "Running..." : "Run forecast"}
        </button>
      </div>

      {runOk && (
        <div
          data-testid="forecast-run-success"
          className="mb-4 rounded border border-green-300 bg-green-50 p-3 text-sm text-green-800"
        >
          Forecast run completed.
        </div>
      )}

      {missingInputs.length > 0 && (
        <div
          data-testid="forecast-run-error"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          Missing inputs:{" "}
          <span data-testid="forecast-missing-inputs">
            {missingInputs.join(", ")}
          </span>
        </div>
      )}

      {genericError && !missingInputs.length && (
        <div
          data-testid="forecast-run-error"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          {genericError}
        </div>
      )}

      {forecasts.length > 0 && (
        <table data-testid="forecast-table" className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b text-left">
              <th className="py-2">Zone</th>
              <th className="py-2">Predicted kWh</th>
              <th className="py-2">Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {forecasts.map((f) => (
              <tr
                key={f.zone_id}
                data-testid={`forecast-row-${f.zone_id}`}
                className="border-b"
              >
                <td
                  className="py-2"
                  data-testid={`forecast-zone-name-${f.zone_id}`}
                >
                  {f.zone_name}
                </td>
                <td
                  className="py-2"
                  data-testid={`forecast-predicted-kwh-${f.zone_id}`}
                >
                  {Number(f.predicted_kwh).toFixed(2)}
                </td>
                <td
                  className="py-2"
                  data-testid={`forecast-timestamp-${f.zone_id}`}
                >
                  {f.timestamp}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
