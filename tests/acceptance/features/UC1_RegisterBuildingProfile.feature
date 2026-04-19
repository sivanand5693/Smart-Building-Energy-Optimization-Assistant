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
