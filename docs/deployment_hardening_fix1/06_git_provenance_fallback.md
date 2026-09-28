# Git provenance fallback

Run provenance still invokes `git rev-parse HEAD` when available. A successful lookup preserves the exact SHA in `engine_commit` and records `engine_commit_status = AVAILABLE`.

Missing Git, missing repository metadata, nonzero `rev-parse`, and subprocess errors no longer crash analysis orchestration. They record `engine_commit = null` and `engine_commit_status = UNAVAILABLE`. No placeholder or invented SHA is used.

