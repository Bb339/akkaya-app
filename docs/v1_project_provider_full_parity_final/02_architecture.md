# Architecture

## Institutional path

`/projects` -> Smart Import -> explicit confirmation -> project revision -> decision-context -> backend preview -> pinned revision/selection hash -> analysis creation -> optimizer -> immutable stored run -> provider adapter -> existing V1 workspace.

## Presentation boundary

The adapter supplies PROJECT_DATA values to the native selector, Leaflet map, current/recommended tables, summary, water and profit charts, monthly-water surface, crop composition, warnings, selected-unit result, benchmark, rationale, and provenance. The retired `#v1-project-result` container remains hidden and empty. The provider drawer is limited to source/project/readiness controls.

`AKKAYA_REFERENCE` keeps the accepted reference fetch/render pipeline. `PROJECT_DATA` uses project APIs exclusively; malformed context fails closed.
