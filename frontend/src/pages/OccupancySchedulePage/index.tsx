import { useEffect, useState } from "react";
import {
  importOccupancy,
  listBuildings,
} from "../../services/api";
import type {
  BuildingSummary,
  ImportErrorItem,
  ImportResult,
} from "../../types";

export default function OccupancySchedulePage() {
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const [buildingId, setBuildingId] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [errors, setErrors] = useState<ImportErrorItem[]>([]);

  useEffect(() => {
    listBuildings().then((list) => {
      setBuildings(list);
      if (list.length > 0) setBuildingId(list[0].id);
    });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (buildingId == null || file == null) return;
    setSubmitting(true);
    setResult(null);
    setErrors([]);
    const response = await importOccupancy(buildingId, file);
    if (response.ok) {
      setResult(response.data);
    } else {
      setErrors(response.errors);
    }
    setSubmitting(false);
  };

  const rowErrors = errors.filter((e) => e.row != null);
  const headerOrFileErrors = errors.filter((e) => e.row == null);

  return (
    <div className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Import Occupancy Schedule</h1>

      <form
        data-testid="import-occupancy-form"
        onSubmit={handleSubmit}
        className="space-y-6"
      >
        <div>
          <label className="block text-sm font-medium">Building</label>
          <select
            data-testid="building-selector"
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
          <label className="block text-sm font-medium">CSV file</label>
          <input
            data-testid="file-input"
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-1 block"
          />
        </div>

        <button
          type="submit"
          data-testid="submit-import-button"
          disabled={submitting || buildingId == null || file == null}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "Importing..." : "Submit"}
        </button>
      </form>

      {result && (
        <div
          data-testid="import-confirmation"
          className="mt-6 rounded border border-green-300 bg-green-50 p-4"
        >
          <span data-testid="records-imported">
            {result.records_imported} records imported
          </span>
        </div>
      )}

      {headerOrFileErrors.length > 0 && (
        <div
          data-testid="header-error"
          className="mt-6 rounded border border-red-300 bg-red-50 p-4 text-sm text-red-700"
        >
          {headerOrFileErrors.map((e, i) => (
            <p key={i}>{e.message}</p>
          ))}
        </div>
      )}

      {rowErrors.length > 0 && (
        <div
          data-testid="row-errors"
          className="mt-6 rounded border border-red-300 bg-red-50 p-4 text-sm text-red-700"
        >
          {rowErrors.map((e, i) => (
            <p key={i} data-testid={`row-error-${e.row}`}>
              row {e.row}
              {e.field ? ` field ${e.field}` : ""}: {e.message}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
