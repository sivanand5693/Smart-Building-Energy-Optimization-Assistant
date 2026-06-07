import { useEffect, useState } from "react";
import {
  listBuildings,
  runSavingsReport,
} from "../../services/api";
import type {
  DailySavingsReportResponse,
} from "../../services/api";
import type { BuildingSummary } from "../../types";

function toCsv(report: DailySavingsReportResponse): string {
  const header =
    "zone_id,baseline_kwh,actual_kwh,savings_kwh,savings_pct,anomaly_flag,anomaly_reason";
  const lineRows = report.lines.map((l) =>
    [
      l.zone_id,
      l.baseline_kwh,
      l.actual_kwh,
      l.savings_kwh,
      l.savings_pct,
      l.anomaly_flag ? "true" : "false",
      l.anomaly_reason ?? "",
    ].join(","),
  );
  const totalsRow = [
    "TOTAL",
    report.total_baseline_kwh,
    report.total_actual_kwh,
    report.total_savings_kwh,
    report.total_savings_pct,
    "",
    "",
  ].join(",");
  return [header, ...lineRows, totalsRow].join("\n");
}

export default function SavingsReportPage() {
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const [buildingId, setBuildingId] = useState<number | null>(null);
  const [reportDate, setReportDate] = useState<string>("");
  const [response, setResponse] = useState<DailySavingsReportResponse | null>(
    null,
  );
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
  }, [buildingId, reportDate]);

  const canSubmit = buildingId != null && reportDate !== "" && !running;

  const handleSubmit = async () => {
    if (buildingId == null || reportDate === "") return;
    setRunning(true);
    setMissingInputs([]);
    setServerError(null);
    setResponse(null);
    const res = await runSavingsReport(buildingId, reportDate);
    if (res.ok) {
      setResponse(res.data);
    } else if (res.status === 400) {
      setMissingInputs(res.missingInputs);
    } else {
      setServerError(res.message ?? "Server error");
    }
    setRunning(false);
  };

  const handleExport = () => {
    if (response == null) return;
    const csv = toCsv(response);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `savings-report-${response.building_id}-${response.report_date}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mx-auto max-w-4xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Daily Savings Report</h1>

      <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-3 md:items-end">
        <div>
          <label className="block text-sm font-medium">Building</label>
          <select
            data-testid="savings-building-selector"
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
          <label className="block text-sm font-medium">Report date</label>
          <input
            data-testid="savings-date-input"
            type="date"
            value={reportDate}
            onChange={(e) => setReportDate(e.target.value)}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </div>
        <button
          data-testid="savings-run-button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {running ? "Generating..." : "Generate"}
        </button>
      </div>

      {response && (
        <div
          data-testid="savings-success-banner"
          className="mb-4 flex items-center gap-2 rounded border border-green-300 bg-green-50 p-3 text-sm text-green-800"
        >
          <span>Report generated.</span>
          {response.cached && (
            <span
              data-testid="savings-cached-pill"
              className="rounded bg-blue-200 px-2 py-0.5 text-xs text-blue-900"
            >
              cached
            </span>
          )}
          <button
            data-testid="savings-export-button"
            onClick={handleExport}
            className="ml-auto rounded bg-gray-200 px-2 py-1 text-xs text-gray-800"
          >
            Export CSV
          </button>
        </div>
      )}

      {missingInputs.length > 0 && (
        <div
          data-testid="savings-error-banner"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          Missing inputs:{" "}
          <span data-testid="savings-missing-inputs">
            {missingInputs.join(", ")}
          </span>
        </div>
      )}

      {serverError && missingInputs.length === 0 && (
        <div
          data-testid="savings-error-banner"
          className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700"
        >
          {serverError}
        </div>
      )}

      {response && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <div className="rounded border border-gray-200 bg-white p-3">
              <div className="text-xs font-semibold uppercase text-gray-500">
                Total baseline
              </div>
              <div
                data-testid="savings-total-baseline"
                className="mt-1 text-sm"
              >
                {response.total_baseline_kwh}
              </div>
            </div>
            <div className="rounded border border-gray-200 bg-white p-3">
              <div className="text-xs font-semibold uppercase text-gray-500">
                Total actual
              </div>
              <div data-testid="savings-total-actual" className="mt-1 text-sm">
                {response.total_actual_kwh}
              </div>
            </div>
            <div className="rounded border border-gray-200 bg-white p-3">
              <div className="text-xs font-semibold uppercase text-gray-500">
                Total savings
              </div>
              <div
                data-testid="savings-total-savings"
                className="mt-1 text-sm"
              >
                {response.total_savings_kwh}
              </div>
            </div>
            <div className="rounded border border-gray-200 bg-white p-3">
              <div className="text-xs font-semibold uppercase text-gray-500">
                Savings %
              </div>
              <div data-testid="savings-total-pct" className="mt-1 text-sm">
                {response.total_savings_pct}
              </div>
            </div>
          </div>

          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-gray-100 text-left">
                <th className="border p-2">Zone</th>
                <th className="border p-2">Baseline kWh</th>
                <th className="border p-2">Actual kWh</th>
                <th className="border p-2">Savings kWh</th>
                <th className="border p-2">Savings %</th>
                <th className="border p-2">Anomaly</th>
                <th className="border p-2">Reason</th>
              </tr>
            </thead>
            <tbody>
              {response.lines.map((l) => (
                <tr
                  key={l.zone_id}
                  data-testid={`savings-line-row-${l.zone_id}`}
                >
                  <td className="border p-2">{l.zone_id}</td>
                  <td className="border p-2">{l.baseline_kwh}</td>
                  <td className="border p-2">{l.actual_kwh}</td>
                  <td className="border p-2">{l.savings_kwh}</td>
                  <td className="border p-2">{l.savings_pct}</td>
                  <td className="border p-2">
                    {l.anomaly_flag && (
                      <span
                        data-testid={`savings-anomaly-flag-${l.zone_id}`}
                        className="rounded bg-red-200 px-2 py-0.5 text-xs text-red-800"
                      >
                        anomaly
                      </span>
                    )}
                  </td>
                  <td className="border p-2">
                    {l.anomaly_flag && (
                      <span
                        data-testid={`savings-anomaly-reason-${l.zone_id}`}
                      >
                        {l.anomaly_reason ?? ""}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
