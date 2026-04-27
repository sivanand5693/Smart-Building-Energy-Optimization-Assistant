import type {
  BuildingProfileInput,
  BuildingProfileResult,
  BuildingSummary,
  ForecastRunResponse,
  ImportErrorItem,
  ImportResult,
  ZoneForecast,
} from "../types";

export type RegisterResult =
  | { ok: true; data: BuildingProfileResult }
  | { ok: false; errors: Record<string, string> };

export async function registerBuildingProfile(
  profile: BuildingProfileInput
): Promise<RegisterResult> {
  const res = await fetch("/api/buildings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });

  if (res.ok) {
    return { ok: true, data: (await res.json()) as BuildingProfileResult };
  }

  if (res.status === 400) {
    const body = await res.json();
    const errors = body?.detail?.errors ?? {
      _general: "Validation failed",
    };
    return { ok: false, errors };
  }

  return {
    ok: false,
    errors: { _general: `Unexpected error (${res.status})` },
  };
}

export async function listBuildings(): Promise<BuildingSummary[]> {
  const res = await fetch("/api/buildings");
  if (!res.ok) return [];
  return (await res.json()) as BuildingSummary[];
}

export type ImportOccupancyResult =
  | { ok: true; data: ImportResult }
  | { ok: false; errors: ImportErrorItem[] };

export async function importOccupancy(
  buildingId: number,
  file: File
): Promise<ImportOccupancyResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`/api/buildings/${buildingId}/occupancy`, {
    method: "POST",
    body: form,
  });

  if (res.ok) {
    return { ok: true, data: (await res.json()) as ImportResult };
  }
  if (res.status === 400) {
    const body = await res.json();
    const errors = (body?.detail?.errors as ImportErrorItem[]) ?? [
      { row: null, field: null, message: "Import failed" },
    ];
    return { ok: false, errors };
  }
  return {
    ok: false,
    errors: [{ row: null, field: null, message: `Unexpected error (${res.status})` }],
  };
}

export type RunForecastResult =
  | { ok: true; data: ForecastRunResponse }
  | { ok: false; missingInputs: string[]; message?: string };

export async function runForecast(buildingId: number): Promise<RunForecastResult> {
  const res = await fetch(`/api/buildings/${buildingId}/forecasts/run`, {
    method: "POST",
  });
  if (res.ok) {
    return { ok: true, data: (await res.json()) as ForecastRunResponse };
  }
  if (res.status === 400) {
    const body = await res.json();
    const missingInputs = (body?.detail?.missingInputs as string[]) ?? [];
    return { ok: false, missingInputs };
  }
  return {
    ok: false,
    missingInputs: [],
    message: `Unexpected error (${res.status})`,
  };
}

export async function getLatestForecasts(buildingId: number): Promise<ZoneForecast[]> {
  const res = await fetch(`/api/buildings/${buildingId}/forecasts/latest`);
  if (!res.ok) return [];
  return (await res.json()) as ZoneForecast[];
}
