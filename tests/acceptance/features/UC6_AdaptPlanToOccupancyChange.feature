Feature: UC6 AdaptPlanToOccupancyChange
  As the OccupancyDataService (and the FacilityManager reviewing the result)
  I want to feed real-time occupancy changes into the active plan
  So that material swings replan the building while small swings are absorbed

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
    And the FacilityManager has applied the rank 1 recommendation for "Tower-A"

  Scenario: UC6-S01 Happy single-zone replan on +50% jump
    When the OccupancyDataService reports occupancy changes for "Tower-A":
      | zone_name | new_occupancy_count |
      | Lobby     | 30                  |
    Then the adapt response has decision "replanned"
    And the adapt response changed_zone_ids list zones ["Lobby"] for "Tower-A"
    And the adapt response includes a non-null new_run_timestamp
    And the database contains 1 plan_adaptation_events rows for "Tower-A"
    And a new setpoint_recommendations run was created for "Tower-A"

  Scenario: UC6-S02 Happy multi-zone replan when two of three cross the threshold
    When the OccupancyDataService reports occupancy changes for "Tower-A":
      | zone_name | new_occupancy_count |
      | Lobby     | 30                  |
      | Floor-1   | 30                  |
      | Floor-2   | 5                   |
    Then the adapt response has decision "replanned"
    And the adapt response changed_zone_ids list zones ["Lobby", "Floor-1"] for "Tower-A"
    And the database contains 1 plan_adaptation_events rows for "Tower-A"
    And a new setpoint_recommendations run was created for "Tower-A"

  Scenario: UC6-S03 Mixed material and non-material yields material-only changed_zone_ids
    When the OccupancyDataService reports occupancy changes for "Tower-A":
      | zone_name | new_occupancy_count |
      | Lobby     | 30                  |
      | Floor-1   | 6                   |
      | Floor-2   | 5                   |
    Then the adapt response has decision "replanned"
    And the adapt response changed_zone_ids list zones ["Lobby"] for "Tower-A"
    And the database contains 1 plan_adaptation_events rows for "Tower-A"

  Scenario: UC6-S04 No-replan when every zone change is below threshold
    When the OccupancyDataService reports occupancy changes for "Tower-A":
      | zone_name | new_occupancy_count |
      | Lobby     | 6                   |
      | Floor-1   | 6                   |
      | Floor-2   | 6                   |
    Then the adapt response has decision "no_replan"
    And the adapt response changed_zone_ids list zones [] for "Tower-A"
    And the adapt response new_run_timestamp is null
    And the database contains 1 plan_adaptation_events rows for "Tower-A"
    And no new setpoint_recommendations run was created for "Tower-A"

  Scenario: UC6-S05 Threshold BELOW 29% is non-material
    When the OccupancyDataService reports a 29 percent jump for zone "Lobby" of "Tower-A"
    Then the adapt response has decision "no_replan"

  Scenario: UC6-S06 Threshold AT 30% is material
    When the OccupancyDataService reports a 30 percent jump for zone "Lobby" of "Tower-A"
    Then the adapt response has decision "replanned"
    And the adapt response changed_zone_ids list zones ["Lobby"] for "Tower-A"

  Scenario: UC6-S07 Zero-baseline edge — any new occupancy is material
    Given the latest occupancy snapshot is missing for zone "Lobby" of "Tower-A"
    When the OccupancyDataService reports occupancy changes for "Tower-A":
      | zone_name | new_occupancy_count |
      | Lobby     | 5                   |
    Then the adapt response has decision "replanned"
    And the adapt response changed_zone_ids list zones ["Lobby"] for "Tower-A"

  Scenario: UC6-S08 Negative direction drop crosses threshold
    Given the latest occupancy snapshot for zone "Lobby" of "Tower-A" is set to 100
    When the OccupancyDataService reports occupancy changes for "Tower-A":
      | zone_name | new_occupancy_count |
      | Lobby     | 60                  |
    Then the adapt response has decision "replanned"
    And the adapt response changed_zone_ids list zones ["Lobby"] for "Tower-A"

  Scenario: UC6-S09 No active plan exists
    Given a building "Plan-less" exists with zones:
      | zone_name |
      | OnlyZone  |
    And the latest occupancy snapshot is seeded for every zone of "Plan-less"
    When the OccupancyDataService reports occupancy changes for "Plan-less":
      | zone_name | new_occupancy_count |
      | OnlyZone  | 20                  |
    Then the adapt is rejected with a missing-inputs error listing "active_plan"
    And the database contains 0 plan_adaptation_events rows for "Plan-less"

  Scenario: UC6-S10 Unknown building id
    When the OccupancyDataService reports an occupancy change against an unknown building id
    Then the adapt is rejected with a missing-inputs error listing "building"

  Scenario: UC6-S11 Unknown zone id in payload
    When the OccupancyDataService reports occupancy changes for "Tower-A" referencing an unknown zone
    Then the adapt is rejected with a missing-inputs error listing "zone"
    And the database contains 0 plan_adaptation_events rows for "Tower-A"
    And no new setpoint_recommendations run was created for "Tower-A"

  Scenario: UC6-S12 Empty occupancy_changes payload
    When the OccupancyDataService reports an empty occupancy_changes payload for "Tower-A"
    Then the adapt is rejected with a missing-inputs error listing "occupancy_changes"
    And the database contains 0 plan_adaptation_events rows for "Tower-A"

  Scenario: UC6-S13 Active plan resolves even when applied state is mixed dispatched/failed
    Given the DeviceControlAdapter is configured to fail the rank 2 recommendation of "Tower-A" with error_code "adapter_error"
    And the FacilityManager applies the rank 2, 3 recommendations for "Tower-A"
    When the OccupancyDataService reports occupancy changes for "Tower-A":
      | zone_name | new_occupancy_count |
      | Lobby     | 30                  |
    Then the adapt response has decision "replanned"
    And the database contains 1 plan_adaptation_events rows for "Tower-A"

  Scenario: UC6-S14 Determinism — identical second payload sees zero delta
    When the OccupancyDataService reports occupancy changes for "Tower-A":
      | zone_name | new_occupancy_count |
      | Lobby     | 30                  |
    And the OccupancyDataService reports the same occupancy changes for "Tower-A" again
    Then the second adapt response has decision "no_replan"
    And the database contains 2 plan_adaptation_events rows for "Tower-A"

  Scenario: UC6-S15 Cross-building isolation
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
    And the FacilityManager has applied the rank 1 recommendation for "Tower-B"
    When the OccupancyDataService reports occupancy changes for "Tower-A":
      | zone_name | new_occupancy_count |
      | Lobby     | 30                  |
    Then the database contains 1 plan_adaptation_events rows for "Tower-A"
    And the database contains 0 plan_adaptation_events rows for "Tower-B"
    And no new setpoint_recommendations run was created for "Tower-B"

  Scenario: UC6-S16 Performance budget for 5-zone replanned path
    Given a building "Perf-Tower" exists with zones:
      | zone_name |
      | P1        |
      | P2        |
      | P3        |
      | P4        |
      | P5        |
    And the latest occupancy snapshot is seeded for every zone of "Perf-Tower"
    And the WeatherAdapter is seeded with current weather for "Perf-Tower"
    And the DeviceStateAdapter is seeded with current device state for every zone of "Perf-Tower"
    And a fresh demand forecast exists for every zone of "Perf-Tower"
    And default comfort constraints are seeded for every zone of "Perf-Tower"
    And a previous successful recommendation run exists for "Perf-Tower" with 5 recommendation rows
    And the FacilityManager has applied the rank 1 recommendation for "Perf-Tower"
    When the OccupancyDataService reports occupancy changes for "Perf-Tower":
      | zone_name | new_occupancy_count |
      | P1        | 30                  |
      | P2        | 30                  |
      | P3        | 30                  |
      | P4        | 30                  |
      | P5        | 30                  |
    Then the adapt response has decision "replanned"
    And the adapt call completes in under 2000 milliseconds

  Scenario: UC6-S17 UI flow via /adapt-plan
    When the user submits an occupancy change for zone "Lobby" of "Tower-A" with count 30 via the AdaptPlanPage
    Then the AdaptPlanPage shows the success banner
    And the AdaptPlanPage decision pill reads "replanned"
    And the AdaptPlanPage reason text is non-empty
    And the AdaptPlanPage lists zone "Lobby" of "Tower-A" as a changed zone
    And the AdaptPlanPage revised-recs table displays 3 rows
