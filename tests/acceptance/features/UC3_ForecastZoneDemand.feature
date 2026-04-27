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
