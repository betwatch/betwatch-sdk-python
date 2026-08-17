# Papercuts

2026-08-15T16:40:35.381475Z - gpt-5.6-sol - jamie

checking the local API before the SDK example → the health endpoint returned 401 and short-circuited the chained example; run the authenticated SDK check directly

2026-08-17T08:05:59.79283Z - claude-opus-5 - jamie

Ran ty on a test file using mypy-style '# type: ignore[attr-defined]' → ty does not honour the bracketed error code and still reported unresolved-attribute; fixed by typing pytest.raises() with the concrete exception class instead of Exception.

2026-08-17T08:05:59.82282Z - claude-opus-5 - jamie

Pre-commit ruff hook was pinned at v0.8.1 while the uv lock resolved ruff 0.14.6 → hook and CI could disagree on formatting; replaced the remote hook with a local 'uv run ruff' hook so there is only ever one ruff version.
