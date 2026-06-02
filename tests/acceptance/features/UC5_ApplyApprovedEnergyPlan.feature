Feature: UC5 ApplyApprovedEnergyPlan
  As the FacilityManager
  I want to apply an approved subset of HVAC setpoint recommendations from the latest run
  So that the building's controllers move toward the optimized plan

  Background:
    Given the system is initialized for acceptance testing
    And the DeviceControlAdapter test double is reset
    And a building "Tower-A" exists with zones:
      | zone_name |
      | Lobby     |
      | Floor-1   |
      | Floor-2   |
    And the latest occupancy snapshot is seeded for every zone of "Tower-A"
    And the WeatherAdapter is seeded with current weather for "Tower-A"
    And the DeviceStateAdapter is seeded with current device state for every zone of "Tower-A"
    And the ForecastModelAdapter test double returns deterministic predictions
    And a fresh demand forecast exists for every zone of "Tower-A"
    And default comfort constraints are seeded for every zone of "Tower-A"
    And the OptimizationAdapter test double returns deterministic recommendations
    And a previous successful recommendation run exists for "Tower-A" with 3 recommendation rows

  Scenario: UC5-S01 Happy single-rec apply
    When the FacilityManager applies the rank 1 recommendation for "Tower-A"
    Then the apply result contains 1 result rows
    And every apply result row has status "dispatched"
    And the database contains 1 applied_setpoint_change rows for "Tower-A"

  Scenario: UC5-S02 Happy multi-rec apply across zones in rank order
    When the FacilityManager applies the rank 1, 2, 3 recommendations for "Tower-A"
    Then the apply result contains 3 result rows
    And every apply result row has status "dispatched"
    And the apply result rows are ordered by rank ascending
    And the DeviceControlAdapter was invoked 3 times for "Tower-A" in rank ascending order
    And the database contains 3 applied_setpoint_change rows for "Tower-A"

  Scenario: UC5-S03 Approve all recommendations of the latest run
    When the FacilityManager applies all recommendations of the latest run for "Tower-A"
    Then the apply result contains 3 result rows
    And the database contains 3 applied_setpoint_change rows for "Tower-A"

  Scenario: UC5-S04 Single-zone boundary apply-all
    Given a building "Solo-Tower" exists with zones:
      | zone_name |
      | OnlyZone  |
    And the latest occupancy snapshot is seeded for every zone of "Solo-Tower"
    And the WeatherAdapter is seeded with current weather for "Solo-Tower"
    And the DeviceStateAdapter is seeded with current device state for every zone of "Solo-Tower"
    And a fresh demand forecast exists for every zone of "Solo-Tower"
    And default comfort constraints are seeded for every zone of "Solo-Tower"
    And a previous successful recommendation run exists for "Solo-Tower" with 1 recommendation rows
    When the FacilityManager applies all recommendations of the latest run for "Solo-Tower"
    Then the apply result contains 1 result rows
    And the database contains 1 applied_setpoint_change rows for "Solo-Tower"

  Scenario: UC5-S05 Multi-zone boundary apply-all
    Given a building "Mega-Tower" exists with zones:
      | zone_name |
      | Z1        |
      | Z2        |
      | Z3        |
      | Z4        |
      | Z5        |
    And the latest occupancy snapshot is seeded for every zone of "Mega-Tower"
    And the WeatherAdapter is seeded with current weather for "Mega-Tower"
    And the DeviceStateAdapter is seeded with current device state for every zone of "Mega-Tower"
    And a fresh demand forecast exists for every zone of "Mega-Tower"
    And default comfort constraints are seeded for every zone of "Mega-Tower"
    And a previous successful recommendation run exists for "Mega-Tower" with 5 recommendation rows
    When the FacilityManager applies all recommendations of the latest run for "Mega-Tower"
    Then the apply result contains 5 result rows
    And the database contains 5 applied_setpoint_change rows for "Mega-Tower"

  Scenario: UC5-S06 Result row field structure
    When the FacilityManager applies the rank 1 recommendation for "Tower-A"
    Then each apply result row exposes recommendation_id, zone_id, setpoint_delta_f, status, error_code, adapter_message, and latency_ms

  Scenario: UC5-S07 Unknown building id
    When the FacilityManager applies the rank 1 recommendation for an unknown building id
    Then the apply is rejected with a missing-inputs error listing "building"

  Scenario: UC5-S08 Unknown recommendation id
    When the FacilityManager applies an unknown recommendation id for "Tower-A"
    Then the apply is rejected with a missing-inputs error listing "recommendation"
    And the database contains 0 applied_setpoint_change rows for "Tower-A"

  Scenario: UC5-S09 Cross-building recommendation id
    Given a building "Tower-B" exists with zones:
      | zone_name |
      | B-Lobby   |
      | B-Floor-1 |
    And the latest occupancy snapshot is seeded for every zone of "Tower-B"
    And the WeatherAdapter is seeded with current weather for "Tower-B"
    And the DeviceStateAdapter is seeded with current device state for every zone of "Tower-B"
    And a fresh demand forecast exists for every zone of "Tower-B"
    And default comfort constraints are seeded for every zone of "Tower-B"
    And a previous successful recommendation run exists for "Tower-B" with 2 recommendation rows
    When the FacilityManager applies the rank 1 recommendation of "Tower-B" against building "Tower-A"
    Then the apply is rejected with a missing-inputs error listing "recommendation"
    And the database contains 0 applied_setpoint_change rows for "Tower-A"

  Scenario: UC5-S10 Idempotency on re-apply
    When the FacilityManager applies the rank 1 recommendation for "Tower-A"
    And the FacilityManager applies the rank 1 recommendation for "Tower-A" again
    Then the second apply result contains 1 result rows
    And the second apply result row has status "failed" with error_code "already_applied"
    And the DeviceControlAdapter was invoked 1 times for "Tower-A"
    And the database contains 1 applied_setpoint_change rows for "Tower-A"

  Scenario: UC5-S11 Stale-run rejection
    Given the previous recommendation run for "Tower-A" is captured as the stale run
    And a fresh demand forecast exists for every zone of "Tower-A"
    And a new successful recommendation run exists for "Tower-A" with 3 recommendation rows
    When the FacilityManager applies the captured stale rank 1 recommendation for "Tower-A"
    Then the apply is rejected with a missing-inputs error listing "stale_run"
    And the database contains 0 applied_setpoint_change rows for "Tower-A"

  Scenario: UC5-S12 Missing HVAC device for one zone
    Given the HVAC devices for zone "Floor-2" of "Tower-A" are deleted
    When the FacilityManager applies all recommendations of the latest run for "Tower-A"
    Then the apply result contains 3 result rows
    And the apply result row for zone "Floor-2" of "Tower-A" has status "failed" with error_code "missing_device"
    And the apply result rows for zone "Lobby" of "Tower-A" all have status "dispatched"
    And the apply result rows for zone "Floor-1" of "Tower-A" all have status "dispatched"
    And the database contains 3 applied_setpoint_change rows for "Tower-A"

  Scenario: UC5-S13 Adapter failure for one line
    Given the DeviceControlAdapter is configured to fail the rank 2 recommendation of "Tower-A" with error_code "adapter_error"
    When the FacilityManager applies the rank 1, 2, 3 recommendations for "Tower-A"
    Then the apply result contains 3 result rows
    And the apply result row at rank 2 has status "failed" with error_code "adapter_error"
    And the apply result row at rank 1 has status "dispatched"
    And the apply result row at rank 3 has status "dispatched"
    And the database contains 3 applied_setpoint_change rows for "Tower-A"

  Scenario: UC5-S14 Cross-building isolation
    Given a building "Tower-B" exists with zones:
      | zone_name |
      | B-Lobby   |
      | B-Floor-1 |
    And the latest occupancy snapshot is seeded for every zone of "Tower-B"
    And the WeatherAdapter is seeded with current weather for "Tower-B"
    And the DeviceStateAdapter is seeded with current device state for every zone of "Tower-B"
    And a fresh demand forecast exists for every zone of "Tower-B"
    And default comfort constraints are seeded for every zone of "Tower-B"
    And a previous successful recommendation run exists for "Tower-B" with 2 recommendation rows
    When the FacilityManager applies all recommendations of the latest run for "Tower-A"
    Then the database contains 3 applied_setpoint_change rows for "Tower-A"
    And the database contains 0 applied_setpoint_change rows for "Tower-B"

  Scenario: UC5-S15 DB error atomicity
    Given the DeviceControlAdapter is configured to force a DB error on the next apply for "Tower-A"
    When the FacilityManager applies all recommendations of the latest run for "Tower-A"
    Then the apply call fails with HTTP 500
    And the database contains 0 applied_setpoint_change rows for "Tower-A"

  Scenario: UC5-S16 Performance budget for 10-rec batch
    Given a building "Perf-Tower" exists with zones:
      | zone_name |
      | P1        |
      | P2        |
      | P3        |
      | P4        |
      | P5        |
      | P6        |
      | P7        |
      | P8        |
      | P9        |
      | P10       |
    And the latest occupancy snapshot is seeded for every zone of "Perf-Tower"
    And the WeatherAdapter is seeded with current weather for "Perf-Tower"
    And the DeviceStateAdapter is seeded with current device state for every zone of "Perf-Tower"
    And a fresh demand forecast exists for every zone of "Perf-Tower"
    And default comfort constraints are seeded for every zone of "Perf-Tower"
    And a previous successful recommendation run exists for "Perf-Tower" with 10 recommendation rows
    When the FacilityManager applies all recommendations of the latest run for "Perf-Tower"
    Then the apply result contains 10 result rows
    And the apply call completes in under 10000 milliseconds

  Scenario: UC5-S17 UI execution summary
    When the user applies all recommendations of the latest run for "Tower-A" via the ApplyPlanPage
    Then the ApplyPlanPage displays 3 apply-result rows for "Tower-A"
    And the ApplyPlanPage shows the success banner
    And every ApplyPlanPage apply-status pill reads "dispatched"
