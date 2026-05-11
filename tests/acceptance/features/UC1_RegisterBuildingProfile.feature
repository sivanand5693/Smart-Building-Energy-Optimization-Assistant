Feature: RegisterBuildingProfile

  Background:
    Given the FacilityManager is authenticated
    And the Building Repository is operational and empty

  Scenario: UC1-S01 Successfully register a valid building profile
    When I open the Register Building Profile form
    And I enter building name "HQ-East"
    And I add zone "Floor-1-North" with device type "HVAC"
    And I add operating schedule "Mon-Fri 08:00-18:00"
    And I submit the form
    Then a confirmation with a building ID is displayed
    And the building "HQ-East" is saved in the Building Repository
    And the saved building has zone "Floor-1-North"
    And the saved zone has device type "HVAC"
    And the saved building has operating schedule "Mon-Fri 08:00-18:00"

  Scenario: UC1-S02 Missing building name shows specific field error
    When I open the Register Building Profile form
    And I leave the building name empty
    And I add zone "Floor-1-North" with device type "HVAC"
    And I add operating schedule "Mon-Fri 08:00-18:00"
    And I submit the form
    Then a validation error for field "buildingName" is displayed
    And no building is saved in the Building Repository

  Scenario: UC1-S03 Missing zone shows specific field error
    When I open the Register Building Profile form
    And I enter building name "HQ-East"
    And I add no zones
    And I add operating schedule "Mon-Fri 08:00-18:00"
    And I submit the form
    Then a validation error for field "zones" is displayed
    And no building is saved in the Building Repository

  Scenario: UC1-S04 Invalid schedule times show specific field error
    When I open the Register Building Profile form
    And I enter building name "HQ-East"
    And I add zone "Floor-1-North" with device type "HVAC"
    And I add operating schedule "Mon-Fri 18:00-08:00"
    And I submit the form
    Then a validation error for field "operatingSchedule" is displayed
    And no building is saved in the Building Repository

  Scenario: UC1-S05 Save completes within performance limit
    When I open the Register Building Profile form
    And I enter building name "HQ-East"
    And I add zone "Floor-1-North" with device type "HVAC"
    And I add operating schedule "Mon-Fri 08:00-18:00"
    And I submit the form
    Then the save time is under 4000 milliseconds

  Scenario: UC1-S06 Register building with multiple zones each with different device types
    When I open the Register Building Profile form
    And I enter building name "HQ-West"
    And I add zone "Floor-1-North" with device type "HVAC"
    And I add zone "Floor-2-South" with device type "Lighting"
    And I add zone "Basement" with device type "Sensor"
    And I add operating schedule "Mon-Fri 08:00-18:00"
    And I submit the form
    Then a confirmation with a building ID is displayed
    And the building "HQ-West" is saved in the Building Repository
    And the saved building has 3 zones
    And the saved zone "Floor-1-North" has device type "HVAC"
    And the saved zone "Floor-2-South" has device type "Lighting"
    And the saved zone "Basement" has device type "Sensor"

  Scenario: UC1-S07 Register building with multiple operating schedules
    When I open the Register Building Profile form
    And I enter building name "HQ-Central"
    And I add zone "Floor-1-North" with device type "HVAC"
    And I add operating schedule "Mon-Fri 08:00-18:00"
    And I add operating schedule "Sat-Sun 10:00-14:00"
    And I submit the form
    Then a confirmation with a building ID is displayed
    And the building "HQ-Central" is saved in the Building Repository
    And the saved building has operating schedule "Mon-Fri 08:00-18:00"
    And the saved building has operating schedule "Sat-Sun 10:00-14:00"

  Scenario: UC1-S08 Missing device type in a zone shows specific field error
    When I open the Register Building Profile form
    And I enter building name "HQ-East"
    And I add zone "Floor-1-North" with no device type
    And I add operating schedule "Mon-Fri 08:00-18:00"
    And I submit the form
    Then a validation error for field "deviceType" is displayed
    And no building is saved in the Building Repository

  Scenario: UC1-S09 Missing operating schedule shows specific field error
    When I open the Register Building Profile form
    And I enter building name "HQ-East"
    And I add zone "Floor-1-North" with device type "HVAC"
    And I add no operating schedule
    And I submit the form
    Then a validation error for field "operatingSchedule" is displayed
    And no building is saved in the Building Repository

  Scenario: UC1-S10 Duplicate zone names within the same building show field error
    When I open the Register Building Profile form
    And I enter building name "HQ-East"
    And I add zone "Floor-1-North" with device type "HVAC"
    And I add zone "Floor-1-North" with device type "Lighting"
    And I add operating schedule "Mon-Fri 08:00-18:00"
    And I submit the form
    Then a validation error for field "zones" is displayed
    And no building is saved in the Building Repository

  Scenario: UC1-S11 Building name of 100 characters is accepted without truncation
    When I open the Register Building Profile form
    And I enter a building name of length 100
    And I add zone "Floor-1-North" with device type "HVAC"
    And I add operating schedule "Mon-Fri 08:00-18:00"
    And I submit the form
    Then a confirmation with a building ID is displayed
    And the saved building name has length 100

  Scenario: UC1-S12 Multiple validation errors reported together on a single submit
    When I open the Register Building Profile form
    And I leave the building name empty
    And I add no zones
    And I add no operating schedule
    And I submit the form
    Then a validation error for field "buildingName" is displayed
    And a validation error for field "zones" is displayed
    And a validation error for field "operatingSchedule" is displayed
    And no building is saved in the Building Repository

  Scenario: UC1-S13 Form state preserved after validation failure
    When I open the Register Building Profile form
    And I enter building name "HQ-East"
    And I add zone "Floor-1-North" with device type "HVAC"
    And I add operating schedule "Mon-Fri 18:00-08:00"
    And I submit the form
    Then a validation error for field "operatingSchedule" is displayed
    And the building name field still shows "HQ-East"
    And the zones list still contains "Floor-1-North"

  Scenario: UC1-S14 Two buildings with the same name are both persisted with distinct IDs
    When I open the Register Building Profile form
    And I enter building name "HQ-East"
    And I add zone "Floor-1-North" with device type "HVAC"
    And I add operating schedule "Mon-Fri 08:00-18:00"
    And I submit the form
    And I open the Register Building Profile form
    And I enter building name "HQ-East"
    And I add zone "Floor-2-North" with device type "Lighting"
    And I add operating schedule "Mon-Fri 09:00-17:00"
    And I submit the form
    Then the Building Repository contains 2 buildings named "HQ-East"
    And the two saved buildings have distinct IDs

  Scenario: UC1-S15 Whitespace-only building name is rejected as missing
    When I open the Register Building Profile form
    And I enter building name "   "
    And I add zone "Floor-1-North" with device type "HVAC"
    And I add operating schedule "Mon-Fri 08:00-18:00"
    And I submit the form
    Then a validation error for field "buildingName" is displayed
    And no building is saved in the Building Repository

  Scenario: UC1-S16 Schedule with equal start and end time is rejected
    When I open the Register Building Profile form
    And I enter building name "HQ-East"
    And I add zone "Floor-1-North" with device type "HVAC"
    And I add operating schedule "Mon-Fri 08:00-08:00"
    And I submit the form
    Then a validation error for field "operatingSchedule" is displayed
    And no building is saved in the Building Repository

  Scenario: UC1-S17 Confirmation displays the persisted building ID and it matches the stored record
    When I open the Register Building Profile form
    And I enter building name "HQ-East"
    And I add zone "Floor-1-North" with device type "HVAC"
    And I add operating schedule "Mon-Fri 08:00-18:00"
    And I submit the form
    Then a confirmation with a building ID is displayed
    And the displayed building ID matches the ID of the saved building "HQ-East"
