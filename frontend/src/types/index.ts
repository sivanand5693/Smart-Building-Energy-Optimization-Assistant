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
