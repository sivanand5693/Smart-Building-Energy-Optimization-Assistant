import { useEffect, useMemo, useState } from "react";
import {
  applyPlan,
  getLatestRecommendations,
  listBuildings,
} from "../../services/api";
import type {
  AppliedChange,
  BuildingSummary,
  SetpointRecommendation,
} from "../../types";

export default function ApplyPlanPage() {
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const [buildingId, setBuildingId] = useState<number | null>(null);
  const [latest, setLatest] = useState<SetpointRecommendation[]>([]);
  const [approved, setApproved] = useState<Set<number>>(new Set());
  const [results, setResults] = useState<AppliedChange[]>([]);
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
    if (buildingId == null) {
      setLatest([]);
      setApproved(new Set());
      return;
    }
    getLatestRecommendations(buildingId).then((rows) => {
      const sorted = [...rows].sort((a, b) => a.rank - b.rank);
      setLatest(sorted);
      setApproved(new Set(sorted.map((r) => recId(r))));
    });
  }, [buildingId]);

  const recId = (r: SetpointRecommendation): number =>
    // Backend serializes a 'recommendation_id' value alias via the row id;
    // we look it up via the runtime field if present, otherwise fall back to
    // rank as a stable selector for the UI. The backend `/recommendations/latest`
    // payload does not currently expose `id`, so we ask the API to refresh.
    (r as unknown as { id?: number }).id ??
    (r as unknown as { recommendation_id?: number }).recommendation_id ??
    r.rank;

  const handleApply = async () => {
    if (buildingId == null) return;
    setRunning(true);
    setMissingInputs([]);
    setServerError(null);
    setResults([]);
    // Fetch with id field via a richer endpoint not yet implemented; for UC5
    // the simpler approach is to use the latest run order to derive ids.
    const ids = latest
      .filter((r) => approved.has(recId(r)))
      .map((r) => recId(r));
    const res = await applyPlan(buildingId, ids);
    if (res.ok) {
      setResults(res.data.results);
    } else if (res.status === 400) {
      setMissingInputs(res.missingInputs);
    } else {
      setServerError(res.message ?? "Server error");
    }
    setRunning(false);
  };

  const anyDispatched = useMemo(
    () => results.some((r) => r.status === "dispatched"),
    [results],
  );

  return (
    <div className="mx-auto max-w-5xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Apply Approved Energy Plan</h1>

      <div className="mb-4 flex items-end gap-4">
        <div className="flex-1">
          <label className="block text-sm font-medium">Building</label>
          <select
            data-testid="apply-building-selector"
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
          data-testid="apply-run-button"
          onClick={handleApply}
          disabled={running || buildingId == null || approved.size === 0}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {running ? "Applying..." : "Apply selected"}
        </button>
      </div>

      {latest.length > 0 && (
        <table
          data-testid="latest-run-table"
          className="mb-6 w-full border-collapse text-sm"
        >
          <thead>
            <tr className="border-b text-left">
              <th className="py-2">Approve</th>
              <th className="py-2">Rank</th>
              <th className="py-2">Zone</th>
              <th className="py-2">Δ°F</th>
            </tr>
          </thead>
          <tbody>
            {latest.map((r) => {
              const id = recId(r);
              return (
                <tr
                  key={r.rank}
                  data-testid={`latest-run-row-${r.rank}`}
                  className="border-b"
                >
                  <td className="py-2">
                    <input
                      type="checkbox"
                      data-testid={`apply-approve-${r.rank}`}
                      checked={approved.has(id)}
                      onChange={(e) => {
                        const next = new Set(approved);
                        if (e.target.checked) next.add(id);
                        else next.delete(id);
                        setApproved(next);
                      }}
                    />
                  </td>
                  <td className="py-2">{r.rank}</td>
                  <td className="py-2">{r.zone_name}</td>
                  <td className="py-2">{Number(r.setpoint_delta_f).toFixed(1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {anyDispatched && (
        <div
          data-testid="apply-success-banner"
          className="mb-4 rounded border border-green-300 bg-green-50 p-3 text-sm text-green-800"
        >
          Apply completed.
        </div>
      )}

      {missingInputs.length > 0 && (
        <div
          data-testid="apply-error-banner"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          Missing inputs:{" "}
          <span data-testid="apply-missing-inputs">
            {missingInputs.join(", ")}
          </span>
        </div>
      )}

      {serverError && !missingInputs.length && (
        <div
          data-testid="apply-error-banner"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          {serverError}
        </div>
      )}

      {results.length > 0 && (
        <table
          data-testid="apply-result-table"
          className="w-full border-collapse text-sm"
        >
          <thead>
            <tr className="border-b text-left">
              <th className="py-2">#</th>
              <th className="py-2">Rec id</th>
              <th className="py-2">Zone</th>
              <th className="py-2">Status</th>
              <th className="py-2">Error</th>
              <th className="py-2">Latency ms</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r, idx) => (
              <tr
                key={r.recommendation_id}
                data-testid={`apply-result-row-${idx}`}
                className="border-b"
              >
                <td className="py-2">{idx + 1}</td>
                <td className="py-2">{r.recommendation_id}</td>
                <td className="py-2">{r.zone_id}</td>
                <td className="py-2">
                  <span data-testid={`apply-status-${idx}`}>{r.status}</span>
                </td>
                <td className="py-2">
                  {r.error_code ? (
                    <span data-testid={`apply-error-${idx}`}>
                      {r.error_code}
                    </span>
                  ) : (
                    ""
                  )}
                </td>
                <td className="py-2">{r.latency_ms}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
