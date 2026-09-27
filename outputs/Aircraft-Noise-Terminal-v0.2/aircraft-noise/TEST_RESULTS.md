# Release 0.2 verification — 26 September 2026

45 tests passed (see test-output.txt). Includes original 31 regression tests and 14 forecast tests covering coordinate validation, all 113 table axes, recovered table identifiers, surrounding maximum, missing cells, no extrapolation, source-linked top three, ties, mappings, terrain correction, contour inside/outside/on, export contract and button-free single-input interface.

JavaScript syntax check passed. Offline dependencies installed from bundled Windows x64 Python 3.12 wheels. CLI example package generated and validated: fixtures/example-aircraft-basis, review status requires_confirmation.

Browser verified with keyboard only: coordinate entry, remote coordinate 0,0 returning unknown/no levels, restoration of example, ranked case cell evidence, invalid-coordinate error, session save/restore with confirmation and successful package export. The finished screenshot is supplied beside the release ZIP.

This verifies implementation behavior; it is not independent acoustic validation or source-page verification. Unresolved aircraft mappings, terrain inputs and chart accuracy remain explicitly preliminary.
