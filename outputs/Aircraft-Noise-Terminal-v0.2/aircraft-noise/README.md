# AircraftNoise 0.2 — keyboard terminal

A local browser application styled after TestDisk / PhotoRec: black background, monospace text, inverse selection and keyboard commands. No buttons or mouse actions.

## Start

Run `Start-AircraftNoise.ps1` in PowerShell, then open http://127.0.0.1:8793. Keep the service running; Ctrl+C stops it. The launcher installs included offline wheels in a local environment. Python 3.12 x64 is required; use `-Python 'C:\path\to\python.exe'` if discovery fails. Python itself is not bundled.

## Keyboard guide

| Key | Action |
|---|---|
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

Coordinate format: `-33.89754544671029, 151.13696110226067`. Startup uses this editable, unconfirmed example. Any valid coordinate is accepted; outside the Sydney calculation domain, exposure is unknown.

Commands: `project ID`, `tolerance METRES`, `elev SITE_M AIRPORT_M DATUM`, `terrain CODE domestic_jet`, `terrain CODE international`, `terrain CODE propeller_light`, `uncorrected`, `map CODE TABLE_BASE acoustic justification`, `resetmap CODE`, `save`, `export`, `coordinates`, `help`.

## Calculation

The default route uses the 2045 worksheet **Aircraft Type Frequency ANEF -2** in AS2021-2015 Aircraft Noise 1.01.xlsm. Noise values come from aircraft_noise_extraction2.xlsx, **Aircraft Matrices**. All 113 tables retain cell addresses. VBA and formulas are never executed.

Straight runway geometry calculates DS, DL and DT. Arrivals use DL/DS; departures use DT/DS. All relevant directions are considered. Nearest runway uses the finite centreline segment; DS uses the extended centreline. Beside-runway and unsupported flight-track cases remain unresolved.

Between entries, select the **highest surrounding cell**, as explicitly selected by the user on 26 September 2026. This is a **preliminary engineering policy**, not asserted permission for aircraft-table interpolation under AS2021. Exact axes use matching rows/columns only. No extrapolation; missing or asterisk corners block lookup. Each case records raw/used distances, selected source cells, frequency entries and issues.

Top three means highest assessed operation/load cases, following the workbook LARGE(...,1/2/3) approach. Ties remain and one aircraft can occupy multiple ranks. Frequency establishes relevance, not acoustic weighting. Fractional movements are retained; dashes remain unresolved. The worksheet does not define units/time periods, so no significance-rate threshold is invented.

Contour results include band, nearest line, distance, inside/outside/on relation and nearest point. Geometry uses EPSG:32756. Chart-derived coordinates and the configurable default 30 m boundary tolerance do not establish survey accuracy.

## Preliminary limitations

Six types remain unmapped: 7879, A350-941, A330-343, 7378MAX, A320-271N, BD-700-1A10. They may change the ranking. Manual mappings require acoustic justification; existing representative mappings also require review.

Default results are **uncorrected screening** because elevations were not supplied. `elev` enables terrain correction with site/airport elevations on one datum; required departure categories must be entered. Raw distances remain preserved. Missing elevations are not treated as equal height.

Workbook comparison: 115,107 cells, 114,122 agreements, 985 differences. Extraction2 takes precedence as requested; affected cells carry discrepancy evidence. Five missing B identifiers were recovered from aircraft blocks, departure headers and Table Index, without changing numeric values. Original Standard page verification, flight tracks, mappings and independent georeferencing remain outstanding. This release does not issue production acoustic approval.

Legacy synthetic fixtures and their separately approved bilinear route remain for regression only; the terminal exclusively uses surrounding maximum. Room calculations and report issue are outside Project 1.

## Example and verification

At the editable example coordinate: nearest contour ANEF20, **474.03 m outside**; nearest runway16R/34L. Uncorrected highest assessed cases: 747400 / 34L departure / short haul **64 dB(A)**; 7673ER / 34L departure **63 dB(A)**; 747400 / 34L departure / long haul **62 dB(A)**. None of the selected cells has a workbook discrepancy. Unresolved candidates and terrain inputs may change these results.

Run from this folder with dependencies installed:

```text
python -m aircraft_noise serve --port 8793
python -m aircraft_noise run --input fixtures/terminal-request.json --output new-aircraft-basis
python -m aircraft_noise validate-package new-aircraft-basis
python -m unittest discover -s tests -v
```

Exports never overwrite existing directories. Sessions and UI exports are in `.local/`, excluded from release ZIP. Source-linked reference data is bundled for local use; original licensed Standard text is not included. `tools/import_sources.py --source-dir PATH` rebuilds reference data using openpyxl (required only for re-import, not running the app).
