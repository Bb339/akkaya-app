# Execution profile contract

Every new analysis request resolves an explicit `execution_profile`.

## REFERENCE_DEMO

Uses the accepted reference or project-explicit demo path. Results carry `REFERENCE MODEL / DEMO DATA` and `REFERENCE_MODEL_OUTPUT`. It may preserve documented legacy assumptions. It never claims official or verified institutional evidence.

## VERIFIED_INSTITUTIONAL

Resolves only active, confirmed, project-year and scope-compatible contract datasets. Resolution fails closed before bundle construction. There is no automatic switch to `REFERENCE_DEMO`. Real inputs receive `VERIFIED INSTITUTIONAL INPUTS`; the checked-in acceptance project receives `SYNTHETIC / NOT_OFFICIAL` and `SYNTHETIC_TEST_OUTPUT`.

The legacy API default remains `REFERENCE_DEMO` for backward-compatible clients. Institutional callers must send the profile explicitly, and dry-run returns the selected profile before execution.
