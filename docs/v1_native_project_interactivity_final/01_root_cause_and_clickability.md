# Root-cause and interaction audit

Baseline: `e1c4cbe699da27d25e45ec73efe0dbfe7049a651` on the accepted deployed ancestry.

The accepted provider bridge left two product-level interaction defects:

1. `renderRun()` reopened the right drawer after every stored run. Its fixed scrim covered the native V1 workspace, so controls that were enabled in the DOM could not receive pointer input.
2. Project run detail was concentrated in the drawer's secondary result block instead of the existing V1 summary, parcel, benchmark, and comparison surfaces.
3. The project selector change handler was installed only in PROJECT_DATA initialization. After switching to AKKAYA_REFERENCE, the selector was visible but had no navigation handler.

The correction removes the scrim when the drawer closes, disables pointer events on the closed drawer, restores focus to the compact provider button, keeps the drawer closed after execution, installs the provider selector globally, places seed/preview next to the existing native optimization control, and projects backend-authoritative stored values into existing V1 surfaces. No browser scientific calculation or reference fallback was added.

The pre-change browser reproduction passed the old DOM-driven test while direct click evidence showed the drawer/scrim lifecycle as the interception risk. The final test checks `elementFromPoint`, bounding boxes, disabled and `aria-disabled` state, and computed `pointer-events` before each required click.
