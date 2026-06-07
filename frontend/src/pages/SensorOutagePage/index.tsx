import { useEffect, useState } from "react";
import {
  declareSensorOutage,
  listBuildings,
  listSensorOutages,
} from "../../services/api";
import type {
  SensorOutageEvent,
  SensorOutageResponse,
} from "../../services/api";
import type { BuildingSummary } from "../../types";

export default function SensorOutagePage() {
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const [buildingId, setBuildingId] = useState<number | null>(null);
  const [selectedZones, setSelectedZones] = useState<Set<number>>(new Set());
  const [reason, setReason] = useState("");
  const [response, setResponse] = useState<SensorOutageResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [missingInputs, setMissingInputs] = useState<string[]>([]);
  const [serverError, setServerError] = useState<string | null>(null);
  const [history, setHistory] = useState<SensorOutageEvent[]>([]);

  useEffect(() => {
    listBuildings().then((list) => {
      setBuildings(list);
      if (list.length > 0) setBuildingId(list[0].id);
    });
  }, []);

  useEffect(() => {
    if (buildingId == null) {
      setHistory([]);
      return;
    }
    setSelectedZones(new Set());
    setResponse(null);
    setMissingInputs([]);
    setServerError(null);
    listSensorOutages(buildingId).then(setHistory);
  }, [buildingId]);

  const currentBuilding = buildings.find((b) => b.id === buildingId);

  const toggleZone = (zoneId: number) => {
    setSelectedZones((prev) => {
      const next = new Set(prev);
      if (next.has(zoneId)) next.delete(zoneId);
      else next.add(zoneId);
      return next;
    });
  };

  const handleDeclare = async () => {
    if (buildingId == null) return;
    setSubmitting(true);
    setResponse(null);
    setMissingInputs([]);
    setServerError(null);
    const res = await declareSensorOutage(
      buildingId,
      Array.from(selectedZones),
      reason,
    );
    if (res.ok) {
      setResponse(res.data);
      const updated = await listSensorOutages(buildingId);
      setHistory(updated);
    } else if (res.status === 400) {
      setMissingInputs(res.missingInputs);
    } else {
      setServerError(res.message ?? "Server error");
    }
    setSubmitting(false);
  };

  return (
    <div className="mx-auto max-w-4xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Sensor Data Outage</h1>

      <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        <div>
          <label className="block text-sm font-medium">Building</label>
          <select
            data-testid="outage-building-selector"
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
          <label className="block text-sm font-medium">Reason</label>
          <input
            data-testid="outage-reason-input"
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="mt-1 w-full rounded border px-3 py-2"
            placeholder="e.g. sensor offline"
          />
        </div>
      </div>

      <div className="mb-4">
        <label className="block text-sm font-medium">Affected zones</label>
        <div className="mt-1 flex flex-wrap gap-3">
          {currentBuilding?.zones?.map((z) => (
            <label key={z.id} className="flex items-center gap-1 text-sm">
              <input
                data-testid={`outage-zone-checkbox-${z.id}`}
                type="checkbox"
                checked={selectedZones.has(z.id)}
                onChange={() => toggleZone(z.id)}
              />
              <span>{z.name}</span>
            </label>
          ))}
        </div>
      </div>

      <button
        data-testid="outage-declare-button"
        onClick={handleDeclare}
        disabled={submitting || buildingId == null}
        className="mb-4 rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
      >
        {submitting ? "Declaring..." : "Declare outage"}
      </button>

      {response && (
        <div
          data-testid="outage-success-banner"
          className="mb-4 rounded border border-green-300 bg-green-50 p-3 text-sm text-green-800"
        >
          <div className="flex items-center gap-2">
            <span>Outage handled.</span>
            <span
              data-testid="outage-decision-pill"
              className="rounded bg-blue-200 px-2 py-0.5 text-xs text-blue-900"
            >
              {response.decision}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {response.affected_zone_ids.map((zid) => (
              <span
                key={zid}
                data-testid={`outage-affected-zone-${zid}`}
                className="rounded bg-yellow-200 px-2 py-0.5 text-xs text-yellow-900"
              >
                zone #{zid}
              </span>
            ))}
          </div>
          <div className="mt-2 text-xs" data-testid="outage-notes">
            {response.notes}
          </div>
        </div>
      )}

      {missingInputs.length > 0 && (
        <div
          data-testid="outage-error-banner"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          Missing inputs:{" "}
          <span data-testid="outage-missing-inputs">
            {missingInputs.join(", ")}
          </span>
        </div>
      )}

      {serverError && missingInputs.length === 0 && (
        <div
          data-testid="outage-error-banner"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          {serverError}
        </div>
      )}

      <h2 className="mb-2 mt-6 text-lg font-semibold">Outage history</h2>
      {history.length === 0 ? (
        <p className="text-sm text-gray-600">No outages recorded.</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-gray-100 text-left">
              <th className="border p-2">Declared at</th>
              <th className="border p-2">Decision</th>
              <th className="border p-2">Reason</th>
              <th className="border p-2">Affected zones</th>
            </tr>
          </thead>
          <tbody>
            {history.map((e) => (
              <tr key={e.id} data-testid={`outage-history-row-${e.id}`}>
                <td className="border p-2">{e.declared_at}</td>
                <td className="border p-2">{e.decision}</td>
                <td className="border p-2">{e.reason}</td>
                <td className="border p-2">{e.affected_zone_ids.length}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
