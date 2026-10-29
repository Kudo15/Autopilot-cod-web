# Task 002 independent review

## Scope and evidence

- Reviewed the uncommitted scoped worker files `backend/app/ingest/normalize.py`,
  `backend/app/ingest/__init__.py`, and `backend/tests/test_normalize.py` against
  `.team/tasks/task-002.md` and the supplied review package. The unrelated modified
  `AGENTS.md` was not attributed to this task.
- `python -m unittest backend.tests.test_normalize -v` — exit 0; 5 tests passed.
- `git diff --check` — exit 0 (only a CRLF warning for unrelated `AGENTS.md`).
- `python -m unittest discover -v` — exit 1, not a Task 002 regression finding:
  `backend.tests.test_public_articles` cannot import `fastapi` in the current Python
  environment. The five Task 002 tests passed before that import error.
- Reproduced URL edge cases directly: a URL with user-info loses that authority
  component, and an IPv6 URL becomes `https://2001:db8::1/x` without brackets.

## Layer 1 — spec compliance

The module provides the required public interface and immutable result fields. It
validates required title/content/source/timestamp fields, normalizes title Unicode and
whitespace, generates a SHA-256 hash, retains provenance, and has focused tests for the
requested core cases. It is pure and uses no file, network, command, or logging APIs.

## Layer 2 — code quality and security

### Findings

- [P2] `backend/app/ingest/normalize.py:53-62` — canonicalization reconstructs the
  netloc solely from `parts.hostname` and `parts.port`. This silently discards URL
  user-info and emits invalid bracket-less IPv6 authorities (for example,
  `https://[2001:db8::1]/x` becomes `https://2001:db8::1/x`). Both behaviors change or
  break a valid HTTP(S) URL, contrary to the requirement to canonicalize without
  changing URL semantics. Preserve a validated user-info/IPv6 authority when rebuilding
  it, or explicitly reject user-info if that input class is intentionally unsupported;
  add regression tests for the supported behavior.

No P1 findings. No P3 findings with evidence.

## Verdict

VERDICT: CHANGES_REQUESTED — Fix the P2 canonical-URL authority reconstruction and add its regression coverage; full-suite verification remains NOT_VERIFIED because FastAPI is unavailable in this Python environment.
