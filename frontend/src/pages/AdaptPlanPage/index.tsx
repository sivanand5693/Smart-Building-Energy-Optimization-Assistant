import { useEffect, useMemo, useState } from "react";
import {
  adaptPlan,
  getLatestRecommendations,
  listBuildings,
} from "../../services/api";
import type { AdaptPlanResponse } from "../../services/api";
import type { BuildingSummary, SetpointRecommendation } from "../../types";

export default function AdaptPlanPage() {
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const [buildingId, setBuildingId] = useState<number | null>(null);
  const [inputs, setInputs] = useState<Record<number, string>>({});
  const [response, setResponse] = useState<AdaptPlanResponse | null>(null);
  const [revisedRecs, setRevisedRecs] = useState<SetpointRecommendation[]>([]);
  const [running, setRunning] = useState(false);
  const [missingInputs, setMissingInputs] = useState<string[]>([]);
  const [serverError, setServerError] = useState<string | null>(null);

  useEffect(() => {
    listBuildings().then((list) => {
      setBuildings(list);
      if (list.length > 0) setBuildingId(list[0].id);
    });
  }, []);

  const selectedBuilding = useMemo(
    () => buildings.find((b) => b.id === buildingId) ?? null,
    [buildings, buildingId],
  );

  useEffect(() => {
    setInputs({});
    setResponse(null);
    setRevisedRecs([]);
    setMissingInputs([]);
    setServerError(null);
    if (buildingId == null) return;
    // Pre-load latest recs so the table always reflects the current plan.
    getLatestRecommendations(buildingId).then((rows) =>
      setRevisedRecs([...rows].sort((a, b) => a.rank - b.rank)),
    );
  }, [buildingId]);

  const anyInput = Object.values(inputs).some(
    (v) => v.trim() !== "" && !Number.isNaN(Number(v)),
  );

  const handleSubmit = async () => {
    if (buildingId == null) return;
    setRunning(true);
    setMissingInputs([]);
    setServerError(null);
    setResponse(null);
    const changes = Object.entries(inputs)
      .filter(([, v]) => v.trim() !== "" && !Number.isNaN(Number(v)))
      .map(([zid, v]) => ({
        zone_id: Number(zid),
        new_occupancy_count: Number(v),
      }));
    const res = await adaptPlan(buildingId, changes);
    if (res.ok) {
      setResponse(res.data);
      // Refresh the revised-recs table from /recommendations/latest so the
      // UI reflects the persisted state.
      const rows = await getLatestRecommendations(buildingId);
      setRevisedRecs([...rows].sort((a, b) => a.rank - b.rank));
    } else if (res.status === 400) {
      setMissingInputs(res.missingInputs);
    } else {
      setServerError(res.message ?? "Server error");
    }
    setRunning(false);
  };

  return (
    <div className="mx-auto max-w-5xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Adapt Plan To Occupancy Change</h1>

      <div className="mb-4 flex items-end gap-4">
        <div className="flex-1">
          <label className="block text-sm font-medium">Building</label>
          <select
            data-testid="adapt-building-selector"
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
          data-testid="adapt-run-button"
          onClick={handleSubmit}
          disabled={running || buildingId == null || !anyInput}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {running ? "Submitting..." : "Submit adapt"}
        </button>
      </div>

      {selectedBuilding && (
        <table className="mb-6 w-full border-collapse text-sm">
          <thead>
            <tr className="border-b text-left">
              <th className="py-2">Zone</th>
              <th className="py-2">New occupancy count</th>
            </tr>
          </thead>
          <tbody>
            {selectedBuilding.zones.map((z) => (
              <tr
                key={z.id}
                data-testid={`adapt-zone-row-${z.id}`}
                className="border-b"
              >
                <td className="py-2">{z.name}</td>
                <td className="py-2">
                  <input
                    type="number"
                    data-testid={`adapt-occupancy-input-${z.id}`}
                    value={inputs[z.id] ?? ""}
                    onChange={(e) =>
                      setInputs({ ...inputs, [z.id]: e.target.value })
                    }
                    className="w-32 rounded border px-2 py-1"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {response && (
        <div
          data-testid="adapt-success-banner"
          className="mb-4 rounded border border-green-300 bg-green-50 p-3 text-sm text-green-800"
        >
          <div className="flex items-center gap-2">
            <span>Adapt completed.</span>
            <span
              data-testid="adapt-decision-pill"
              className="rounded bg-green-200 px-2 py-0.5 text-xs"
            >
              {response.decision}
            </span>
          </div>
          <div data-testid="adapt-reason-text" className="mt-1 text-xs">
            {response.reason}
          </div>
          {response.changed_zone_ids.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {response.changed_zone_ids.map((zid) => (
                <span
                  key={zid}
                  data-testid={`adapt-changed-zone-${zid}`}
                  className="rounded bg-amber-200 px-2 py-0.5 text-xs"
                >
                  {selectedBuilding?.zones.find((z) => z.id === zid)?.name ??
                    `zone ${zid}`}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {missingInputs.length > 0 && (
        <div
          data-testid="adapt-error-banner"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          Missing inputs:{" "}
          <span data-testid="adapt-missing-inputs">
            {missingInputs.join(", ")}
          </span>
        </div>
      )}

      {serverError && !missingInputs.length && (
        <div
          data-testid="adapt-error-banner"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          {serverError}
        </div>
      )}

      {revisedRecs.length > 0 && (
        <table
          data-testid="adapt-revised-recs-table"
          className="w-full border-collapse text-sm"
        >
          <thead>
            <tr className="border-b text-left">
              <th className="py-2">Rank</th>
              <th className="py-2">Zone</th>
              <th className="py-2">Δ°F</th>
              <th className="py-2">Savings (kWh)</th>
            </tr>
          </thead>
          <tbody>
            {revisedRecs.map((r) => (
              <tr
                key={r.rank}
                data-testid={`adapt-revised-rec-row-${r.rank}`}
                className="border-b"
              >
                <td className="py-2">{r.rank}</td>
                <td className="py-2">{r.zone_name}</td>
                <td className="py-2">{Number(r.setpoint_delta_f).toFixed(1)}</td>
                <td className="py-2">{r.projected_savings_kwh}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
