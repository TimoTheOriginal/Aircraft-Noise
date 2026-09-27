# Version 0.2 update

See README.md for current controls and calculations. Version 0.3 uses traceable two-axis linear interpolation for the aircraft noise matrices and retains Clause 3.1.4 highest-case selection. This interpolation is an engineering implementation choice, not a method prescribed by AS 2021:2015. Contract 1.0.0 gains additive optional fields.

---

# Aircraft basis contract / 1.0.0

Project 1 produces `aircraft-basis`. It consumes no other module's package. Required payload top-level names and common Quantity, Issue, SourceRecord, Spectrum, manifest fields follow the supplied prompt. Numerical values use finite JSON numbers or null; NaN is rejected at serialization. Numerical display rounding does not modify exported precision.

The result returned by `build_aircraft_basis` is a service envelope: `payload`, `sources`, `issues`, `data_mode`, `revision`, `request`. `payload` becomes `aircraft_basis.json`. Calculation results are deterministic for identical request and data bytes. Export inserts a fresh UUID and UTC time in the manifest, never into the deterministic payload. No Python objects or absolute file paths are required by a consumer.

## Nested field dictionary

| Field | Meaning / units |
|---|---|
| `site.receptors[]` | Stable receptor ID, latitude/longitude degrees in EPSG:4326, user confirmation, source description, elevation metres and vertical datum or null |
| `site.runway_geometry[]` | One runway/receptor pair; signed projection, runway length, DS and finite segment distance in m; DL/DT are null for beside-runway geometry |
| `signed_projection_m` | Dot product from end_1 toward end_2; retains direction |
| `projection_lon_lat` | Perpendicular projection onto infinite centreline in WGS84 [longitude, latitude] |
| `nearest` | Minimum finite centreline-segment distance among three supplied runways; never acoustic governing status |
| `anef.receptors[].actual_band` | Lower / upper contour numbers; null lower below 20, null upper inside highest contour; both null outside coverage |
| `project_contour_label` | Higher bounding contour for an inter-contour band; highest contour for open-ended band; null below20/outside; exact contour on mapped boundary |
| `boundary_distance_m` | Minimum metric distance to any contour boundary; tolerance separately recorded |
| `coverage_status` | `within_provisional_viewport` or `outside_coverage`; viewport is not independently verified map-panel extent |
| `report_required` | true below20 under project rule; null elsewhere pending broader workflow decisions |
| `operation_cases[]` | Stable ID, receptor, aircraft, direction, load, table and relevance evidence; raw/corrected geometry, terrain record, lookup trace, exterior Quantity, spectrum reference or null, issues |
| `noise_tables` request object | Keyed table IDs; increasing irregular distance row axis and DS column axis in metres; dB(A) cells; blanks/asterisks remain nonnumeric |
| `terrain_tables` request object | Keyed operation-specific columns with ordered [absolute height difference m, distance correction m] rows |
| `lookup_trace` | Zero-based row/column, raw source value and nonzero weight for every used cell |
| `governing_exterior[]` | Receptor, tied highest assessed case IDs, Quantity and explicit provisional selection basis |
| `criterion_catalogue[]` | Stable criterion ID, building/activity, source-linked Quantity and applicability notes; no per-room assignment |
| `review_decisions[]` | Manual override records preserve computed values, proposed value, reason, reviewer and supplied timestamp; not professional approval |

## Validation and ownership boundaries

The schema files for `room-results` and `report-issue` preserve required top-level names only and are explicitly placeholders for owner-defined nested schemas. This module does not validate those package types. Aircraft geometry/audit nested objects permit implementation-specific details; consumer adapters must resolve differences explicitly before integration. This is a development contract, not evidence of agreement with missing downstream modules.

Unknown source IDs, duplicate request source IDs, mismatched spectrum arrays, invalid CRS/coordinates and malformed table axes produce errors. Package validation checks canonical payload/sources paths, SHA-256 exact saved bytes, traversal/absolute paths, source references, asset inventory and matching project/assessment IDs. Synthetic or blocked packages cannot be marked approved. Approval signatures are not created or authenticated by this implementation.

The UI allocates monotonically increasing revisions per project+assessment in SQLite. CLI callers provide `revision` and must maintain monotonicity in their own export ledger; destination overwrite is rejected. Preserve incoming bytes/IDs in future consumers. Any altered payload needs a new export; prior approvals never carry over. Unsupported major versions are rejected by the exact 1.0.0 schema. A migration or adapter must be explicit and tested.
