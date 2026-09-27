# Version 0.2 update

See README.md for current controls and calculations. Version 0.3 uses traceable two-axis linear interpolation for the aircraft noise matrices and retains Clause 3.1.4 highest-case selection. This interpolation is an engineering implementation choice, not a method prescribed by AS 2021:2015. Contract 1.0.0 gains additive optional fields.

---

# Integration / Project 1

Produced package: `aircraft-basis`, shared contract **1.0.0**, Draft 2020-12 schemas. Consumed packages: none. Python package name: `aircraft_noise`.

Public commands and APIs are documented in README. UI and CLI use the same deterministic core. `fixtures/synthetic-request.json` and `fixtures/synthetic-aircraft-basis/` are the provider fixture; `ContractTests` validates the package as a prospective consumer. Rerun `python -m unittest discover -s tests -v` when Projects 2 / 3 arrive. Import the exact package UUID and payload SHA-256, never just its project ID.

Required assets are relative `assets/site-map.svg` and source/payload JSON covered by the manifest. GeoJSON and the Standard source text remain in the local source repository. Exports contain source hashes, not the licensed Standard. Map SVG carries a preliminary/data-mode label. Missing spectra and criteria are visible issues, never inferred from overall levels or rooms.

Supported calculations: point contour bands, straight runway geometry, supported-direction exact table lookup, explicitly approved bilinear interpolation, operation-specific terrain correction, maximum assessed candidate. These routes remain preliminary for real projects until inputs/evidence are verified. Curved tracks, footprints, displaced thresholds, automatic aircraft mapping/forecast ingestion, measured design comparisons and additional airport packages are not production routes.

Open decisions: reconcile nested aircraft fields with downstream module schemas; adopt a complete independently reviewed airport/reference package; verify coverage and controls; nominate real-project benchmark; establish reviewer identities and evidence/signature verification. A request's `verified` reference tag is an input assertion, not a software-generated professional certification. All supplied-source results are blocked from approval in this release.

Changing the UI inputs marks displayed results stale. Recalculation rebuilds the payload; export gets a fresh package ID and revision. Saved snapshots and issued export folders are not overwritten. CLI destination names must be new. Source hashes identify current local bytes; external source changes require a new calculation and export. Multi-user locking/approval workflows are not implemented.

End-to-end Project 1 → 2 → 3 validation remains pending. Independent module tests do not establish that chain or professional acceptance. Once all modules exist, test matching packages with networking disabled and compare a nominated real project against an independent acoustic assessment.
