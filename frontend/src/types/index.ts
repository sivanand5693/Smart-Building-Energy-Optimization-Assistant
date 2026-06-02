export interface DeviceInput {
  device_type: string;
  device_name?: string;
}

export interface ZoneInput {
  name: string;
  devices: DeviceInput[];
}

export interface OperatingScheduleInput {
  days_of_week: string;
  start_time: string; // "HH:MM:SS"
  end_time: string;
}

export interface BuildingProfileInput {
  building_name: string;
  zones: ZoneInput[];
  operating_schedules: OperatingScheduleInput[];
}

export interface BuildingProfileResult {
  building_id: number;
  name: string;
}

export interface ValidationErrorResponse {
  detail: { errors: Record<string, string> };
}

export interface ZoneSummary {
  id: number;
  name: string;
}

export interface BuildingSummary {
  id: number;
  name: string;
  zones: ZoneSummary[];
}

export interface ImportResult {
  records_imported: number;
}

export interface ImportErrorItem {
  row: number | null;
  field: string | null;
  message: string;
}

export interface ZoneForecast {
  zone_id: number;
  zone_name: string;
  timestamp: string;
  predicted_kwh: string;
  model_version: string;
}

export interface ForecastRunResponse {
  building_id: number;
  run_timestamp: string;
  elapsed_ms: number;
  forecasts: ZoneForecast[];
}

export interface SetpointRecommendation {
  id?: number;
  building_id: number;
  zone_id: number;
  zone_name: string;
  run_timestamp: string;
  setpoint_delta_f: string;
  projected_savings_kwh: string;
  comfort_impact: string;
  rank: number;
  model_version: string;
}

export interface RecommendationRunResponse {
  building_id: number;
  run_timestamp: string;
  elapsed_ms: number;
  recommendations: SetpointRecommendation[];
}

export interface AppliedChange {
  recommendation_id: number;
  building_id: number;
  zone_id: number;
  applied_at: string;
  setpoint_delta_f: string;
  status: string;
  error_code: string | null;
  adapter_message: string;
  latency_ms: number;
}

export interface ApplyPlanResponse {
  building_id: number;
  applied_at: string;
  elapsed_ms: number;
  results: AppliedChange[];
}
