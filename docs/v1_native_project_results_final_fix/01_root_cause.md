# Root cause

Baseline `3508fc158443a1f0c5d1bed2d0669940a7395b7c` hid the provider drawer result block with CSS, but `renderRun()` continued to populate that hidden subtree. The visible V1 surface received only abbreviated text in a few existing nodes, so crop composition, HHI, provenance and complete budget/monthly details were not available in the user-visible result workspace. The native budget badges also retained their frozen placeholder values.

Static V1 parcel labels were not bound to the active provider. PROJECT_DATA therefore displayed reference terminology even though its canonical selection and map objects were analysis units. Monthly violation labels concatenated two backend lists without presentation-layer de-duplication.

The correction removes all result writes to the retired drawer sink, creates one result section inside the existing visible V1 metrics card, binds provider terminology at runtime, and de-duplicates only the rendered violation-month list. Backend values and scientific calculations are not changed.
