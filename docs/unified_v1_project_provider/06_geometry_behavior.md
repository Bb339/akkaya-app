# Geometry behavior

Geometry is project input and is never borrowed from Akkaya.

- **FULL:** every project unit with a Polygon, MultiPolygon or valid latitude/longitude point is rendered.
- **PARTIAL:** only units with project geometry are rendered; all units remain in the selector and the exact covered/total count is shown.
- **NONE:** no coordinate is fabricated; the selector and analysis remain usable and the map explains that geometry was not provided.

Map clicks select the corresponding project identity. Selector changes focus matching geometry when present. Duplicate unit identity fails in the backend projection before rendering.

