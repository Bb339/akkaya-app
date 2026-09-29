# Map provider contract

PROJECT_DATA reuses the existing V1 map instance and base layer. It does not create another L.map or install another tile layer. V1 initializes Esri Imagery and retains its existing OSM fallback for unavailable plugin conditions.

Reference overlays are removed from the same map and a project layer is added from backend Polygon, MultiPolygon or explicit point geometry only. Runtime invents no coordinates. Layer click and selector changes stay synchronized. Coverage messages are explicit for FULL, PARTIAL and NONE. The accepted 20-file package stays unchanged; the separate visual package supplies 24/24 polygons.
