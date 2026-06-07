Feature: UC8 ExplainRecommendation
  As the FacilityManager (and any caller of the explain endpoint)
  I want a concise natural-language explanation of a setpoint recommendation
  So that I can review the dominant energy, comfort, and occupancy factors before acting on it

  Background:
    Given the system is initialized for acceptance testing
    And the DeviceControlAdapter test double is reset
    And the ExplanationAdapter test double is reset
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

  Scenario: UC8-S01 Happy path — text references all three factors and the numeric savings
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 200
    And the explanation text contains case-insensitive substring "energy"
    And the explanation text contains case-insensitive substring "comfort"
    And the explanation text contains case-insensitive substring "occupancy"
    And the explanation text contains the projected_savings_kwh value
    And the database contains 1 recommendation_explanations row for the latest recommendation of zone "Lobby" of "Tower-A"

  Scenario: UC8-S02 Factors JSON shape — keys energy, comfort, occupancy each non-empty
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 200
    And the explanation factors object has a non-empty "energy" entry
    And the explanation factors object has a non-empty "comfort" entry
    And the explanation factors object has a non-empty "occupancy" entry

  Scenario: UC8-S03 Idempotency — second call is cached and the adapter is not re-invoked
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 200
    And the explanation response has cached "false"
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 200
    And the explanation response has cached "true"
    And the explanation adapter has been invoked 1 time
    And the database contains 1 recommendation_explanations row for the latest recommendation of zone "Lobby" of "Tower-A"

  Scenario: UC8-S04 Determinism — identical inputs across two recommendations produce identical text
    Given the latest recommendation factor fields for zone "Floor-1" of "Tower-A" are copied from zone "Lobby" of "Tower-A"
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    And the explanation text is captured as the baseline for zone "Lobby" of "Tower-A"
    When the FacilityManager requests an explanation for the latest recommendation of zone "Floor-1" of "Tower-A"
    Then the explanation text for zone "Floor-1" of "Tower-A" matches the baseline for zone "Lobby" of "Tower-A" modulo identifiers

  Scenario: UC8-S05 Unknown recommendation_id is rejected with no row written
    When the FacilityManager requests an explanation for recommendation id 9999999
    Then the explanation response status is 400
    And the explanation response missingInputs equals ["recommendation"]

  Scenario: UC8-S06 Missing comfort constraints for the zone yields a 400
    Given the comfort constraints for zone "Lobby" of "Tower-A" are deleted
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 400
    And the explanation response missingInputs equals ["comfort_constraints"]
    And the database contains 0 recommendation_explanations row for the latest recommendation of zone "Lobby" of "Tower-A"

  Scenario: UC8-S07 Missing occupancy records for the zone yields a 400
    Given all occupancy records for zone "Lobby" of "Tower-A" are deleted
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 400
    And the explanation response missingInputs equals ["occupancy"]
    And the database contains 0 recommendation_explanations row for the latest recommendation of zone "Lobby" of "Tower-A"

  Scenario: UC8-S08 Missing forecast row for the zone yields a 400
    Given the latest demand forecast is missing for zone "Lobby" of "Tower-A"
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 400
    And the explanation response missingInputs equals ["forecast"]
    And the database contains 0 recommendation_explanations row for the latest recommendation of zone "Lobby" of "Tower-A"

  Scenario: UC8-S09 Multiple missing inputs accumulate and are returned sorted alphabetically
    Given the comfort constraints for zone "Lobby" of "Tower-A" are deleted
    And all occupancy records for zone "Lobby" of "Tower-A" are deleted
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 400
    And the explanation response missingInputs equals ["comfort_constraints", "occupancy"]

  Scenario: UC8-S10 Cross-building isolation — explain on A doesn't touch B
    Given a building "Tower-B" exists with zones:
      | zone_name |
      | B-Lobby   |
    And the latest occupancy snapshot is seeded for every zone of "Tower-B"
    And the WeatherAdapter is seeded with current weather for "Tower-B"
    And the DeviceStateAdapter is seeded with current device state for every zone of "Tower-B"
    And a fresh demand forecast exists for every zone of "Tower-B"
    And default comfort constraints are seeded for every zone of "Tower-B"
    And a previous successful recommendation run exists for "Tower-B" with 1 recommendation rows
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 200
    And the database contains 1 recommendation_explanations row for the latest recommendation of zone "Lobby" of "Tower-A"
    And the database contains 0 recommendation_explanations row for the latest recommendation of zone "B-Lobby" of "Tower-B"

  Scenario: UC8-S11 Quality Q1 — text contains comfort_impact word and the occupancy count value
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 200
    And the explanation text contains the comfort_impact value
    And the explanation text contains the latest occupancy_count value

  Scenario: UC8-S12 Quality Q2 — first-generation elapsed_ms is under 4000
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 200
    And the explanation response elapsed_ms is under 4000

  Scenario: UC8-S13 Cached response elapsed_ms is under 500
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    And the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 200
    And the explanation response has cached "true"
    And the explanation response elapsed_ms is under 500

  Scenario: UC8-S14 Atomicity — forced DB error mid-write rolls back, zero rows survive
    Given the ExplanationService is configured to force a DB error on the next request
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 500
    And the database contains 0 recommendation_explanations row for the latest recommendation of zone "Lobby" of "Tower-A"

  Scenario: UC8-S15 Model version is persisted on the row and surfaced in the API body
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 200
    And the explanation response model_version equals "explanation-double-v1"
    And the persisted recommendation_explanations row model_version equals "explanation-double-v1" for the latest recommendation of zone "Lobby" of "Tower-A"

  Scenario: UC8-S16 GET endpoint returns the cached row when present, 404 otherwise
    When the FacilityManager fetches the explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 404
    When the FacilityManager requests an explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 200
    When the FacilityManager fetches the explanation for the latest recommendation of zone "Lobby" of "Tower-A"
    Then the explanation response status is 200
    And the explanation factors object has a non-empty "energy" entry

  Scenario: UC8-S17 UI flow via /explain
    When the user requests an explanation for zone "Lobby" of "Tower-A" via the ExplainPage
    Then the ExplainPage shows the success banner
    And the ExplainPage shows the explanation text
    And the ExplainPage shows the three factor sections
    And the ExplainPage shows the model-version pill
    When the user requests an explanation for zone "Lobby" of "Tower-A" via the ExplainPage again
    Then the ExplainPage shows the cached pill
