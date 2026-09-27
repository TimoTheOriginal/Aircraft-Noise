# Release 0.3 verification — 26 September 2026

46 tests passed (see test-output.txt). The suite covers coordinate validation, all 113 table axes, recovered table identifiers, two-axis linear interpolation and weights, missing cells, no extrapolation, source-linked top three, ties, mappings, terrain correction, contour inside/outside/on, portrait-map world-file bounds, export contract and button-free single-input interface.

JavaScript syntax check passed. Offline dependencies installed from bundled Windows x64 Python 3.12 wheels. CLI example package generated and validated: fixtures/example-aircraft-basis, review status requires_confirmation.

Browser verified with keyboard only: coordinate entry, remote coordinate 0,0 returning unknown/no levels, restoration of example, ranked case cell evidence, invalid-coordinate error, session save/restore with confirmation and successful package export. The finished screenshot is supplied beside the release ZIP.

This verifies implementation behavior; it is not independent acoustic validation or source-page verification. Unresolved aircraft mappings, terrain inputs and chart accuracy remain explicitly preliminary.

Colour/map update: all regressions pass. Browser verified G map navigation, site zoom, keyboard pan/zoom and labelled nearest-line connector; JavaScript syntax checks passed. Map uses supplied geometry locally.

Version 0.3: all 46 tests pass after replacing the forecast surrounding-maximum route with two-axis linear interpolation. Tests verify exact-axis collapse, four weights summing to one, no extrapolation, missing-cell blocking, revised top-three values and package validation. Browser checks verified the continuous single-column menu, semantic colour groups, keyboard access to Site map, portrait-map background, and per-cell interpolation weights. The map overlay uses the supplied `Airport Map Portrait.tfw` transform and its 11,692 × 8,267 source grid.
