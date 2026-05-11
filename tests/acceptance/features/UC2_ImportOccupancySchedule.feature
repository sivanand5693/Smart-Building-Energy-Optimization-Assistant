Feature: ImportOccupancySchedule

  Background:
    Given the FacilityManager is authenticated
    And a building "HQ-East" exists with zones "Floor-1" and "Floor-2"
    And the occupancy schedule store is empty

  Scenario: UC2-S01 Successfully import a valid occupancy schedule
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload occupancy rows for building "HQ-East":
      | zone    | timestamp           | occupancy_count |
      | Floor-1 | 2026-04-20T09:00:00 | 25              |
      | Floor-2 | 2026-04-20T09:00:00 | 15              |
    And I submit the import
    Then a confirmation showing "2 records imported" is displayed
    And the occupancy schedule contains 2 records
    And a record exists for zone "Floor-1" at "2026-04-20T09:00:00" with count 25
    And a record exists for zone "Floor-2" at "2026-04-20T09:00:00" with count 15

  Scenario: UC2-S02 Unknown zone_id identifies the offending row
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload raw CSV content:
      """
      zone_id,timestamp,occupancy_count
      999999,2026-04-20T09:00:00,25
      """
    And I submit the import
    Then an import error references row 2 and names the field "zone_id"
    And the occupancy schedule is empty

  Scenario: UC2-S03 Invalid timestamp identifies the offending row
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload occupancy rows for building "HQ-East" mixing valid and invalid:
      | zone    | timestamp           | occupancy_count |
      | Floor-1 | 2026-04-20T09:00:00 | 25              |
      | Floor-1 | not-a-timestamp     | 30              |
    And I submit the import
    Then an import error references row 3 and names the field "timestamp"
    And the occupancy schedule is empty

  Scenario: UC2-S04 Non-integer occupancy_count identifies the offending row
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload occupancy rows for building "HQ-East" mixing valid and invalid:
      | zone    | timestamp           | occupancy_count |
      | Floor-1 | 2026-04-20T09:00:00 | not-a-number    |
    And I submit the import
    Then an import error references row 2 and names the field "occupancy_count"
    And the occupancy schedule is empty

  Scenario: UC2-S05 Malformed header is reported with a header error
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload raw CSV content:
      """
      wrong_col_a,wrong_col_b,wrong_col_c
      1,2026-04-20T09:00:00,25
      """
    And I submit the import
    Then an import error indicates a header issue
    And the occupancy schedule is empty

  Scenario: UC2-S06 Empty file is rejected with a clear error
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload an empty CSV
    And I submit the import
    Then an import error indicates the file is empty
    And the occupancy schedule is empty

  Scenario: UC2-S07 Import of 1000 rows completes within the time limit
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload a generated CSV with 1000 valid occupancy rows for building "HQ-East"
    And I submit the import
    Then a confirmation showing "1000 records imported" is displayed
    And the import time is under 5000 milliseconds

  Scenario: UC2-S08 Zone belonging to another building is rejected
    Given a second building "HQ-West" exists with zone "WestWing-1"
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload a row referencing zone "WestWing-1" in building "HQ-West" at "2026-04-20T09:00:00" with count 12
    And I submit the import
    Then an import error references row 2 and names the field "zone_id"
    And the occupancy schedule is empty

  Scenario: UC2-S09 Negative occupancy_count identifies the offending row
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload occupancy rows for building "HQ-East" mixing valid and invalid:
      | zone    | timestamp           | occupancy_count |
      | Floor-1 | 2026-04-20T09:00:00 | -5              |
    And I submit the import
    Then an import error references row 2 and names the field "occupancy_count"
    And the occupancy schedule is empty

  Scenario: UC2-S10 Non-integer zone_id identifies the offending row
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload raw CSV content:
      """
      zone_id,timestamp,occupancy_count
      abc,2026-04-20T09:00:00,25
      """
    And I submit the import
    Then an import error references row 2 and names the field "zone_id"
    And the occupancy schedule is empty

  Scenario: UC2-S11 Wrong column count is reported as a row error
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload raw CSV content:
      """
      zone_id,timestamp,occupancy_count
      1,2026-04-20T09:00:00,25,extra
      """
    And I submit the import
    Then an import error references row 2 without naming a field
    And the occupancy schedule is empty

  Scenario: UC2-S12 Multiple invalid rows are all reported atomically
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload occupancy rows for building "HQ-East" mixing valid and invalid:
      | zone    | timestamp           | occupancy_count |
      | Floor-1 | not-a-timestamp     | 25              |
      | Floor-2 | 2026-04-20T09:00:00 | not-a-number    |
    And I submit the import
    Then an import error references row 2 and names the field "timestamp"
    And an import error references row 3 and names the field "occupancy_count"
    And the occupancy schedule is empty

  Scenario: UC2-S13 Blank lines between data rows are skipped, valid rows imported
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload raw CSV content for building "HQ-East" with blank lines:
      """
      zone_id,timestamp,occupancy_count
      {Floor-1},2026-04-20T09:00:00,25

      {Floor-2},2026-04-20T10:00:00,15
      """
    And I submit the import
    Then a confirmation showing "2 records imported" is displayed
    And the occupancy schedule contains 2 records

  Scenario: UC2-S14 Header with surrounding whitespace is tolerated
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload raw CSV content for building "HQ-East" with templated header:
      """
      zone_id ,  timestamp ,occupancy_count
      {Floor-1},2026-04-20T09:00:00,25
      """
    And I submit the import
    Then a confirmation showing "1 records imported" is displayed
    And the occupancy schedule contains 1 records

  Scenario: UC2-S15 Submit is disabled until both building and file are selected
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    Then the submit button is disabled

  Scenario: UC2-S16 File containing only a header row is rejected
    When I open Import Occupancy Schedule
    And I select building "HQ-East"
    And I upload raw CSV content:
      """
      zone_id,timestamp,occupancy_count
      """
    And I submit the import
    Then an import error indicates no data rows
    And the occupancy schedule is empty
