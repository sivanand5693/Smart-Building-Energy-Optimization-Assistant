import type {
  AppliedChange,
  ApplyPlanResponse,
  BuildingProfileInput,
  BuildingProfileResult,
  BuildingSummary,
  ForecastRunResponse,
  ImportErrorItem,
  ImportResult,
  RecommendationRunResponse,
  SetpointRecommendation,
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

export type RunRecommendationsResult =
  | { ok: true; data: RecommendationRunResponse }
  | { ok: false; missingInputs: string[]; message?: string };

export async function runRecommendations(
  buildingId: number,
): Promise<RunRecommendationsResult> {
  const res = await fetch(`/api/buildings/${buildingId}/recommendations/run`, {
    method: "POST",
  });
  if (res.ok) {
    return { ok: true, data: (await res.json()) as RecommendationRunResponse };
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

export async function getLatestRecommendations(
  buildingId: number,
): Promise<SetpointRecommendation[]> {
  const res = await fetch(`/api/buildings/${buildingId}/recommendations/latest`);
  if (!res.ok) return [];
  return (await res.json()) as SetpointRecommendation[];
}

export type ApplyPlanResult =
  | { ok: true; data: ApplyPlanResponse }
  | { ok: false; missingInputs: string[]; status: number; message?: string };

export async function applyPlan(
  buildingId: number,
  recommendationIds: number[],
): Promise<ApplyPlanResult> {
  const res = await fetch(`/api/buildings/${buildingId}/plans/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recommendation_ids: recommendationIds }),
  });
  if (res.ok) {
    return { ok: true, data: (await res.json()) as ApplyPlanResponse };
  }
  if (res.status === 400) {
    const body = await res.json().catch(() => ({}));
    const missingInputs = (body?.detail?.missingInputs as string[]) ?? [];
    return { ok: false, missingInputs, status: 400 };
  }
  return {
    ok: false,
    missingInputs: [],
    status: res.status,
    message: `Server error (${res.status})`,
  };
}

export async function getLatestPlan(
  buildingId: number,
): Promise<AppliedChange[]> {
  const res = await fetch(`/api/buildings/${buildingId}/plans/latest`);
  if (!res.ok) return [];
  return (await res.json()) as AppliedChange[];
}

// -- UC6 AdaptPlanToOccupancyChange ----------------------------------------

export interface OccupancyChangePayload {
  zone_id: number;
  new_occupancy_count: number;
}

export interface AdaptPlanResponse {
  building_id: number;
  decision: string;
  reason: string;
  active_plan_run_timestamp: string;
  new_run_timestamp: string | null;
  changed_zone_ids: number[];
  requested_at: string;
  elapsed_ms: number;
  revised_recommendations: SetpointRecommendation[];
}

export type AdaptPlanResult =
  | { ok: true; data: AdaptPlanResponse }
  | { ok: false; missingInputs: string[]; status: number; message?: string };

export async function adaptPlan(
  buildingId: number,
  changes: OccupancyChangePayload[],
): Promise<AdaptPlanResult> {
  const res = await fetch(`/api/buildings/${buildingId}/plan/adapt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ occupancy_changes: changes }),
  });
  if (res.ok) {
    return { ok: true, data: (await res.json()) as AdaptPlanResponse };
  }
  if (res.status === 400) {
    const body = await res.json().catch(() => ({}));
    const missingInputs = (body?.detail?.missingInputs as string[]) ?? [];
    return { ok: false, missingInputs, status: 400 };
  }
  return {
    ok: false,
    missingInputs: [],
    status: res.status,
    message: `Server error (${res.status})`,
  };
}

// -- UC7 DetectComfortViolationRisk ----------------------------------------

export interface ComfortRiskAlertItem {
  zone_id: number;
  zone_name: string;
  projected_temp_f: string;
  occupied_min_f: string;
  occupied_max_f: string;
  risk_score: string;
  direction: string;
  mitigation: string;
}

export interface ComfortRiskRunResponse {
  building_id: number;
  decision: string;
  alerts_count: number;
  source_run_timestamp: string | null;
  run_at: string | null;
  elapsed_ms: number;
  alerts: ComfortRiskAlertItem[];
}

export type ComfortRiskResult =
  | { ok: true; data: ComfortRiskRunResponse }
  | { ok: false; missingInputs: string[]; status: number; message?: string };

// -- UC8 ExplainRecommendation ---------------------------------------------

export interface ExplanationResponse {
  recommendation_id: number;
  text: string;
  factors: Record<string, string>;
  cached: boolean;
  elapsed_ms: number;
  model_version: string;
  generated_at: string | null;
}

export type ExplanationResult =
  | { ok: true; data: ExplanationResponse }
  | { ok: false; missingInputs: string[]; status: number; message?: string };

export async function explainRecommendation(
  recommendationId: number,
): Promise<ExplanationResult> {
  const res = await fetch(
    `/api/recommendations/${recommendationId}/explain`,
    { method: "POST" },
  );
  if (res.ok) {
    return { ok: true, data: (await res.json()) as ExplanationResponse };
  }
  if (res.status === 400) {
    const body = await res.json().catch(() => ({}));
    const missingInputs = (body?.detail?.missingInputs as string[]) ?? [];
    return { ok: false, missingInputs, status: 400 };
  }
  return {
    ok: false,
    missingInputs: [],
    status: res.status,
    message: `Server error (${res.status})`,
  };
}

// -- UC9 GenerateDailySavingsReport ----------------------------------------

export interface SavingsReportLine {
  zone_id: number;
  baseline_kwh: string;
  actual_kwh: string;
  savings_kwh: string;
  savings_pct: string;
  anomaly_flag: boolean;
  anomaly_reason: string | null;
}

export interface DailySavingsReportResponse {
  report_id: number | null;
  building_id: number;
  report_date: string;
  total_baseline_kwh: string;
  total_actual_kwh: string;
  total_savings_kwh: string;
  total_savings_pct: string;
  lines: SavingsReportLine[];
  cached: boolean;
  elapsed_ms: number;
  generated_at: string | null;
}

export type SavingsReportResult =
  | { ok: true; data: DailySavingsReportResponse }
  | { ok: false; missingInputs: string[]; status: number; message?: string };

export async function runSavingsReport(
  buildingId: number,
  reportDate: string,
): Promise<SavingsReportResult> {
  const res = await fetch(
    `/api/buildings/${buildingId}/savings-reports/run`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report_date: reportDate }),
    },
  );
  if (res.ok) {
    return { ok: true, data: (await res.json()) as DailySavingsReportResponse };
  }
  if (res.status === 400) {
    const body = await res.json().catch(() => ({}));
    const missingInputs = (body?.detail?.missingInputs as string[]) ?? [];
    return { ok: false, missingInputs, status: 400 };
  }
  return {
    ok: false,
    missingInputs: [],
    status: res.status,
    message: `Server error (${res.status})`,
  };
}

export async function runComfortRisk(
  buildingId: number,
): Promise<ComfortRiskResult> {
  const res = await fetch(`/api/buildings/${buildingId}/comfort-risk/run`, {
    method: "POST",
  });
  if (res.ok) {
    return { ok: true, data: (await res.json()) as ComfortRiskRunResponse };
  }
  if (res.status === 400) {
    const body = await res.json().catch(() => ({}));
    const missingInputs = (body?.detail?.missingInputs as string[]) ?? [];
    return { ok: false, missingInputs, status: 400 };
  }
  return {
    ok: false,
    missingInputs: [],
    status: res.status,
    message: `Server error (${res.status})`,
  };
}
