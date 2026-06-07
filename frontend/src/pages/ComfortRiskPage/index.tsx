import { useEffect, useState } from "react";
import { listBuildings, runComfortRisk } from "../../services/api";
import type { ComfortRiskRunResponse } from "../../services/api";
import type { BuildingSummary } from "../../types";

export default function ComfortRiskPage() {
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const [buildingId, setBuildingId] = useState<number | null>(null);
  const [response, setResponse] = useState<ComfortRiskRunResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [missingInputs, setMissingInputs] = useState<string[]>([]);
  const [serverError, setServerError] = useState<string | null>(null);

  useEffect(() => {
    listBuildings().then((list) => {
      setBuildings(list);
      if (list.length > 0) setBuildingId(list[0].id);
    });
  }, []);

  useEffect(() => {
    setResponse(null);
    setMissingInputs([]);
    setServerError(null);
  }, [buildingId]);

  const handleSubmit = async () => {
    if (buildingId == null) return;
    setRunning(true);
    setMissingInputs([]);
    setServerError(null);
    setResponse(null);
    const res = await runComfortRisk(buildingId);
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
    <div className="mx-auto max-w-5xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Detect Comfort Violation Risk</h1>

      <div className="mb-4 flex items-end gap-4">
        <div className="flex-1">
          <label className="block text-sm font-medium">Building</label>
          <select
            data-testid="comfort-risk-building-selector"
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
          data-testid="comfort-risk-run-button"
          onClick={handleSubmit}
          disabled={running || buildingId == null}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {running ? "Running..." : "Run detection"}
        </button>
      </div>

      {response && (
        <div
          data-testid="comfort-risk-success-banner"
          className="mb-4 rounded border border-green-300 bg-green-50 p-3 text-sm text-green-800"
        >
          <div className="flex items-center gap-2">
            <span>Detection run completed.</span>
            <span
              data-testid="comfort-risk-decision-pill"
              className="rounded bg-green-200 px-2 py-0.5 text-xs"
            >
              {response.decision}
            </span>
          </div>
        </div>
      )}

      {missingInputs.length > 0 && (
        <div
          data-testid="comfort-risk-error-banner"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          Missing inputs:{" "}
          <span data-testid="comfort-risk-missing-inputs">
            {missingInputs.join(", ")}
          </span>
        </div>
      )}

      {serverError && !missingInputs.length && (
        <div
          data-testid="comfort-risk-error-banner"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          {serverError}
        </div>
      )}

      {response && response.decision === "pass" && (
        <div
          data-testid="comfort-risk-pass-message"
          className="rounded border border-green-200 bg-green-50 p-3 text-sm text-green-800"
        >
          All zones inside their comfort bands. No mitigation needed.
        </div>
      )}

      {response && response.alerts.length > 0 && (
        <table
          data-testid="comfort-risk-alerts-table"
          className="w-full border-collapse text-sm"
        >
          <thead>
            <tr className="border-b text-left">
              <th className="py-2">Zone</th>
              <th className="py-2">Projected °F</th>
              <th className="py-2">Band</th>
              <th className="py-2">Risk</th>
              <th className="py-2">Direction</th>
              <th className="py-2">Mitigation</th>
            </tr>
          </thead>
          <tbody>
            {response.alerts.map((a) => (
              <tr
                key={a.zone_id}
                data-testid={`comfort-risk-alert-row-${a.zone_id}`}
                className="border-b"
              >
                <td className="py-2">{a.zone_name}</td>
                <td className="py-2">{a.projected_temp_f}</td>
                <td className="py-2">
                  {a.occupied_min_f}–{a.occupied_max_f}
                </td>
                <td
                  className="py-2"
                  data-testid={`comfort-risk-score-${a.zone_id}`}
                >
                  {a.risk_score}
                </td>
                <td className="py-2">{a.direction}</td>
                <td
                  className="py-2"
                  data-testid={`comfort-risk-mitigation-${a.zone_id}`}
                >
                  {a.mitigation}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
