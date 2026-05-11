# UC1-S14 Failure Bundle — Unique-Name Constraint Blocks Duplicate Building Names

## Input

- **Use case:** UC1 RegisterBuildingProfile
- **Failing scenario:** UC1-S14 Two buildings with the same name are both persisted with distinct IDs
- **Expected result:** Two rows in `buildings` with `name = 'HQ-East'` and distinct `id`s; confirmation panel visible after each of the two submits.
- **Actual result:** Only one row was persisted. The second submit silently failed (the UI never showed a confirmation, and the first submit's confirmation was still on screen when the assertion ran, but the DB still showed exactly one row named `HQ-East`).
- **Database state:** `SELECT COUNT(*) FROM buildings WHERE name = 'HQ-East'` returned **1**, not the expected 2.
- **Logs / stack trace:**
  ```
  Assertion Failed: expected 2 buildings named 'HQ-East'; found 1
  ```
  No Python traceback — the failure is in the `then` step, not the action. The second `POST /api/buildings` request returned 500 (Postgres `UniqueViolation`) but the page kept the prior confirmation visible so Playwright's `wait_for_function(...confirmation-panel OR error...)` returned immediately on the stale element.
- **Relevant code:**
  - `backend/app/infrastructure/models/building_model.py` line 12 — `name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)`
  - `backend/app/services/building_service.py` — `register_building_profile` (no pre-check for name uniqueness; relies on DB)
  - `backend/app/api/routes/building.py` — only catches `ValidationFailure`, not `IntegrityError`
  - The Alembic migration that originally created `buildings` (with `unique=True` on `name`)

---

## A) Failure Summary

- Scenario S14 is explicit: registering the same `building_name` twice must produce **two** persisted rows with **distinct IDs**.
- The current schema declares `buildings.name` `UNIQUE`, so the second insert raises a Postgres `UniqueViolation`, propagated as SQLAlchemy `IntegrityError` and surfaced by FastAPI as a 500.
- The acceptance contract in T1 (Assumption set, oracle list, and acceptance check table) treats `building_name` as **not unique** — only IDs must be distinct.
- This is a schema/contract mismatch, not a service-logic bug. The fix has to land in the model + a migration.

## B) Root Cause Hypothesis

`BuildingModel.name` was declared `unique=True` during the original UC1 T3 implementation. The structured requirement for UC1 (Assumption A1 and the related acceptance checks) does not mandate name uniqueness; in fact S14 explicitly contradicts it. The DB-level unique constraint was an over-tightening that S14 now exposes.

## C) Candidate Fix Options

### Option 1 — Drop the unique constraint via a new Alembic migration (recommended)
1. Edit `backend/app/infrastructure/models/building_model.py` to remove `unique=True` from the `name` column.
2. Generate (or hand-write) an Alembic migration that does `op.drop_constraint("buildings_name_key", "buildings", type_="unique")` (or whatever the auto-generated constraint name is — confirm via `\d buildings`).
3. Apply to both `smart_building_dev` and `smart_building_test` (`alembic upgrade head` and `TESTING=1 alembic upgrade head`).
4. No service or UI changes — `_validate` already does not check uniqueness; the repository will simply commit the second insert.

- **Pros:** matches the T1 contract exactly; minimal code change; preserves all other scenarios; no error-shape translation needed.
- **Cons:** drops a defensive guardrail (admittedly one that contradicts the spec). Two operators could accidentally create same-named buildings — but the acceptance suite explicitly requires this.
- **Risk:** low. Migration is reversible. Need to confirm the auto-generated constraint name on the existing DB before writing the `down_revision`/`downgrade` halves.

### Option 2 — Keep the unique constraint and revise T1
Treat the constraint as the source of truth and rewrite S14 to assert that the second submit produces a duplicate-name error keyed under `buildingName`.

- **Pros:** preserves the existing safety net.
- **Cons:** **violates the project's hard rule** — we never edit `.feature` files (or the underlying T1 contract) to make a test pass. Rejected by the methodology.
- **Risk:** would invalidate the user-approved T1.

### Option 3 — Soft-uniqueness in the service, with a flag to bypass
Add a `_validate` check that rejects duplicate building names, but expose an "allow duplicates" toggle (header/query param) the harness sets for S14.

- **Pros:** none that justify the complexity.
- **Cons:** introduces test-only branching in production code; contradicts the user-approved T1 (which clearly states two buildings with the same name should both persist).
- **Risk:** high — bad pattern, defeats the contract.

### Recommendation

**Option 1.** The constraint was a UC1-T3 oversight, S14 was specifically added in the expansion to capture this case, and dropping the constraint is the single-line model change + one short migration that brings the schema back in line with the approved contract.

## D) Verification Notes

After applying Option 1, re-run:

- **UC1-S14** — must show 2 rows in `buildings` named `HQ-East` with distinct IDs.
- **UC1-S01, S06, S07, S11, S17** — happy paths must still pass (no regression from dropping the constraint).
- **UC1-S02, S03, S04, S08, S09, S12, S13, S15, S16** — all field-error scenarios still produce their expected error keys.
- **Full UC1 regression** — must end at 17/17 once S10 is also fixed.
- **Full project regression** — UC2 and UC3 should be unaffected (no other UC depends on `buildings.name` being unique).

Expected post-patch result for S14 in isolation: pass.

### Migration sketch
```python
# alembic/versions/<rev>_uc1_drop_buildings_name_unique.py
def upgrade():
    op.drop_constraint("buildings_name_key", "buildings", type_="unique")

def downgrade():
    op.create_unique_constraint("buildings_name_key", "buildings", ["name"])
```
Confirm the exact constraint name with `psql smart_building_test -c '\d buildings'` before applying.
