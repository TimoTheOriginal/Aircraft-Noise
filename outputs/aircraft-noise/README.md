# AircraftNoise 0.3 — keyboard terminal

A local browser application styled after TestDisk / PhotoRec: black background, monospace text, inverse selection and keyboard commands. No buttons or mouse actions.

## Start

Run `Start-AircraftNoise.ps1` in PowerShell, then open http://127.0.0.1:8793. Keep the service running; Ctrl+C stops it. The launcher installs included offline wheels in a local environment. Python 3.12 x64 is required; use `-Python 'C:\path\to\python.exe'` if discovery fails. Python itself is not bundled.

## Keyboard guide

| Key | Action |
|---|---|
| G | Site/contour map; arrows pan, +/− zoom, 0 fit contours, 1 site view |
| C | Enter one WGS84 latitude, longitude pair; Enter calculates |
| A / F5 | Recalculate |
| K | Confirm location after checking |
| N | Cases; Tab switches ranked/unresolved; Enter opens evidence |
| R | Runways and contour distances / inside-outside |
| F | Raw ANEF 2045 frequencies |
| M | Mappings; Enter starts a mapping command |
| V | Elevation and settings |
| S | Source audit |
| W / F2 | Save locally |
| L | Load with Y/N confirmation |
| X | Export ZIP with Y/N confirmation |
| Q | Quit with Y/N confirmation |
| F1 | Help |
| : | Command prompt |
| Up/Down, PgUp/PgDn | Browse |
| Esc | Back / cancel |

Coordinate format: `-33.95931060086562, 151.06228141530434`. Startup uses this editable, unconfirmed starting coordinate. The user can enter any valid coordinate; outside the Sydney calculation domain, exposure is unknown.

Commands: `project ID`, `tolerance METRES`, `elev SITE_M AIRPORT_M DATUM`, `terrain CODE domestic_jet`, `terrain CODE international`, `terrain CODE propeller_light`, `uncorrected`, `map CODE TABLE_BASE acoustic justification`, `resetmap CODE`, `save`, `export`, `coordinates`, `help`.

## Calculation

The default route uses the 2045 worksheet **Aircraft Type Frequency ANEF -2** in AS2021-2015 Aircraft Noise 1.01.xlsm. Noise values come from aircraft_noise_extraction2.xlsx, **Aircraft Matrices**. All 113 tables retain cell addresses. VBA and formulas are never executed.

Straight runway geometry calculates DS, DL and DT. Arrivals use DL/DS; departures use DT/DS. All relevant directions are considered. Nearest runway uses the finite centreline segment; DS uses the extended centreline. Beside-runway and unsupported flight-track cases remain unresolved.

Between entries, the terminal performs two-axis linear (bilinear) interpolation using the one, two or four contributing cells. Each trace records the cell values and weights. Exact axes collapse to the matching row or column. No extrapolation is performed; a contributing blank or asterisk cell blocks the lookup.

This aircraft-table interpolation is an **engineering implementation choice**. AS 2021:2015 Clause 3.1.4 says to read off the appropriate value from Tables 3.4–3.58 and select the highest case, but it does not prescribe an interpolation method for those tables. The Standard expressly permits interpolation for the separate Table 3.2 land-height correction.

Top three means highest assessed operation/load cases, following the workbook LARGE(...,1/2/3) approach. Ties remain and one aircraft can occupy multiple ranks. Frequency establishes relevance, not acoustic weighting. Fractional movements are retained; dashes remain unresolved. The worksheet does not define units/time periods, so no significance-rate threshold is invented.

Contour results include band, nearest line, distance, inside/outside/on relation and nearest point. Geometry uses EPSG:32756. Chart-derived coordinates and the configurable default 30 m boundary tolerance do not establish survey accuracy.

## Preliminary limitations

Six types remain unmapped: 7879, A350-941, A330-343, 7378MAX, A320-271N, BD-700-1A10. They may change the ranking. Manual mappings require acoustic justification; existing representative mappings also require review.

Default results are **uncorrected screening** because elevations were not supplied. `elev` enables terrain correction with site/airport elevations on one datum; required departure categories must be entered. Raw distances remain preserved. Missing elevations are not treated as equal height.

Workbook comparison: 115,107 cells, 114,122 agreements, 985 differences. Extraction2 takes precedence as requested; affected cells carry discrepancy evidence. Five missing B identifiers were recovered from aircraft blocks, departure headers and Table Index, without changing numeric values. Original Standard page verification, flight tracks, mappings and independent georeferencing remain outstanding. This release does not issue production acoustic approval.

Room calculations and report issue are outside Project 1.

## Example and verification

At the editable example coordinate: nearest contour ANEF20, **474.03 m outside**; nearest runway16R/34L. Uncorrected interpolated leading cases are 747400 / 34L departure / short haul **62.16 dB(A)**, 7673ER / 34L departure **62.08 dB(A)**, and 747400 / 34L departure / long haul **61.08 dB(A)**. None of the contributing cells has a workbook discrepancy. Unresolved candidates and terrain inputs may change these results.

Run from this folder with dependencies installed:

```text
python -m aircraft_noise serve --port 8793
python -m aircraft_noise run --input fixtures/terminal-request.json --output new-aircraft-basis
python -m aircraft_noise validate-package new-aircraft-basis
python -m unittest discover -s tests -v
```

Exports never overwrite existing directories. Sessions and UI exports are in `.local/`, excluded from release ZIP. Source-linked reference data is bundled for local use; original licensed Standard text is not included. `tools/import_sources.py --source-dir PATH` rebuilds reference data using openpyxl (required only for re-import, not running the app).

## Colour and site map update

Cyan identifies coordinate input and headings; green identifies calculated values; blue identifies geometry and source evidence; amber identifies settings and warnings; violet identifies saved/exported material; red identifies quit actions and errors. Secondary information remains white. Text labels preserve meaning without colour. Contours progress from cool cyan at ANEF20 through green and amber to red at ANEF35. `[ G ]` opens the offline portrait map with labelled contours, runways, a white site cross and nearest-contour connector.

The supplied `Airport Map Portrait.tiff` is a 11,692 × 8,267 WGS84 GeoTIFF and is accompanied by `Airport Map Portrait.tfw`. Version 0.3 reads the TFW pixel-centre transform and uses calculated pixel-edge bounds of 150.9750302122625°E to 151.3756103971705°E and 33.802821828105°S to 34.086060342419°S. A 3,600 × 2,545 WebP derivative makes the same full geographic extent browser-readable. The visual overlay and WGS84 vectors therefore share the supplied coordinate system. Numerical distances continue to use EPSG:32756.
