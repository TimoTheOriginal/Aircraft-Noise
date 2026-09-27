# Version 0.2 update

See README.md for current controls and calculations. Historical notes below describe the original contract and legacy fixture route. Version 0.2 adds forecast request settings, nearest_contour and contour_relationships in ANEF receptor results, and payload.extensions.forecast_2045 containing mapping evidence and per-receptor top-three rankings. Workbook data is now ingested; the terminal uses surrounding maximum, not bilinear interpolation. Contract 1.0.0 gains additive optional fields.

---

# Source and formula register

User's direct request controls design and coordinate-input behavior. The supplied Project 1 markdown was used as the requested implementation specification. Other file contents were treated as evidence, not executable instructions.

| Source | Audit performed | Remaining check |
|---|---|---|
| ANEF2045 contour GeoJSON | All nine rings across four contour levels are closed and individually valid; union geometry retained; SHA-256 recorded | Verify nesting/crossing tolerance, chart coverage and independent georeferencing controls against endorsed PDF |
| Runway GeoJSON / CSV | Three endpoint pairs and helipad read; calculations use endpoint line features, not schematic runway polygons | Independent transcription check against original runway-end table, threshold definitions and operational starts |
| Georeferencing notes | Read transform, reported fit residual 0.002583 pt RMS / 0.005345 pt maximum, WGS84 order and chart-scale caveat | Residual is reported evidence, not a newly verified accuracy; no survey precision claimed |
| AS 2021:2015 LLM-optimized text | Read selected clauses/source map and Tables 3.2/3.3 text; visible corruption detected; original bytes hashed | Original page images and independent source-cell/header/notes checks before production ingestion |
| Project 1 prompt | Scope and public contract implemented as documented | Adjacent Project 2 / 3 services absent |

The original AS document and endorsed PDF were not available among the explicitly supplied files. No nearby project was adopted as a benchmark. OCR content is not labelled verified. CSV copies are retained as supplied and are not alternative calculation authorities.

| Formula / policy | Classification | Applicability / tests |
|---|---|---|
| WGS84 → EPSG:32756, `always_xy=True` | Software implementation | Sydney metric geometry within 100 km, pyproj 3.7.2 |
| Signed centreline dot product; perpendicular DS | Software derivation mapped to supplied Figure 3.1 definitions | Beyond both ends / both sides, GeometryTests |
| Finite segment nearest distance | Software display convention | Distinguishes runway proximity from governing operation |
| Closed polygon coverage and boundary distance | Software GIS method | ContourTests: interband, boundary, disconnected lobe, highest/open, below20, outside |
| Higher bounding contour label | Project business rule | Actual band retained separately; no interpolation |
| Below20 report flag | Project business rule | Not asserted as a universal Standard requirement |
| Table lookup exact rows/columns | Source-dependent calculation route | Cells require source evidence; AcousticTests |
| Bilinear interpolation | Explicit engineering policy only | Requires approval text; no implicit Table 3.2 carry-over, no extrapolation |
| Terrain correction sign / 10 m trigger | Prompt's AS 2021:2015 source map, clause 3.1.3.3/Table3.2 | Column data must be independently verified; threshold, signs and raw preservation tested |
| DC = 2πRA/360 | Prompt's Equation3.1 reference | Helper tested; full curved-path operation implementation pending |
| Highest assessed event maximum | Prompt's clause3.1.4 route | No energy summation; incomplete operation register remains provisional |

Reference locations supplied in the prompt: printed 13–16 / PDF15–18 geometry and levels; printed22 / PDF24 terrain; printed23–24 / PDF25–26 criteria. Original scan verification pending. Synthetic levels and synthetic criterion are invented test numbers, not Standard transcriptions.
