# Proxy, Resilience, and Structured Logging — Fix Tests & Create PR

## TL;DR

> **Quick Summary**: GitHub Issue #15 (User Story 3 / P3) is already fully implemented. The remaining work is fixing 3 failing tests with wrong field name assertions, exporting 2 missing exceptions from `__init__.py`, marking spec tasks as done, and creating a PR.
> 
> **Deliverables**:
> - 3 test assertions fixed (field name mismatches)
> - 2 missing exception exports added to public API
> - Spec tasks T038-T045, T052 marked complete
> - PR opened against `main` (Closes #15)
> 
> **Estimated Effort**: Quick
> **Parallel Execution**: NO — sequential (3 small changes then commit+PR)
> **Critical Path**: Fix tests → Export exceptions → Mark tasks → Run CI → Commit → PR

---

## Context

### Original Request
User asked to implement GitHub Issue #15 ("User Story 3 (P3): Proxy, resilience, and structured logging") and create an early PR against `main`.

### Interview Summary
**Key Findings (from extensive analysis session)**:
- ALL implementation code is already complete: `proxy.py`, `client.py` (retry/backoff, 429 handling, structured logging), `exceptions.py`, `config.py`
- ALL test infrastructure exists: `test_proxy_service.py` (17 tests), `test_logging.py` (11 tests), `test_resilience_and_logging.py` (11 tests)
- Only 3 tests fail due to test-code field name mismatches, not implementation bugs
- Two exceptions (`ProxyMisconfigurationError`, `UpstreamUnavailableError`) are implemented but not exported from `__init__.py`
- Spec docs already contain full documentation of error categories and structured logging schema

### Pre-existing Working Directory State
The working directory has pre-existing changes NOT related to this issue:
- Deleted `.specify/` files
- Modified `pyproject.toml` and `uv.lock`
- Untracked `AGENTS.md`

**CRITICAL**: Do NOT commit these. Only stage files explicitly modified by the tasks below.

---

## Work Objectives

### Core Objective
Fix the 3 failing test assertions, add missing exception exports, mark tasks complete, and open a PR.

### Concrete Deliverables
- All 170+ tests passing (currently 3 fail)
- `ProxyMisconfigurationError` and `UpstreamUnavailableError` exported from package
- Clean PR against `main` referencing Issue #15

### Definition of Done
- [ ] `uv run pytest tests/unit -v` → all pass (0 failures)
- [ ] `uv run pytest tests/integration -v -m "not live"` → all pass (0 failures)
- [ ] `uv run pyright wikidata_collector tests` → no errors
- [ ] `uv run ruff check wikidata_collector tests` → clean
- [ ] `uv run ruff format --check wikidata_collector tests` → clean
- [ ] PR created and URL returned

### Must Have
- Exact field name corrections (not behavioral changes)
- Exception exports matching README usage examples

### Must NOT Have (Guardrails)
- Do NOT modify any implementation code (proxy.py, client.py, models.py, etc.)
- Do NOT commit pre-existing working directory changes (.specify/, pyproject.toml, uv.lock, AGENTS.md)
- Do NOT change test logic or test intent — only fix wrong field/parameter names
- Do NOT add new tests — existing coverage is comprehensive
- Do NOT modify `specs/001-wikidata-etl-package/spec.md` or `research.md` content — they already document everything

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: Tests-after (tests already exist, we're fixing assertions)
- **Framework**: pytest (via `uv run pytest`)

---

## Execution Strategy

### Sequential Execution (Simple Task)

All tasks are sequential and small. No parallelization needed.

```
Task 1: Fix unit test assertion keys
Task 2: Fix integration test field names
Task 3: Export missing exceptions
Task 4: Mark spec tasks complete
Task 5: Run full CI suite, commit, push, create PR
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|------------|--------|
| 1 | None | 5 |
| 2 | None | 5 |
| 3 | None | 5 |
| 4 | None | 5 |
| 5 | 1, 2, 3, 4 | None |

---

## TODOs

- [ ] 1. Fix unit test parameter key assertions

  **What to do**:
  In `tests/unit/test_client_iterators.py`, the test `test_iter_with_filters` (class `TestIterPublicFigures`) asserts that `get_public_figures` was called with parameters `nationality` and `profession`. But `iter_public_figures` translates these: it passes `nationality` as `country=` and `profession` as `occupations=` to `get_public_figures` (see `client.py` lines 590-599).

  Apply this exact edit at lines 130-131:
  ```python
  # BEFORE (wrong — these are iter_public_figures param names, not get_public_figures):
  assert call_kwargs["nationality"] == "Q30"
  assert call_kwargs["profession"] == ["Q33999"]

  # AFTER (correct — these are the actual get_public_figures param names):
  assert call_kwargs["country"] == "Q30"
  assert call_kwargs["occupations"] == ["Q33999"]
  ```

  **Must NOT do**:
  - Do NOT change the test function name, docstring, or other assertions
  - Do NOT change lines 128-129 (birthday_from/birthday_to assertions are correct)
  - Do NOT change any other test in this file

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 2, 3, 4)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `tests/unit/test_client_iterators.py:110-131` — The test method `test_iter_with_filters`, lines 130-131 are the wrong assertions
  - `wikidata_collector/client.py:560-600` — `iter_public_figures` method showing how `nationality` is passed as `country=nationality` (line 594) and `profession` is passed as `occupations=profession` (line 595)

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: Unit test test_iter_with_filters passes after fix
    Tool: Bash
    Preconditions: uv sync --dev completed
    Steps:
      1. Run: uv run pytest tests/unit/test_client_iterators.py::TestIterPublicFigures::test_iter_with_filters -v
      2. Assert: exit code 0
      3. Assert: output contains "PASSED"
      4. Assert: output does NOT contain "FAILED"
    Expected Result: Test passes
    Evidence: Terminal output captured
  ```

  **Commit**: YES (groups with Task 2)
  - Message: `fix(tests): correct field name mismatches in iterator and integration tests`
  - Files: `tests/unit/test_client_iterators.py`, `tests/integration/test_iterate_public_figures.py`

---

- [ ] 2. Fix integration test field name assertions

  **What to do**:
  In `tests/integration/test_iterate_public_figures.py`, two tests reference model fields that don't exist on `PublicFigureNormalizedRecord`.

  **Fix 1 — `test_iterate_with_birthday_filters` (line 109):**
  
  The model has `birth_date` (a `datetime` object), not `birthday` (a string). The `_pf` helper at lines 16-28 converts the birthday string to `datetime.fromisoformat(birthday)`, so `birth_date` for `"1995-06-15T00:00:00"` is `datetime(1995, 6, 15, 0, 0)`.

  ```python
  # BEFORE (line 109):
  assert results[0].birthday == "1995-06-15T00:00:00Z"

  # AFTER:
  assert results[0].birth_date == datetime(1995, 6, 15)
  ```

  Note: `datetime` is already imported on line 8: `from datetime import datetime`

  **Fix 2 — `test_iterate_with_nationality_filter` (line 136):**
  
  The model has `countries` (List[str]), not `nationalities`. The `_pf` helper stores `nationalities` as `countries=list(nationalities or [])`.

  ```python
  # BEFORE (line 136):
  assert results[0].nationalities == ["United States"]

  # AFTER:
  assert results[0].countries == ["United States"]
  ```

  **Must NOT do**:
  - Do NOT change the `_pf` helper function (it correctly maps birthday→birth_date and nationalities→countries)
  - Do NOT change mock setup or test logic
  - Do NOT change any other assertions in these tests

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 1, 3, 4)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `tests/integration/test_iterate_public_figures.py:109` — wrong field `.birthday` (should be `.birth_date`)
  - `tests/integration/test_iterate_public_figures.py:136` — wrong field `.nationalities` (should be `.countries`)
  - `tests/integration/test_iterate_public_figures.py:16-28` — `_pf` helper showing field mapping: `birthday` param → `birth_date=datetime.fromisoformat(birthday)`, `nationalities` param → `countries=list(nationalities or [])`
  - `wikidata_collector/models.py:131-141` — `PublicFigureNormalizedRecord` class showing actual fields: `birth_date: Optional[datetime]`, `countries: List[str]`

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: Integration test test_iterate_with_birthday_filters passes
    Tool: Bash
    Preconditions: uv sync --dev completed
    Steps:
      1. Run: uv run pytest tests/integration/test_iterate_public_figures.py::TestIteratePublicFiguresHappyPath::test_iterate_with_birthday_filters -v
      2. Assert: exit code 0
      3. Assert: output contains "PASSED"
    Expected Result: Test passes
    Evidence: Terminal output captured

  Scenario: Integration test test_iterate_with_nationality_filter passes
    Tool: Bash
    Preconditions: uv sync --dev completed
    Steps:
      1. Run: uv run pytest tests/integration/test_iterate_public_figures.py::TestIteratePublicFiguresHappyPath::test_iterate_with_nationality_filter -v
      2. Assert: exit code 0
      3. Assert: output contains "PASSED"
    Expected Result: Test passes
    Evidence: Terminal output captured
  ```

  **Commit**: YES (groups with Task 1)
  - Message: `fix(tests): correct field name mismatches in iterator and integration tests`
  - Files: `tests/unit/test_client_iterators.py`, `tests/integration/test_iterate_public_figures.py`

---

- [ ] 3. Export missing exceptions from `__init__.py`

  **What to do**:
  Add `ProxyMisconfigurationError` and `UpstreamUnavailableError` to the public API exports in `wikidata_collector/__init__.py`. These exceptions are defined in `exceptions.py` and used in README examples but not currently exported.

  **Edit 1 — Add to import block (lines 9-15):**
  ```python
  # BEFORE:
  from .exceptions import (
      EntityNotFoundError,
      InvalidFilterError,
      InvalidQIDError,
      QueryExecutionError,
      WikidataCollectorError,
  )

  # AFTER:
  from .exceptions import (
      EntityNotFoundError,
      InvalidFilterError,
      InvalidQIDError,
      ProxyMisconfigurationError,
      QueryExecutionError,
      UpstreamUnavailableError,
      WikidataCollectorError,
  )
  ```

  **Edit 2 — Add to `__all__` list (lines 23-33):**
  ```python
  # BEFORE:
  __all__ = [
      "WikidataClient",
      "PublicFigureNormalizedRecord",
      "PublicInstitutionNormalizedRecord",
      "SubInstitution",
      "WikidataCollectorError",
      "InvalidQIDError",
      "EntityNotFoundError",
      "QueryExecutionError",
      "InvalidFilterError",
  ]

  # AFTER:
  __all__ = [
      "WikidataClient",
      "PublicFigureNormalizedRecord",
      "PublicInstitutionNormalizedRecord",
      "SubInstitution",
      "WikidataCollectorError",
      "InvalidQIDError",
      "EntityNotFoundError",
      "QueryExecutionError",
      "InvalidFilterError",
      "ProxyMisconfigurationError",
      "UpstreamUnavailableError",
  ]
  ```

  **Must NOT do**:
  - Do NOT modify `exceptions.py` — the classes already exist there
  - Do NOT change any other imports or exports

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 1, 2, 4)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `wikidata_collector/__init__.py:1-34` — Full file showing current imports and __all__
  - `wikidata_collector/exceptions.py` — Exception class definitions (ProxyMisconfigurationError, UpstreamUnavailableError already exist)
  - `README.md` error handling section — Shows usage of these exceptions in example code

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: Missing exceptions are now importable from package root
    Tool: Bash
    Preconditions: uv sync --dev completed
    Steps:
      1. Run: uv run python -c "from wikidata_collector import ProxyMisconfigurationError, UpstreamUnavailableError; print('OK')"
      2. Assert: exit code 0
      3. Assert: output contains "OK"
    Expected Result: Both exceptions importable from wikidata_collector
    Evidence: Terminal output captured

  Scenario: pyright passes on __init__.py
    Tool: Bash
    Steps:
      1. Run: uv run pyright wikidata_collector/__init__.py
      2. Assert: exit code 0
      3. Assert: output contains "0 errors"
    Expected Result: No type errors
    Evidence: Terminal output captured
  ```

  **Commit**: YES (separate commit)
  - Message: `feat(exports): add ProxyMisconfigurationError and UpstreamUnavailableError to public API`
  - Files: `wikidata_collector/__init__.py`

---

- [ ] 4. Mark spec tasks T038-T045, T052 as complete

  **What to do**:
  In `specs/001-wikidata-etl-package/tasks.md`, all User Story 3 tasks (T038-T045, T052) are marked `[ ]` but are fully implemented. Mark them as `[X]`.

  Lines 108-123 should change from `- [ ]` to `- [X]` for these tasks:
  - T038 (line 108)
  - T039 (line 109)
  - T040 (line 110)
  - T041 (line 111-115 — multi-line item, only change the first line's checkbox)
  - T042 (line 119)
  - T043 (line 120)
  - T044 (line 121)
  - T045 (line 122)
  - T052 (line 123)

  **Must NOT do**:
  - Do NOT change any task descriptions
  - Do NOT change any other tasks outside US3
  - Do NOT modify spec.md or research.md (they already have full documentation)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 1, 2, 3)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `specs/001-wikidata-etl-package/tasks.md:106-123` — User Story 3 task list with unchecked boxes
  - `specs/001-wikidata-etl-package/spec.md:232-336` — Already contains structured logging schema and error categories documentation (T052 content)

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: All US3 tasks are marked complete
    Tool: Bash
    Steps:
      1. Run: grep -c "\- \[ \] T0[3-5]" specs/001-wikidata-etl-package/tasks.md
      2. Assert: output is "0" (no unchecked US3 tasks remain)
      3. Run: grep -c "\- \[X\] T038\|\- \[X\] T039\|\- \[X\] T040\|\- \[X\] T041\|\- \[X\] T042\|\- \[X\] T043\|\- \[X\] T044\|\- \[X\] T045\|\- \[X\] T052" specs/001-wikidata-etl-package/tasks.md
      4. Assert: output is "9"
    Expected Result: All 9 US3 tasks marked [X]
    Evidence: Terminal output captured
  ```

  **Commit**: YES (separate commit)
  - Message: `docs(specs): mark User Story 3 tasks T038-T045, T052 as complete`
  - Files: `specs/001-wikidata-etl-package/tasks.md`

---

- [ ] 5. Run CI suite, commit, push, and create PR

  **What to do**:

  **Step 1: Run full CI checks:**
  ```bash
  uv run pytest tests/unit -v
  uv run pytest tests/integration -v -m "not live"
  uv run pyright wikidata_collector tests
  uv run ruff format --check wikidata_collector tests
  uv run ruff check wikidata_collector tests
  ```
  ALL must pass with zero failures/errors. If any fail, diagnose and fix before proceeding.

  **Step 2: Stage and commit (ONLY modified files — not pre-existing changes):**

  Commit 1 (test fixes):
  ```bash
  git add tests/unit/test_client_iterators.py tests/integration/test_iterate_public_figures.py
  git commit -m "fix(tests): correct field name mismatches in iterator and integration tests

Tests referenced wrong model field names (birthday→birth_date,
nationalities→countries) and wrong parameter keys (nationality→country,
profession→occupations)."
  ```

  Commit 2 (exception exports):
  ```bash
  git add wikidata_collector/__init__.py
  git commit -m "feat(exports): add ProxyMisconfigurationError and UpstreamUnavailableError to public API"
  ```

  Commit 3 (spec tasks):
  ```bash
  git add specs/001-wikidata-etl-package/tasks.md
  git commit -m "docs(specs): mark User Story 3 tasks T038-T045, T052 as complete"
  ```

  **Step 3: Push and create PR:**
  ```bash
  git push -u origin feature/proxy-resilience-logging
  ```

  Create PR using `gh pr create`:
  - **Title**: `feat: Implement proxy, resilience, and structured logging (User Story 3 / P3)`
  - **Base**: `main`
  - **Body** (use heredoc):
    ```
    ## Summary

    Closes #15

    This PR completes User Story 3 (P3): Proxy, resilience, and structured logging.

    ### What was already implemented (prior commits on `main`)
    - `wikidata_collector/proxy.py`: Full ProxyManager with round-robin rotation, SSRF prevention, failure detection with cooldown
    - `wikidata_collector/client.py`: Proxy-aware HTTP with retry/backoff, 429 Retry-After handling, 502/503/504 upstream error handling, structured logging via `_log_query_execution`, `_log_page_fetch`, `_log_retry_attempt`, `_log_query_failure`
    - `wikidata_collector/exceptions.py`: `ProxyMisconfigurationError`, `UpstreamUnavailableError` exception classes
    - `wikidata_collector/config.py`: Proxy configuration via `PROXY_LIST` env var
    - `tests/unit/test_proxy_service.py`: 17 unit tests for proxy behavior
    - `tests/unit/test_logging.py`: 11 unit tests for structured logging
    - `tests/integration/test_resilience_and_logging.py`: 11 integration tests for resilience

    ### What this PR fixes
    1. **Test assertion mismatches** — 3 tests referenced wrong field names:
       - `test_iter_with_filters`: `nationality`→`country`, `profession`→`occupations` (parameter name translation in `iter_public_figures`)
       - `test_iterate_with_birthday_filters`: `.birthday`→`.birth_date` (model field is `birth_date: datetime`)
       - `test_iterate_with_nationality_filter`: `.nationalities`→`.countries` (model field is `countries: List[str]`)
    2. **Missing public API exports** — Added `ProxyMisconfigurationError` and `UpstreamUnavailableError` to `__init__.py`
    3. **Spec task tracking** — Marked tasks T038-T045, T052 as complete

    ### Test results
    - Unit tests: 136 passing (was 135 passing, 1 failing)
    - Integration tests: 43 passing (was 41 passing, 2 failing)
    - All CI checks pass (pyright, ruff format, ruff check)
    ```

  **Must NOT do**:
  - Do NOT stage `.specify/`, `pyproject.toml`, `uv.lock`, or `AGENTS.md`
  - Do NOT use `git add .` or `git add -A`
  - Do NOT force push

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None (final task)
  - **Blocked By**: Tasks 1, 2, 3, 4

  **References**:
  - GitHub Issue #15 — The issue to close
  - `AGENTS.md` CI pipeline section — Lists exact commands for CI checks
  - `.github/workflows/` — CI workflow for reference

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: Full CI suite passes
    Tool: Bash
    Steps:
      1. Run: uv run pytest tests/unit -v
      2. Assert: exit code 0, 136 passed
      3. Run: uv run pytest tests/integration -v -m "not live"
      4. Assert: exit code 0, 43 passed (3 deselected)
      5. Run: uv run pyright wikidata_collector tests
      6. Assert: exit code 0, 0 errors
      7. Run: uv run ruff check wikidata_collector tests
      8. Assert: exit code 0
      9. Run: uv run ruff format --check wikidata_collector tests
      10. Assert: exit code 0
    Expected Result: All CI checks green
    Evidence: Terminal output captured

  Scenario: PR created successfully
    Tool: Bash
    Steps:
      1. Run: gh pr view --json url,state,title
      2. Assert: state is "OPEN"
      3. Assert: title contains "proxy" or "resilience"
      4. Assert: URL is returned
    Expected Result: PR exists and is open
    Evidence: PR URL captured and returned to user
  ```

  **Commit**: YES (see commit structure above)

---

## Commit Strategy

| After Task(s) | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1, 2 | `fix(tests): correct field name mismatches in iterator and integration tests` | `tests/unit/test_client_iterators.py`, `tests/integration/test_iterate_public_figures.py` | `uv run pytest tests/unit/test_client_iterators.py::TestIterPublicFigures::test_iter_with_filters tests/integration/test_iterate_public_figures.py -v` |
| 3 | `feat(exports): add ProxyMisconfigurationError and UpstreamUnavailableError to public API` | `wikidata_collector/__init__.py` | `uv run python -c "from wikidata_collector import ProxyMisconfigurationError, UpstreamUnavailableError"` |
| 4 | `docs(specs): mark User Story 3 tasks T038-T045, T052 as complete` | `specs/001-wikidata-etl-package/tasks.md` | grep for `[X]` on task lines |

---

## Success Criteria

### Verification Commands
```bash
uv run pytest tests/unit -v                    # Expected: 136 passed
uv run pytest tests/integration -v -m "not live"  # Expected: 43 passed, 3 deselected
uv run pyright wikidata_collector tests        # Expected: 0 errors
uv run ruff check wikidata_collector tests     # Expected: clean
uv run ruff format --check wikidata_collector tests  # Expected: clean
gh pr view --json url                          # Expected: PR URL
```

### Final Checklist
- [ ] All 3 failing tests now pass
- [ ] `ProxyMisconfigurationError` and `UpstreamUnavailableError` importable from `wikidata_collector`
- [ ] Spec tasks T038-T045, T052 marked `[X]`
- [ ] No pre-existing changes committed (`.specify/`, `pyproject.toml`, `uv.lock`, `AGENTS.md` NOT staged)
- [ ] PR open against `main` with "Closes #15" in body
- [ ] PR URL returned to user
