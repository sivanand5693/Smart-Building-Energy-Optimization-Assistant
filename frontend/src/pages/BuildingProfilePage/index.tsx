import { useState } from "react";
import { registerBuildingProfile } from "../../services/api";
import type {
  BuildingProfileInput,
  BuildingProfileResult,
} from "../../types";

interface ZoneDraft {
  name: string;
  deviceType: string;
  deviceName?: string;
}

interface ScheduleDraft {
  days_of_week: string;
  start_time: string;
  end_time: string;
}

export default function BuildingProfilePage() {
  const [buildingName, setBuildingName] = useState("");
  const [zones, setZones] = useState<ZoneDraft[]>([]);
  const [schedules, setSchedules] = useState<ScheduleDraft[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<BuildingProfileResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [zoneNameDraft, setZoneNameDraft] = useState("");
  const [deviceTypeDraft, setDeviceTypeDraft] = useState("HVAC");
  const [scheduleDraft, setScheduleDraft] = useState<ScheduleDraft>({
    days_of_week: "Mon-Fri",
    start_time: "08:00",
    end_time: "18:00",
  });

  const addZone = () => {
    if (!zoneNameDraft.trim()) return;
    setZones([
      ...zones,
      { name: zoneNameDraft.trim(), deviceType: deviceTypeDraft },
    ]);
    setZoneNameDraft("");
  };

  const addSchedule = () => {
    setSchedules([...schedules, { ...scheduleDraft }]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrors({});
    setResult(null);

    const payload: BuildingProfileInput = {
      building_name: buildingName,
      zones: zones.map((z) => ({
        name: z.name,
        devices: [{ device_type: z.deviceType, device_name: z.deviceName }],
      })),
      operating_schedules: schedules.map((s) => ({
        days_of_week: s.days_of_week,
        start_time: s.start_time.length === 5 ? `${s.start_time}:00` : s.start_time,
        end_time: s.end_time.length === 5 ? `${s.end_time}:00` : s.end_time,
      })),
    };

    const response = await registerBuildingProfile(payload);
    if (response.ok) {
      setResult(response.data);
    } else {
      setErrors(response.errors);
    }
    setSubmitting(false);
  };

  return (
    <div className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Register Building Profile</h1>

      <form
        data-testid="register-building-form"
        onSubmit={handleSubmit}
        className="space-y-6"
      >
        <div>
          <label className="block text-sm font-medium">Building name</label>
          <input
            data-testid="building-name-input"
            type="text"
            value={buildingName}
            onChange={(e) => setBuildingName(e.target.value)}
            className="mt-1 w-full rounded border px-3 py-2"
          />
          {errors.buildingName && (
            <p data-testid="error-buildingName" className="mt-1 text-sm text-red-600">
              {errors.buildingName}
            </p>
          )}
        </div>

        <section>
          <h2 className="mb-2 text-lg font-medium">Zones</h2>
          <ul data-testid="zones-list" className="mb-3 space-y-1 text-sm">
            {zones.map((z, i) => (
              <li key={i} data-testid="zone-item">
                {z.name} — {z.deviceType}
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <input
              data-testid="zone-name-input"
              type="text"
              placeholder="Zone name"
              value={zoneNameDraft}
              onChange={(e) => setZoneNameDraft(e.target.value)}
              className="flex-1 rounded border px-3 py-2"
            />
            <select
              data-testid="device-type-input"
              value={deviceTypeDraft}
              onChange={(e) => setDeviceTypeDraft(e.target.value)}
              className="rounded border px-3 py-2"
            >
              <option>HVAC</option>
              <option>Lighting</option>
              <option>Plug Load</option>
              <option>Other</option>
            </select>
            <button
              type="button"
              data-testid="add-zone-button"
              onClick={addZone}
              className="rounded bg-gray-200 px-3 py-2"
            >
              Add zone
            </button>
          </div>
          {errors.zones && (
            <p data-testid="error-zones" className="mt-1 text-sm text-red-600">
              {errors.zones}
            </p>
          )}
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium">Operating schedules</h2>
          <ul data-testid="schedules-list" className="mb-3 space-y-1 text-sm">
            {schedules.map((s, i) => (
              <li key={i} data-testid="schedule-item">
                {s.days_of_week} {s.start_time}-{s.end_time}
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <input
              data-testid="schedule-days-input"
              type="text"
              value={scheduleDraft.days_of_week}
              onChange={(e) =>
                setScheduleDraft({ ...scheduleDraft, days_of_week: e.target.value })
              }
              className="rounded border px-3 py-2"
            />
            <input
              data-testid="schedule-start-input"
              type="time"
              value={scheduleDraft.start_time}
              onChange={(e) =>
                setScheduleDraft({ ...scheduleDraft, start_time: e.target.value })
              }
              className="rounded border px-3 py-2"
            />
            <input
              data-testid="schedule-end-input"
              type="time"
              value={scheduleDraft.end_time}
              onChange={(e) =>
                setScheduleDraft({ ...scheduleDraft, end_time: e.target.value })
              }
              className="rounded border px-3 py-2"
            />
            <button
              type="button"
              data-testid="add-schedule-button"
              onClick={addSchedule}
              className="rounded bg-gray-200 px-3 py-2"
            >
              Add schedule
            </button>
          </div>
          {errors.operatingSchedule && (
            <p
              data-testid="error-operatingSchedule"
              className="mt-1 text-sm text-red-600"
            >
              {errors.operatingSchedule}
            </p>
          )}
        </section>

        <button
          type="submit"
          data-testid="submit-button"
          disabled={submitting}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "Saving..." : "Submit"}
        </button>

        {errors._general && (
          <p data-testid="error-general" className="text-sm text-red-600">
            {errors._general}
          </p>
        )}
      </form>

      {result && (
        <div
          data-testid="confirmation-panel"
          className="mt-6 rounded border border-green-300 bg-green-50 p-4"
        >
          <p>
            Building registered: <strong>{result.name}</strong> (ID:{" "}
            <span data-testid="building-id">{result.building_id}</span>)
          </p>
        </div>
      )}
    </div>
  );
}
