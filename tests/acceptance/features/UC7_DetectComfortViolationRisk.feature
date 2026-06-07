Feature: UC7 DetectComfortViolationRisk
  As the Scheduler (and the FacilityManager reviewing the result)
  I want to detect zones whose projected post-plan temperature is heading outside the comfort band
  So that risk alerts and mitigations are generated before occupants feel discomfort

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
    And the DeviceStateAdapter setpoint_f is set to 72 for every zone of "Tower-A"

  Scenario: UC7-S01 Above-band alert for a single zone
    Given the latest recommendation setpoint_delta_f for zone "Lobby" of "Tower-A" is set to 7.0
    When the Scheduler triggers a comfort-risk run for "Tower-A"
    Then the comfort-risk response has decision "alert"
    And the comfort-risk response has alerts_count 1
    And the comfort-risk alert for zone "Lobby" of "Tower-A" has direction "above"
    And the database contains 1 comfort_risk_runs rows for "Tower-A"
    And the database contains 1 comfort_risk_alerts rows for "Tower-A"

  Scenario: UC7-S02 Below-band alert for a single zone
    Given the latest recommendation setpoint_delta_f for zone "Lobby" of "Tower-A" is set to -8.0
    When the Scheduler triggers a comfort-risk run for "Tower-A"
    Then the comfort-risk response has decision "alert"
    And the comfort-risk alert for zone "Lobby" of "Tower-A" has direction "below"
    And the comfort-risk alert for zone "Lobby" of "Tower-A" has mitigation starting with "Increase setpoint by"

  Scenario: UC7-S03 Multi-zone mixed — one above, one below, one within
    Given the latest recommendation setpoint_delta_f for zone "Lobby" of "Tower-A" is set to 7.0
    And the latest recommendation setpoint_delta_f for zone "Floor-1" of "Tower-A" is set to -8.0
    And the latest recommendation setpoint_delta_f for zone "Floor-2" of "Tower-A" is set to 1.0
    When the Scheduler triggers a comfort-risk run for "Tower-A"
    Then the comfort-risk response has decision "alert"
    And the comfort-risk response has alerts_count 2
    And the database contains 1 comfort_risk_runs rows for "Tower-A"
    And the database contains 2 comfort_risk_alerts rows for "Tower-A"

  Scenario: UC7-S04 All zones within band yields a pass
    When the Scheduler triggers a comfort-risk run for "Tower-A"
    Then the comfort-risk response has decision "pass"
    And the comfort-risk response has alerts_count 0
    And the database contains 1 comfort_risk_runs rows for "Tower-A"
    And the database contains 0 comfort_risk_alerts rows for "Tower-A"

  Scenario: UC7-S05 Risk boundary BELOW 0.50 — no alert for that zone
    Given the latest recommendation setpoint_delta_f for zone "Lobby" of "Tower-A" is set to 6.4
    When the Scheduler triggers a comfort-risk run for "Tower-A"
    Then the comfort-risk response has decision "pass"
    And the database contains 0 comfort_risk_alerts rows for "Tower-A"

  Scenario: UC7-S06 Risk boundary AT 0.50 — alerted
    Given the latest recommendation setpoint_delta_f for zone "Lobby" of "Tower-A" is set to 6.5
    When the Scheduler triggers a comfort-risk run for "Tower-A"
    Then the comfort-risk response has decision "alert"
    And the comfort-risk alert for zone "Lobby" of "Tower-A" has risk_score "0.500"

  Scenario: UC7-S07 Mitigation text shape for both directions
    Given the latest recommendation setpoint_delta_f for zone "Lobby" of "Tower-A" is set to 7.0
    And the latest recommendation setpoint_delta_f for zone "Floor-1" of "Tower-A" is set to -8.0
    When the Scheduler triggers a comfort-risk run for "Tower-A"
    Then the comfort-risk alert for zone "Lobby" of "Tower-A" has mitigation "Reduce setpoint by 4.0°F to return to comfort band."
    And the comfort-risk alert for zone "Floor-1" of "Tower-A" has mitigation "Increase setpoint by 4.0°F to return to comfort band."

  Scenario: UC7-S08 Unknown building rejected with no rows written
    When the Scheduler triggers a comfort-risk run for an unknown building id
    Then the comfort-risk run is rejected with a missing-inputs error listing "building"

  Scenario: UC7-S09 No prior plan exists
    Given a building "Plan-less" exists with zones:
      | zone_name |
      | OnlyZone  |
    When the Scheduler triggers a comfort-risk run for "Plan-less"
    Then the comfort-risk run is rejected with a missing-inputs error listing "plan"
    And the database contains 0 comfort_risk_runs rows for "Plan-less"

  Scenario: UC7-S10 Partial plan — only covered zones are evaluated
    Given the latest recommendation rows for zone "Floor-2" of "Tower-A" are deleted
    And the latest recommendation setpoint_delta_f for zone "Lobby" of "Tower-A" is set to 7.0
    When the Scheduler triggers a comfort-risk run for "Tower-A"
    Then the comfort-risk response has decision "alert"
    And no comfort-risk alert exists for zone "Floor-2" of "Tower-A"

  Scenario: UC7-S11 Missing comfort constraints on all zones collapses to 400
    Given the comfort constraints for zone "Lobby" of "Tower-A" are deleted
    And the comfort constraints for zone "Floor-1" of "Tower-A" are deleted
    And the comfort constraints for zone "Floor-2" of "Tower-A" are deleted
    When the Scheduler triggers a comfort-risk run for "Tower-A"
    Then the comfort-risk run is rejected with a missing-inputs error listing "comfort_constraints"
    And the database contains 0 comfort_risk_runs rows for "Tower-A"

  Scenario: UC7-S12 Missing device state on one zone — skip that zone
    Given the DeviceStateAdapter has no data for zone "Lobby" of "Tower-A"
    And the latest recommendation setpoint_delta_f for zone "Floor-1" of "Tower-A" is set to 7.0
    When the Scheduler triggers a comfort-risk run for "Tower-A"
    Then the comfort-risk response has decision "alert"
    And no comfort-risk alert exists for zone "Lobby" of "Tower-A"

  Scenario: UC7-S13 Cross-building isolation
    Given a building "Tower-B" exists with zones:
      | zone_name |
      | B-Lobby   |
    And the latest occupancy snapshot is seeded for every zone of "Tower-B"
    And the WeatherAdapter is seeded with current weather for "Tower-B"
    And the DeviceStateAdapter is seeded with current device state for every zone of "Tower-B"
    And a fresh demand forecast exists for every zone of "Tower-B"
    And default comfort constraints are seeded for every zone of "Tower-B"
    And a previous successful recommendation run exists for "Tower-B" with 1 recommendation rows
    And the DeviceStateAdapter setpoint_f is set to 72 for every zone of "Tower-B"
    And the latest recommendation setpoint_delta_f for zone "Lobby" of "Tower-A" is set to 7.0
    When the Scheduler triggers a comfort-risk run for "Tower-A"
    Then the database contains 1 comfort_risk_runs rows for "Tower-A"
    And the database contains 0 comfort_risk_runs rows for "Tower-B"
    And the database contains 0 comfort_risk_alerts rows for "Tower-B"

  Scenario: UC7-S14 Atomicity — forced DB error rolls back the run
    Given the ComfortRiskService is configured to force a DB error on the next run for "Tower-A"
    And the latest recommendation setpoint_delta_f for zone "Lobby" of "Tower-A" is set to 7.0
    When the Scheduler triggers a comfort-risk run for "Tower-A"
    Then the comfort-risk run returns a 500 server error
    And the database contains 0 comfort_risk_runs rows for "Tower-A"
    And the database contains 0 comfort_risk_alerts rows for "Tower-A"

  Scenario: UC7-S15 Performance budget for a 5-zone building
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
    And the DeviceStateAdapter setpoint_f is set to 72 for every zone of "Perf-Tower"
    When the Scheduler triggers a comfort-risk run for "Perf-Tower"
    Then the comfort-risk run completes in under 3000 milliseconds

  Scenario: UC7-S16 Determinism across back-to-back runs
    Given the latest recommendation setpoint_delta_f for zone "Lobby" of "Tower-A" is set to 7.0
    When the Scheduler triggers a comfort-risk run for "Tower-A"
    And the Scheduler triggers a comfort-risk run for "Tower-A" again
    Then the two comfort-risk runs produce identical alert rows for "Tower-A"

  Scenario: UC7-S17 UI flow via /comfort-risk
    Given the latest recommendation setpoint_delta_f for zone "Lobby" of "Tower-A" is set to 7.0
    When the user triggers a comfort-risk run for "Tower-A" via the ComfortRiskPage
    Then the ComfortRiskPage shows the success banner
    And the ComfortRiskPage decision pill reads "alert"
    And the ComfortRiskPage lists zone "Lobby" of "Tower-A" as an alert row
