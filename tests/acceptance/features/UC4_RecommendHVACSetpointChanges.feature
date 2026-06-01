Feature: UC4 RecommendHVACSetpointChanges
  As the FacilityManager
  I want HVAC setpoint change recommendations derived from the latest forecasts and zone comfort constraints
  So that I can later approve and dispatch an energy plan (UC5)

  Background:
    Given the system is initialized for acceptance testing
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

  Scenario: UC4-S01 Happy path 3-zone recommendation run for Tower-A
    When the FacilityManager triggers a recommendation run for "Tower-A"
    Then the run result lists 3 recommendation rows
    And each recommendation row exposes building_id, zone_id, setpoint_delta_f, projected_savings_kwh, comfort_impact, rank, and model_version
    And the database contains 3 setpoint_recommendation rows for "Tower-A"
    And the RecommendationsPage displays 3 recommendation rows for "Tower-A"

  Scenario: UC4-S02 Single-zone happy path
    Given a building "Solo-Tower" exists with zones:
      | zone_name |
      | OnlyZone  |
    And the latest occupancy snapshot is seeded for every zone of "Solo-Tower"
    And the WeatherAdapter is seeded with current weather for "Solo-Tower"
    And the DeviceStateAdapter is seeded with current device state for every zone of "Solo-Tower"
    And a fresh demand forecast exists for every zone of "Solo-Tower"
    And default comfort constraints are seeded for every zone of "Solo-Tower"
    When the FacilityManager triggers a recommendation run for "Solo-Tower"
    Then the run result lists 1 recommendation rows
    And the database contains 1 setpoint_recommendation rows for "Solo-Tower"

  Scenario: UC4-S03 Larger multi-zone happy path
    Given a building "Mega-Tower" exists with zones:
      | zone_name |
      | Z1        |
      | Z2        |
      | Z3        |
      | Z4        |
      | Z5        |
      | Z6        |
    And the latest occupancy snapshot is seeded for every zone of "Mega-Tower"
    And the WeatherAdapter is seeded with current weather for "Mega-Tower"
    And the DeviceStateAdapter is seeded with current device state for every zone of "Mega-Tower"
    And a fresh demand forecast exists for every zone of "Mega-Tower"
    And default comfort constraints are seeded for every zone of "Mega-Tower"
    When the FacilityManager triggers a recommendation run for "Mega-Tower"
    Then the run result lists 6 recommendation rows
    And the database contains 6 setpoint_recommendation rows for "Mega-Tower"

  Scenario: UC4-S04 Ranking is monotonically non-increasing
    When the FacilityManager triggers a recommendation run for "Tower-A"
    Then the projected_savings_kwh sequence over the ranked rows is monotonically non-increasing

  Scenario: UC4-S05 Every projected_savings_kwh is non-negative
    When the FacilityManager triggers a recommendation run for "Tower-A"
    Then every recommendation row has a projected_savings_kwh greater than or equal to 0

  Scenario: UC4-S06 comfort_impact is constrained to the enum
    When the FacilityManager triggers a recommendation run for "Tower-A"
    Then every recommendation row has a comfort_impact in "none, minor, moderate"

  Scenario: UC4-S07 Infeasible candidates are filtered
    Given the OptimizationAdapter test double is configured to emit an infeasible candidate for zone "Floor-2" of "Tower-A"
    When the FacilityManager triggers a recommendation run for "Tower-A"
    Then the database contains 2 setpoint_recommendation rows for "Tower-A"
    And no recommendation row references zone "Floor-2" of "Tower-A"

  Scenario: UC4-S08 Missing forecast fails atomically
    Given the latest demand forecast is missing for zone "Floor-1" of "Tower-A"
    When the FacilityManager triggers a recommendation run for "Tower-A"
    Then the run is rejected with a missing-inputs error listing "forecast"
    And the database contains 0 setpoint_recommendation rows for "Tower-A"

  Scenario: UC4-S09 Stale forecast (>24h) fails atomically
    Given the latest demand forecast for zone "Lobby" of "Tower-A" is forced to 36 hours old
    When the FacilityManager triggers a recommendation run for "Tower-A"
    Then the run is rejected with a missing-inputs error listing "forecast"
    And the database contains 0 setpoint_recommendation rows for "Tower-A"

  Scenario: UC4-S10 Missing comfort constraints fails atomically
    Given the comfort constraints for zone "Floor-2" of "Tower-A" are deleted
    When the FacilityManager triggers a recommendation run for "Tower-A"
    Then the run is rejected with a missing-inputs error listing "comfort_constraints"
    And the database contains 0 setpoint_recommendation rows for "Tower-A"

  Scenario: UC4-S11 Unknown building id
    When the FacilityManager triggers a recommendation run for an unknown building id
    Then the run is rejected with a missing-inputs error listing "building"

  Scenario: UC4-S12 Empty building with zero zones
    Given a building "Empty-Tower" exists with no zones
    When the FacilityManager triggers a recommendation run for "Empty-Tower"
    Then the run is rejected with a missing-inputs error listing "zones"
    And the database contains 0 setpoint_recommendation rows for "Empty-Tower"

  Scenario: UC4-S13 Failed run preserves prior recommendations
    Given a previous successful recommendation run exists for "Tower-A" with 3 recommendation rows
    And the comfort constraints for zone "Floor-1" of "Tower-A" are deleted
    When the FacilityManager triggers a recommendation run for "Tower-A"
    Then the run is rejected with a missing-inputs error listing "comfort_constraints"
    And the database still contains 3 setpoint_recommendation rows for "Tower-A" from the prior run

  Scenario: UC4-S14 Cross-building isolation
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
    When the FacilityManager triggers a recommendation run for "Tower-A"
    Then the database contains 3 setpoint_recommendation rows for "Tower-A"
    And the database still contains 2 setpoint_recommendation rows for "Tower-B" from the prior run

  Scenario: UC4-S15 Determinism across re-runs
    When the FacilityManager triggers a recommendation run for "Tower-A"
    And the ranked recommendations are captured as the baseline
    And the FacilityManager triggers a recommendation run for "Tower-A"
    Then the ranked recommendations match the baseline exactly

  Scenario: UC4-S16 Recommendation run completes within performance budget
    When the FacilityManager triggers a recommendation run for "Tower-A"
    Then the recommendation run completes in under 5000 milliseconds

  Scenario: UC4-S17 UI error gating after failed run
    Given the comfort constraints for zone "Lobby" of "Tower-A" are deleted
    When the user triggers a recommendation run for "Tower-A" via the RecommendationsPage
    Then the RecommendationsPage shows an error banner listing "comfort_constraints"
    And the RecommendationsPage displays no recommendation rows for "Tower-A"
    And the RecommendationsPage run button is re-enabled
