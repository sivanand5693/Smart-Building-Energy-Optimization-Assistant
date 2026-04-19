# UC1: RegisterBuildingProfile — UI Design

## Part A) UI Design Summary

### Main Page
`RegisterBuildingProfilePage`

### Inputs
- `buildingName` — text input
- `zones[]` — repeatable section:
  - `zoneName` — text input
  - `devices[]` — repeatable:
    - `deviceType` — dropdown (HVAC, Lighting, Plug Load, Other)
    - `deviceName` — text input (optional)
- `operatingSchedules[]` — repeatable:
  - `daysOfWeek` — multi-select (Mon–Sun)
  - `startTime` — time input
  - `endTime` — time input
- Submit button

### Outputs
- **Confirmation panel** — displays saved `buildingId` and `buildingName` on success
- **Field-level error messages** — rendered inline next to each field, text includes the field name (e.g., "buildingName is required")
- **General error area** — for server/unknown errors not tied to a specific field
