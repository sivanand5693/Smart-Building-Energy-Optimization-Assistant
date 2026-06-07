Feature: UC10 HandleSensorDataOutage
  As the MonitoringService (and the FacilityManager reviewing via /sensor-outage)
  I want sensor data outages to switch the system into fallback estimation mode
  So that affected forecasts and recommendations are flagged with degraded confidence
  And so that planning is paused when no usable history exists

  Background:
    Given the system is initialized for acceptance testing
    And a building "Tower-A" exists with zones:
      | zone_name |
      | Lobby     |
      | Office    |

  Scenario: UC10-S01 Happy fallback — one zone affected, recent forecast exists
    Given a recent demand_forecasts row exists for zone "Lobby" of "Tower-A"
    And a latest-run setpoint_recommendations row exists for zone "Lobby" of "Tower-A"
    When the MonitoringService declares a sensor outage for "Tower-A" affecting zones "Lobby" with reason "sensor offline"
    Then the sensor outage response status is 200
    And the sensor outage response has decision "fallback"
    And the latest demand_forecasts row for zone "Lobby" of "Tower-A" has degraded_confidence "true"
    And the latest-run setpoint_recommendations rows for zone "Lobby" of "Tower-A" have degraded_confidence "true"
    And the database contains 1 sensor_outage_events row for "Tower-A"

  Scenario: UC10-S02 Multi-zone fallback — only affected zones flagged
    Given a building "Tower-Multi" exists with zones:
      | zone_name |
      | Z1        |
      | Z2        |
      | Z3        |
    And a recent demand_forecasts row exists for zone "Z1" of "Tower-Multi"
    And a recent demand_forecasts row exists for zone "Z2" of "Tower-Multi"
    And a recent demand_forecasts row exists for zone "Z3" of "Tower-Multi"
    And a latest-run setpoint_recommendations row exists for zone "Z1" of "Tower-Multi"
    And a latest-run setpoint_recommendations row exists for zone "Z2" of "Tower-Multi"
    And a latest-run setpoint_recommendations row exists for zone "Z3" of "Tower-Multi"
    When the MonitoringService declares a sensor outage for "Tower-Multi" affecting zones "Z1,Z2" with reason "sensor offline"
    Then the sensor outage response status is 200
    And the sensor outage response has decision "fallback"
    And the latest demand_forecasts row for zone "Z1" of "Tower-Multi" has degraded_confidence "true"
    And the latest demand_forecasts row for zone "Z2" of "Tower-Multi" has degraded_confidence "true"
    And the latest demand_forecasts row for zone "Z3" of "Tower-Multi" has degraded_confidence "false"
    And the latest-run setpoint_recommendations rows for zone "Z3" of "Tower-Multi" have degraded_confidence "false"

  Scenario: UC10-S03 Pause path — all zones affected and no recent forecast for any
    When the MonitoringService declares a sensor outage for "Tower-A" affecting zones "Lobby,Office" with reason "full outage"
    Then the sensor outage response status is 200
    And the sensor outage response has decision "paused"
    And the database contains 1 sensor_outage_events row for "Tower-A"
    And the sensor_outage_events row notes for "Tower-A" contain "planning paused"

  Scenario: UC10-S04 All zones affected but recent forecast exists for at least one → fallback
    Given a recent demand_forecasts row exists for zone "Lobby" of "Tower-A"
    When the MonitoringService declares a sensor outage for "Tower-A" affecting zones "Lobby,Office" with reason "partial outage"
    Then the sensor outage response status is 200
    And the sensor outage response has decision "fallback"
    And the latest demand_forecasts row for zone "Lobby" of "Tower-A" has degraded_confidence "true"

  Scenario: UC10-S05 Degraded-confidence persists in DB — older rows untouched
    Given two demand_forecasts rows exist for zone "Lobby" of "Tower-A" — an older one and a newer one
    When the MonitoringService declares a sensor outage for "Tower-A" affecting zones "Lobby" with reason "sensor offline"
    Then the sensor outage response status is 200
    And the newest demand_forecasts row for zone "Lobby" of "Tower-A" has degraded_confidence "true"
    And the oldest demand_forecasts row for zone "Lobby" of "Tower-A" has degraded_confidence "false"

  Scenario: UC10-S06 Re-declaring the same outage creates a second event row (non-idempotent)
    Given a recent demand_forecasts row exists for zone "Lobby" of "Tower-A"
    When the MonitoringService declares a sensor outage for "Tower-A" affecting zones "Lobby" with reason "sensor offline"
    Then the sensor outage response status is 200
    When the MonitoringService declares a sensor outage for "Tower-A" affecting zones "Lobby" with reason "sensor offline"
    Then the sensor outage response status is 200
    And the database contains 2 sensor_outage_events rows for "Tower-A"
    And the latest demand_forecasts row for zone "Lobby" of "Tower-A" has degraded_confidence "true"

  Scenario: UC10-S07 Unknown building yields a 400
    When the MonitoringService declares a sensor outage for unknown building id 9999999 affecting zones "1" with reason "sensor offline"
    Then the sensor outage response status is 400
    And the sensor outage response missingInputs equals ["building"]

  Scenario: UC10-S08 Empty affected_zone_ids yields a 400
    When the MonitoringService declares a sensor outage for "Tower-A" affecting no zones with reason "sensor offline"
    Then the sensor outage response status is 400
    And the sensor outage response missingInputs equals ["affected_zone_ids"]
    And the database contains 0 sensor_outage_events rows for "Tower-A"

  Scenario: UC10-S09 Zone id not belonging to the building yields a 400
    Given a building "Tower-Other" exists with zones:
      | zone_name |
      | Other     |
    When the MonitoringService declares a sensor outage for "Tower-A" affecting zone of "Tower-Other" "Other" with reason "sensor offline"
    Then the sensor outage response status is 400
    And the sensor outage response missingInputs equals ["zone"]
    And the database contains 0 sensor_outage_events rows for "Tower-A"

  Scenario: UC10-S10 Missing reason yields a 400
    When the MonitoringService declares a sensor outage for "Tower-A" affecting zones "Lobby" with reason ""
    Then the sensor outage response status is 400
    And the sensor outage response missingInputs equals ["reason"]
    And the database contains 0 sensor_outage_events rows for "Tower-A"

  Scenario: UC10-S11 Atomicity — forced DB error mid-write rolls back, zero rows survive
    Given a recent demand_forecasts row exists for zone "Lobby" of "Tower-A"
    And the SensorOutageService is configured to force a DB error on the next request
    When the MonitoringService declares a sensor outage for "Tower-A" affecting zones "Lobby" with reason "sensor offline"
    Then the sensor outage response status is 500
    And the database contains 0 sensor_outage_events rows for "Tower-A"
    And the latest demand_forecasts row for zone "Lobby" of "Tower-A" has degraded_confidence "false"

  Scenario: UC10-S12 Cross-building isolation — outage on A doesn't flag B's rows
    Given a building "Tower-B" exists with zones:
      | zone_name |
      | B-Lobby   |
    And a recent demand_forecasts row exists for zone "Lobby" of "Tower-A"
    And a recent demand_forecasts row exists for zone "B-Lobby" of "Tower-B"
    When the MonitoringService declares a sensor outage for "Tower-A" affecting zones "Lobby" with reason "sensor offline"
    Then the sensor outage response status is 200
    And the latest demand_forecasts row for zone "B-Lobby" of "Tower-B" has degraded_confidence "false"
    And the database contains 1 sensor_outage_events row for "Tower-A"
    And the database contains 0 sensor_outage_events rows for "Tower-B"

  Scenario: UC10-S13 Performance — 5-zone elapsed_ms is under 2000
    Given a building "Tower-Perf" exists with zones:
      | zone_name |
      | P1        |
      | P2        |
      | P3        |
      | P4        |
      | P5        |
    And a recent demand_forecasts row exists for zone "P1" of "Tower-Perf"
    And a recent demand_forecasts row exists for zone "P2" of "Tower-Perf"
    And a recent demand_forecasts row exists for zone "P3" of "Tower-Perf"
    And a recent demand_forecasts row exists for zone "P4" of "Tower-Perf"
    And a recent demand_forecasts row exists for zone "P5" of "Tower-Perf"
    When the MonitoringService declares a sensor outage for "Tower-Perf" affecting zones "P1,P2,P3,P4,P5" with reason "sensor offline"
    Then the sensor outage response status is 200
    And the sensor outage response elapsed_ms is under 2000

  Scenario: UC10-S14 UC3 forecast response surfaces the degraded_confidence flag
    Given a recent demand_forecasts row exists for zone "Lobby" of "Tower-A"
    When the MonitoringService declares a sensor outage for "Tower-A" affecting zones "Lobby" with reason "sensor offline"
    Then the sensor outage response status is 200
    When the FacilityManager fetches the latest forecasts for "Tower-A"
    Then the latest forecasts response carries degraded_confidence "true" for zone "Lobby" of "Tower-A"

  Scenario: UC10-S15 UC4 recommendations response surfaces the degraded_confidence flag
    Given a recent demand_forecasts row exists for zone "Lobby" of "Tower-A"
    And a latest-run setpoint_recommendations row exists for zone "Lobby" of "Tower-A"
    When the MonitoringService declares a sensor outage for "Tower-A" affecting zones "Lobby" with reason "sensor offline"
    Then the sensor outage response status is 200
    When the FacilityManager fetches the latest recommendations for "Tower-A"
    Then the latest recommendations response carries degraded_confidence "true" for zone "Lobby" of "Tower-A"

  Scenario: UC10-S16 History endpoint returns events ordered by declared_at DESC
    Given a recent demand_forecasts row exists for zone "Lobby" of "Tower-A"
    When the MonitoringService declares a sensor outage for "Tower-A" affecting zones "Lobby" with reason "first outage"
    Then the sensor outage response status is 200
    When the MonitoringService declares a sensor outage for "Tower-A" affecting zones "Lobby" with reason "second outage"
    Then the sensor outage response status is 200
    When the FacilityManager fetches the sensor outage history for "Tower-A"
    Then the sensor outage history has 2 events
    And the sensor outage history first event reason equals "second outage"

  Scenario: UC10-S17 UI flow via /sensor-outage
    Given a recent demand_forecasts row exists for zone "Lobby" of "Tower-A"
    And a latest-run setpoint_recommendations row exists for zone "Lobby" of "Tower-A"
    When the user declares a sensor outage for "Tower-A" affecting zones "Lobby" with reason "sensor offline" via the SensorOutagePage
    Then the SensorOutagePage shows the success banner
    And the SensorOutagePage shows the decision pill with text "fallback"
    And the SensorOutagePage shows an affected-zone chip for zone "Lobby" of "Tower-A"
    And the SensorOutagePage shows a history row for the newest event
    When the user opens the /forecasts page for "Tower-A"
    Then the ForecastsPage shows a degraded badge for zone "Lobby" of "Tower-A"
    When the user opens the /recommendations page for "Tower-A"
    Then the RecommendationsPage shows a degraded badge for zone "Lobby" of "Tower-A"
