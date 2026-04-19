# UC2: ImportOccupancySchedule — Database Design

## Part B) Database Design Summary

### Core Tables

**New table:** `occupancy_records`

| Field | Type | Constraints |
|---|---|---|
| `id` | PK | auto-increment |
| `zone_id` | FK → `zones.id` | not null, ON DELETE CASCADE |
| `timestamp` | `TIMESTAMP` | not null |
| `occupancy_count` | `INTEGER` | not null, ≥ 0 |
| `created_at` | `TIMESTAMP` | default `now()` |

Existing tables from UC1 (`buildings`, `zones`, `devices`, `operating_schedules`) remain unchanged.

### Seed Data (per scenario)
- One building "HQ-East"
- Two zones "Floor-1" and "Floor-2", each with one dummy device (HVAC)
- One operating schedule (to satisfy UC1 validation contract if needed)
- Zero `occupancy_records`

### Reset Rules
Truncate in FK order before each scenario:
1. `occupancy_records`
2. `operating_schedules`
3. `devices`
4. `zones`
5. `buildings`
