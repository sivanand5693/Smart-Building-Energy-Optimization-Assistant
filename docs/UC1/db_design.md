# UC1: RegisterBuildingProfile — Database Design

## Part B) Database Design Summary

### Core Tables

| Table | Fields |
|---|---|
| `buildings` | `id` (PK), `name` (unique, not null), `created_at` (timestamp) |
| `zones` | `id` (PK), `building_id` (FK → buildings.id), `name` (not null) |
| `devices` | `id` (PK), `zone_id` (FK → zones.id), `device_type` (not null), `device_name` (nullable) |
| `operating_schedules` | `id` (PK), `building_id` (FK → buildings.id), `days_of_week` (not null), `start_time`, `end_time` |

### Seed Data
- Empty DB — UC1 registers new buildings; no pre-existing data needed

### Reset Rules
Truncate in FK order before each scenario:
1. `operating_schedules`
2. `devices`
3. `zones`
4. `buildings`
