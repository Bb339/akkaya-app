# Root-cause audit

Baseline: b0745a6138030a5131b5584d206ba35e60826055.

1. The provider integration injected a full-width section into the V1 header row. Its normal document flow increased page height and displaced the accepted V1 hierarchy.
2. PROJECT_DATA removed the native Leaflet instance and created a second OSM-only map. This discarded V1 Esri Imagery and made project mode look like another application.
3. The accepted 20-file fixture contains only two explicit points and no polygon dataset, so sparse coverage was correct but unsuitable for a full visual demonstration.
4. Synthetic classification is authoritative only when the exact project metadata contract is persisted. Names and similar free text remain irrelevant.
5. Frozen V1 reference labels could remain stale after reference requests were blocked. Project mode now replaces them with project identity or an explicit unavailable state.
6. Current water, profit and efficiency are not canonical fields in the accepted input contract. Browser-calculated substitutes are prohibited, so missing states are explicit.
7. Smart Import lacked a non-blocking state for a clearly unrelated supported file.
8. V1 sent GA configuration keys when ACO or ABC was selected. The adapter now uses each engine existing explicit parameter contract.
