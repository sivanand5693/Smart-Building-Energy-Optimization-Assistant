Feature: UC3 ForecastZoneDemand
  As the Scheduler
  I want a forecast of zone-level energy demand for a building
  So that the Optimization Service can act on up-to-date demand estimates

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

  Scenario: UC3-S01 Successful forecast for all zones of a building
    When the Scheduler triggers a forecast run for "Tower-A"
    Then the run result lists 3 zone forecasts
    And each zone forecast exposes a non-null timestamp and zone_id
    And the database contains 3 demand_forecast rows for "Tower-A"
    And the ForecastsPage displays 3 forecast rows for "Tower-A"

  Scenario: UC3-S02 Missing occupancy data fails atomically
    Given the latest occupancy snapshot is missing for zone "Floor-2" of "Tower-A"
    When the Scheduler triggers a forecast run for "Tower-A"
    Then the run is rejected with a missing-inputs error listing "occupancy"
    And the database contains 0 demand_forecast rows for "Tower-A"

  Scenario: UC3-S03 Missing weather data fails atomically
    Given the WeatherAdapter has no data for "Tower-A"
    When the Scheduler triggers a forecast run for "Tower-A"
    Then the run is rejected with a missing-inputs error listing "weather"
    And the database contains 0 demand_forecast rows for "Tower-A"

  Scenario: UC3-S04 Missing device-state data fails atomically
    Given the DeviceStateAdapter has no data for zone "Lobby" of "Tower-A"
    When the Scheduler triggers a forecast run for "Tower-A"
    Then the run is rejected with a missing-inputs error listing "device_state"
    And the database contains 0 demand_forecast rows for "Tower-A"

  Scenario: UC3-S05 Forecast records include structured timestamp and zone_id fields
    When the Scheduler triggers a forecast run for "Tower-A"
    Then every persisted demand_forecast row has a non-null timestamp column
    And every persisted demand_forecast row has a zone_id referencing an existing zone

  Scenario: UC3-S06 Forecast run completes within performance budget
    When the Scheduler triggers a forecast run for "Tower-A"
    Then the forecast run completes in under 6000 milliseconds

  Scenario: UC3-S07 Failed run preserves prior forecasts
    Given a previous successful forecast run exists for "Tower-A" with 3 forecast rows
    And the WeatherAdapter has no data for "Tower-A"
    When the Scheduler triggers a forecast run for "Tower-A"
    Then the run is rejected with a missing-inputs error listing "weather"
    And the database still contains 3 demand_forecast rows for "Tower-A" from the prior run

  Scenario: UC3-S08 Single-zone happy path
    Given a building "Solo-Tower" exists with zones:
      | zone_name |
      | OnlyZone  |
    And the latest occupancy snapshot is seeded for every zone of "Solo-Tower"
    And the WeatherAdapter is seeded with current weather for "Solo-Tower"
    And the DeviceStateAdapter is seeded with current device state for every zone of "Solo-Tower"
    When the Scheduler triggers a forecast run for "Solo-Tower"
    Then the run result lists 1 zone forecasts
    And the database contains 1 demand_forecast rows for "Solo-Tower"
    And the ForecastsPage displays 1 forecast rows for "Solo-Tower"

  Scenario: UC3-S09 Larger multi-zone happy path
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
    When the Scheduler triggers a forecast run for "Mega-Tower"
    Then the run result lists 6 zone forecasts
    And every zone forecast in the result has a distinct zone_id
    And every zone forecast in the result has a distinct predicted_kwh
    And the database contains 6 demand_forecast rows for "Mega-Tower"

  Scenario: UC3-S10 Determinism across re-runs
    When the Scheduler triggers a forecast run for "Tower-A"
    And the predicted_kwh per zone is captured as the baseline
    And the Scheduler triggers a forecast run for "Tower-A"
    Then the predicted_kwh per zone matches the baseline exactly

  Scenario: UC3-S11 Cross-building isolation
    Given a building "Tower-B" exists with zones:
      | zone_name |
      | B-Lobby   |
      | B-Floor-1 |
    And the latest occupancy snapshot is seeded for every zone of "Tower-B"
    And the WeatherAdapter is seeded with current weather for "Tower-B"
    And the DeviceStateAdapter is seeded with current device state for every zone of "Tower-B"
    And a previous successful forecast run exists for "Tower-B" with 2 forecast rows
    When the Scheduler triggers a forecast run for "Tower-A"
    Then the database contains 3 demand_forecast rows for "Tower-A"
    And the database still contains 2 demand_forecast rows for "Tower-B" from the prior run

  Scenario: UC3-S12 Building with zero zones
    Given a building "Empty-Tower" exists with no zones
    When the Scheduler triggers a forecast run for "Empty-Tower"
    Then the run is rejected with a missing-inputs error listing "zones"
    And the database contains 0 demand_forecast rows for "Empty-Tower"

  Scenario: UC3-S13 Unknown building id
    When the Scheduler triggers a forecast run for an unknown building id
    Then the run is rejected with a missing-inputs error listing "building"

  Scenario: UC3-S14 Multiple zones missing occupancy
    Given the latest occupancy snapshot is missing for zone "Floor-1" of "Tower-A"
    And the latest occupancy snapshot is missing for zone "Floor-2" of "Tower-A"
    When the Scheduler triggers a forecast run for "Tower-A"
    Then the run is rejected with a missing-inputs error listing "occupancy"
    And the database contains 0 demand_forecast rows for "Tower-A"

  Scenario: UC3-S15 Multiple missing input categories
    Given the WeatherAdapter has no data for "Tower-A"
    And the DeviceStateAdapter has no data for zone "Lobby" of "Tower-A"
    When the Scheduler triggers a forecast run for "Tower-A"
    Then the run is rejected with a missing-inputs error listing "weather"
    And the database contains 0 demand_forecast rows for "Tower-A"

  Scenario: UC3-S16 UI error gating after failed run
    Given the WeatherAdapter has no data for "Tower-A"
    When the user triggers a forecast run for "Tower-A" via the ForecastsPage
    Then the ForecastsPage shows an error banner listing "weather"
    And the ForecastsPage displays no forecast rows for "Tower-A"

  Scenario: UC3-S17 Forecast model_version is stamped on every row
    When the Scheduler triggers a forecast run for "Tower-A"
    Then every persisted demand_forecast row has a non-empty model_version
