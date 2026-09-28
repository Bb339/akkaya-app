# Workspace Navigation Fix1

## Root cause

The accepted Fix2 workspace requires one exact `project` key in the URL hash. The existing workflow links replaced that complete hash with DOM-only fragments such as `#analysis-section`. A normal section click therefore removed the authoritative project identity and correctly triggered the Fix2 fail-closed state.

## Canonical URL state

Workspace-generated URLs use:

`#project=<percent-encoded-project-id>&section=<allowed-section>`

`project` remains authoritative. It must occur exactly once, decode successfully, be non-empty, and identify an existing project. No default project and no Akkaya/reference fallback is used.

`section` is optional for compatibility with accepted Fix2 links. Workspace navigation, card selection, and project creation write it explicitly. Its allowlist is:

- `project`
- `data`
- `readiness`
- `analysis`
- `result`
- `provenance`
- `reference`

An unknown, empty, duplicate, or malformed `section` keeps the exact valid project, displays an explicit message, and normalizes the URL to `section=project`. It never changes or fabricates project identity. A legacy section-only fragment has no project identity and remains fail-closed.

## Navigation behavior

Workflow links update the canonical hash and retain the loaded project. Hash changes and browser back/forward restore the exact project and allowed section deterministically. Section changes within one project do not clear a rendered stored result. If `section=result` is requested before a result is loaded, the immutable run history is shown with an explicit instruction to select a run or start an analysis.

Stored-run selection and analysis completion write `section=result`. The decision screen return link writes the exact originating project with `section=result`.

## Scope boundary

This correction changes only project workspace HTML/JavaScript, focused browser expectations, and this report. It does not change scientific calculations, optimization or scoring, readiness semantics, adapters, datasets, candidate matrices, robustness evidence, or the frozen V1 `index.html`.

No push, deployment, tag, or Render service change is part of this milestone.
