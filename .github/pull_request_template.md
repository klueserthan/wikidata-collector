## Description

<!-- Provide a clear and concise description of your changes -->

## Related Tasks

<!-- Link to tasks from specs/001-wikidata-etl-package/tasks.md -->

- Addresses task: <!-- e.g., T1.1, T2.3 -->
- Relates to user story: <!-- e.g., US1, US2 -->

## Type of Change

<!-- Mark with an 'x' all that apply -->

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)

## Pre-Commit Checklist

Before requesting review, I have:

### Branch & Base
- [ ] Created this branch from `001-wikidata-etl-package` (NOT from `main`)
- [ ] Set PR base to `001-wikidata-etl-package` (verified below title)

### Code Quality (CI Checks)
- [ ] Run `uv run pyright wikidata_collector tests` and fixed all type errors
- [ ] Run `uv run ruff format wikidata_collector tests` to format code
- [ ] Run `uv run ruff check --fix wikidata_collector tests` and resolved all lint issues
- [ ] Or run `.github/scripts/pre-commit-checks.sh` for all checks

### Testing
- [ ] Run unit tests locally (`uv run pytest tests/unit -v`) and they pass
- [ ] Run integration tests locally (`uv run pytest tests/integration -v -m "not live"`) and they pass
- [ ] Added unit tests for new functionality (if applicable)
- [ ] Tests follow TDD principles (written before implementation)
- [ ] Code coverage maintained or improved

### Documentation & Specs
- [ ] Consulted relevant specs in `specs/001-wikidata-etl-package/` before implementing
- [ ] Updated docstrings for new/modified public APIs
- [ ] Updated README if user-facing behavior changed
- [ ] Followed design decisions documented in `specs/001-wikidata-etl-package/research.md`

### CI & Constitution
- [ ] Verified CI is green on this PR
- [ ] Followed constitution requirements (`.specify/memory/constitution.md`)
- [ ] Semantic versioning impact considered (if API changes)

## Testing Strategy

<!-- Describe how you tested your changes -->

### Unit Tests
<!-- List new or modified unit tests -->

### Integration Tests
<!-- List new or modified integration tests, if applicable -->

### Manual Testing
<!-- Describe any manual testing performed -->

## Breaking Changes

<!-- If this is a breaking change, describe the impact and migration path -->

## Additional Notes

<!-- Any additional context, screenshots, or information that reviewers should know -->

---

**Constitution Compliance**: This PR adheres to the [Wikidata Collector Constitution](.specify/memory/constitution.md), including TDD workflow, semantic versioning, and CI quality gates.
