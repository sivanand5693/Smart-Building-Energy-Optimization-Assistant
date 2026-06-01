# UC4 RecommendHVACSetpointChanges — Acceptance Status

| Field | Value |
|---|---|
| Status | pass |
| Scenarios | 17 / 17 |
| T4 cycles | 0 |
| Tested at | 2026-06-01 |

## Latest run

```
PYTHONPATH="./backend:." behave tests/acceptance/features/UC4_RecommendHVACSetpointChanges.feature
1 feature passed, 0 failed, 0 skipped
17 scenarios passed, 0 failed, 0 skipped
230 steps passed, 0 failed, 0 skipped, 0 undefined
Took 0m2.846s
```

## Regression (UC1 + UC2 + UC3 + UC4)

```
PYTHONPATH="./backend:." behave tests/acceptance/features/UC1_RegisterBuildingProfile.feature \
                                  tests/acceptance/features/UC2_ImportOccupancySchedule.feature \
                                  tests/acceptance/features/UC3_ForecastZoneDemand.feature \
                                  tests/acceptance/features/UC4_RecommendHVACSetpointChanges.feature
4 features passed, 0 failed, 0 skipped
67 scenarios passed, 0 failed, 0 skipped
728 steps passed, 0 failed, 0 skipped, 0 undefined
Took 0m11.187s
```

## Failure bundles

None.
