Feature: UC9 GenerateDailySavingsReport
  As the FacilityManager (and any caller of the savings-report endpoint)
  I want a daily savings report comparing baseline and actual energy usage per zone
  So that I can review savings totals and anomaly flags for a building on a given date

  Background:
    Given the system is initialized for acceptance testing
    And a building "Tower-A" exists with zones:
      | zone_name |
      | Lobby     |

  Scenario: UC9-S01 Happy single-zone — savings math and no anomaly
    Given energy usage rows are ingested for "Tower-A" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | Lobby     | 100.000      | 80.000     |
    When the FacilityManager generates a savings report for "Tower-A" on "2026-06-07"
    Then the savings report response status is 200
    And the savings report has total_savings_kwh "20.000"
    And the savings report has total_savings_pct "20.00"
    And the savings report line for zone "Lobby" of "Tower-A" has savings_kwh "20.000" and savings_pct "20.00"
    And the savings report line for zone "Lobby" of "Tower-A" has anomaly_flag "false"
    And the database contains 1 daily_savings_reports row for "Tower-A" on "2026-06-07"
    And the database contains 1 daily_savings_report_lines rows for "Tower-A" on "2026-06-07"

  Scenario: UC9-S02 Happy multi-zone — totals equal the sum of per-zone lines
    Given a building "Tower-Multi" exists with zones:
      | zone_name |
      | Z1        |
      | Z2        |
      | Z3        |
    And energy usage rows are ingested for "Tower-Multi" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | Z1        | 100.000      | 80.000     |
      | Z2        | 200.000      | 150.000    |
      | Z3        |  50.000      | 40.000     |
    When the FacilityManager generates a savings report for "Tower-Multi" on "2026-06-07"
    Then the savings report response status is 200
    And the savings report has total_baseline_kwh "350.000"
    And the savings report has total_actual_kwh "270.000"
    And the savings report has total_savings_kwh "80.000"
    And the savings report total_savings_kwh equals the sum of per-line savings_kwh
    And the database contains 3 daily_savings_report_lines rows for "Tower-Multi" on "2026-06-07"

  Scenario: UC9-S03 Over-consumption anomaly — actual > baseline*1.10
    Given energy usage rows are ingested for "Tower-A" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | Lobby     | 100.000      | 120.000    |
    When the FacilityManager generates a savings report for "Tower-A" on "2026-06-07"
    Then the savings report response status is 200
    And the savings report line for zone "Lobby" of "Tower-A" has anomaly_flag "true"
    And the savings report line for zone "Lobby" of "Tower-A" has anomaly_reason "over_consumption"

  Scenario: UC9-S04 Suspicious-low anomaly — actual < baseline*0.5
    Given energy usage rows are ingested for "Tower-A" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | Lobby     | 100.000      | 30.000     |
    When the FacilityManager generates a savings report for "Tower-A" on "2026-06-07"
    Then the savings report response status is 200
    And the savings report line for zone "Lobby" of "Tower-A" has anomaly_flag "true"
    And the savings report line for zone "Lobby" of "Tower-A" has anomaly_reason "suspicious_low"

  Scenario: UC9-S05 Anomaly boundaries — exact ratios are not anomalies; tiny overshoots are
    Given a building "Tower-Bounds" exists with zones:
      | zone_name |
      | Edge-Hi   |
      | Edge-Lo   |
      | Over-Hi   |
      | Over-Lo   |
    And energy usage rows are ingested for "Tower-Bounds" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | Edge-Hi   | 100.000      | 110.000    |
      | Edge-Lo   | 100.000      | 50.000     |
      | Over-Hi   | 100.000      | 110.001    |
      | Over-Lo   | 100.000      | 49.999     |
    When the FacilityManager generates a savings report for "Tower-Bounds" on "2026-06-07"
    Then the savings report response status is 200
    And the savings report line for zone "Edge-Hi" of "Tower-Bounds" has anomaly_flag "false"
    And the savings report line for zone "Edge-Lo" of "Tower-Bounds" has anomaly_flag "false"
    And the savings report line for zone "Over-Hi" of "Tower-Bounds" has anomaly_flag "true"
    And the savings report line for zone "Over-Hi" of "Tower-Bounds" has anomaly_reason "over_consumption"
    And the savings report line for zone "Over-Lo" of "Tower-Bounds" has anomaly_flag "true"
    And the savings report line for zone "Over-Lo" of "Tower-Bounds" has anomaly_reason "suspicious_low"

  Scenario: UC9-S06 Zero baseline edge — savings is negative actual, pct is 0, no anomaly
    Given energy usage rows are ingested for "Tower-A" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | Lobby     | 0.000        | 10.000     |
    When the FacilityManager generates a savings report for "Tower-A" on "2026-06-07"
    Then the savings report response status is 200
    And the savings report line for zone "Lobby" of "Tower-A" has savings_kwh "-10.000" and savings_pct "0.00"
    And the savings report line for zone "Lobby" of "Tower-A" has anomaly_flag "false"

  Scenario: UC9-S07 Negative savings within thresholds — actual mildly over baseline, no anomaly
    Given energy usage rows are ingested for "Tower-A" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | Lobby     | 100.000      | 105.000    |
    When the FacilityManager generates a savings report for "Tower-A" on "2026-06-07"
    Then the savings report response status is 200
    And the savings report line for zone "Lobby" of "Tower-A" has savings_kwh "-5.000" and savings_pct "-5.00"
    And the savings report line for zone "Lobby" of "Tower-A" has anomaly_flag "false"

  Scenario: UC9-S08 Missing baseline for one zone yields a 400 — no rows written
    Given energy usage rows are ingested for "Tower-A" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | Lobby     |              | 80.000     |
    When the FacilityManager generates a savings report for "Tower-A" on "2026-06-07"
    Then the savings report response status is 400
    And the savings report response missingInputs equals ["baseline"]
    And the database contains 0 daily_savings_reports row for "Tower-A" on "2026-06-07"
    And the database contains 0 daily_savings_report_lines rows for "Tower-A" on "2026-06-07"

  Scenario: UC9-S09 Missing actual for one zone yields a 400 — no rows written
    Given energy usage rows are ingested for "Tower-A" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | Lobby     | 100.000      |            |
    When the FacilityManager generates a savings report for "Tower-A" on "2026-06-07"
    Then the savings report response status is 400
    And the savings report response missingInputs equals ["actual"]
    And the database contains 0 daily_savings_reports row for "Tower-A" on "2026-06-07"

  Scenario: UC9-S10 Both missing — labels accumulate sorted alphabetically and deduplicated
    Given energy usage rows are ingested for "Tower-A" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | Lobby     |              |            |
    When the FacilityManager generates a savings report for "Tower-A" on "2026-06-07"
    Then the savings report response status is 400
    And the savings report response missingInputs equals ["actual", "baseline"]
    And the database contains 0 daily_savings_reports row for "Tower-A" on "2026-06-07"

  Scenario: UC9-S11 Unknown building yields a 400
    When the FacilityManager generates a savings report for unknown building id 9999999 on "2026-06-07"
    Then the savings report response status is 400
    And the savings report response missingInputs equals ["building"]

  Scenario: UC9-S12 Invalid date format yields a 400
    When the FacilityManager generates a savings report for "Tower-A" with report_date "not-a-date"
    Then the savings report response status is 400
    And the savings report response missingInputs equals ["report_date"]

  Scenario: UC9-S13 Idempotency — re-running for the same (building, date) returns cached, no new rows
    Given energy usage rows are ingested for "Tower-A" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | Lobby     | 100.000      | 80.000     |
    When the FacilityManager generates a savings report for "Tower-A" on "2026-06-07"
    Then the savings report response status is 200
    And the savings report response has cached "false"
    When the FacilityManager generates a savings report for "Tower-A" on "2026-06-07"
    Then the savings report response status is 200
    And the savings report response has cached "true"
    And the database contains 1 daily_savings_reports row for "Tower-A" on "2026-06-07"
    And the database contains 1 daily_savings_report_lines rows for "Tower-A" on "2026-06-07"

  Scenario: UC9-S14 Atomicity — forced DB error mid-write rolls back, zero rows survive
    Given energy usage rows are ingested for "Tower-A" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | Lobby     | 100.000      | 80.000     |
    And the ReportingService is configured to force a DB error on the next request
    When the FacilityManager generates a savings report for "Tower-A" on "2026-06-07"
    Then the savings report response status is 500
    And the database contains 0 daily_savings_reports row for "Tower-A" on "2026-06-07"
    And the database contains 0 daily_savings_report_lines rows for "Tower-A" on "2026-06-07"

  Scenario: UC9-S15 Performance — 5-zone elapsed_ms is under 5000
    Given a building "Tower-Perf" exists with zones:
      | zone_name |
      | P1        |
      | P2        |
      | P3        |
      | P4        |
      | P5        |
    And energy usage rows are ingested for "Tower-Perf" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | P1        | 100.000      | 80.000     |
      | P2        | 110.000      | 95.000     |
      | P3        | 120.000      | 100.000    |
      | P4        | 130.000      | 105.000    |
      | P5        | 140.000      | 110.000    |
    When the FacilityManager generates a savings report for "Tower-Perf" on "2026-06-07"
    Then the savings report response status is 200
    And the savings report response elapsed_ms is under 5000

  Scenario: UC9-S16 Cross-building isolation — running for A doesn't write rows for B
    Given a building "Tower-B" exists with zones:
      | zone_name |
      | B-Lobby   |
    And energy usage rows are ingested for "Tower-A" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | Lobby     | 100.000      | 80.000     |
    And energy usage rows are ingested for "Tower-B" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | B-Lobby   | 200.000      | 150.000    |
    When the FacilityManager generates a savings report for "Tower-A" on "2026-06-07"
    Then the savings report response status is 200
    And the database contains 1 daily_savings_reports row for "Tower-A" on "2026-06-07"
    And the database contains 0 daily_savings_reports row for "Tower-B" on "2026-06-07"
    And the database contains 1 daily_savings_report_lines rows for "Tower-A" on "2026-06-07"
    And the database contains 0 daily_savings_report_lines rows for "Tower-B" on "2026-06-07"

  Scenario: UC9-S17 UI flow via /savings-report
    Given energy usage rows are ingested for "Tower-A" on "2026-06-07":
      | zone_name | baseline_kwh | actual_kwh |
      | Lobby     | 100.000      | 120.000    |
    When the user generates a savings report for "Tower-A" on "2026-06-07" via the SavingsReportPage
    Then the SavingsReportPage shows the success banner
    And the SavingsReportPage shows totals for "Tower-A" on "2026-06-07"
    And the SavingsReportPage shows a line row for zone "Lobby" of "Tower-A"
    And the SavingsReportPage shows an anomaly flag for zone "Lobby" of "Tower-A"
    And the SavingsReportPage shows the export button
    When the user generates a savings report for "Tower-A" on "2026-06-07" via the SavingsReportPage again
    Then the SavingsReportPage shows the cached pill
