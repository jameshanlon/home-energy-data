# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Scripts to analyse and visualise home energy data collected from a Vaillant Arotherm Plus heat pump. The Python script reads CSVs exported from the Vaillant system, computes statistics and COP (Coefficient of Performance), and writes `output/data.json`. A Vite+React frontend (using MUI X Charts) reads that JSON and renders an interactive dashboard.

## Commands

```bash
# Set up virtualenv, install Python deps, install npm deps, and install pre-commit hooks
make install

# Run the Python analysis and generate output/data.json
make run

# Build the React frontend into output/
make build

# Run analysis + build in one step
make all

# Serve the output locally at http://localhost:8001
make serve

# Run directly with options
./analyse-energy-data.py --output-dir output
./analyse-energy-data.py --dump                        # print raw data as a table
./analyse-energy-data.py --from 2024-01-01 --to 2024-12-31
./analyse-energy-data.py --scale-consumed 1.1 --scale-generated 0.95

# Clean virtualenv, output, and node_modules
make clean
```

Code is formatted with `black` (enforced via pre-commit). The frontend build requires Node.js ≥ 14.18 (Node 20 via nvm is used on this machine); `make build` sources nvm automatically.

## Architecture

**Shared module** (`vaillant.py`): the single source of truth for the CSV export layout — dialect, column names, filename patterns, per-sensor plausible ranges, the COP definition and the hourly-to-daily averaging. Both Python scripts read the exports through it.

**Python layer** (`analyse-energy-data.py`): reads CSVs, computes stats and COP, writes `output/data.json`.

**Renovation charts** (`renovation-charts.py`): renders the before/after comparison PNGs for the 2025 renovation into `charts/`.

**Frontend** (`frontend/`): Vite+React app that fetches `data.json` and renders stats tables and charts using `@mui/x-charts`. Built output lands in `output/`.

**Data flow:**
1. `read_csv()` reads the semicolon-delimited CSVs into a `Dataset` (a `defaultdict` keyed by `datetime`) via `vaillant.read_records()`.
2. Each row populates a `Record` object via `setattr`, using the column header as the attribute name (colons replaced with underscores).
3. `vaillant.read_records()` takes each row's columns from the file's own header, so the 2023 energy CSV's 6 repeated column blocks need no special handling.
4. `vaillant.parse_value()` drops blank cells and readings outside the sensor's plausible range (the outdoor sensor logs occasional -40 C spikes).
5. After loading, consumed and generated Wh values are optionally scaled via `--scale-consumed` / `--scale-generated`.
6. `main()` builds `LineChart` and `ScatterChart` objects from the dataset, then passes them to `generate_json()`.
7. `generate_json()` serialises the charts and stats to `output/data.json`.
8. The React app (`frontend/src/App.jsx`) fetches `data.json` on mount and renders the dashboard.

**Data ordering note:** `iter_records()` sorts by `DateTime` before yielding. This is necessary because the `defaultdict` insertion order is not chronological — energy CSVs are read first (inserting their timestamps), so hourly timestamps from DHW/system/zone CSVs that don't overlap get appended later.

**Temperature chart aggregation:** DHW and ambient temperature CSVs contain hourly data (~18k points over the full date range). These are aggregated to daily averages via `vaillant.daily_means()` before serialisation to keep the charts readable.

**Erroneous COP readings:** the heat pump occasionally logs an absurd COP. Individual readings go through `vaillant.reading_cop()`, which clips to `vaillant.MAX_COP` rather than dropping the day, so its heat output still counts towards the energy totals. Aggregates (SCOP) use the unclipped `vaillant.cop()` ratio.

**Key Python classes:**
- `Record` — one data point per datetime; fields are derived from `vaillant.RECORD_ATTRS`, mapping CSV column names with `:` → `_`.
- `Dataset` — holds all records, provides `iter_records(date_from, date_to)`, `iter_year(year)`, and `total*` aggregation helpers.
- `LineChart` / `ScatterChart` — simple data containers; `get_symbol()` produces a JS-safe identifier from the chart name.
- `Stats` — populated per-year (and once for the full range) with totals and SCOP values; serialised to JSON.

**Frontend structure:**
```
frontend/
├── package.json
├── vite.config.js      # outDir set to ../output
├── index.html
└── src/
    ├── main.jsx
    └── App.jsx         # fetches data.json, renders StatsTable + ChartCard components
```

**Adding a new year:** Add the year to `YEARS` and place the four CSV files in `data/<year>/` following the filename patterns in `vaillant.py`. No column lists need editing — the readers follow each file's header. A column the exports have never carried before must still be added to `vaillant.py`, which `Dataset.add` will tell you about by name.

**Data files** (`data/<year>/`):
- `energy_data_<year>_ArothermPlus_*.csv` — consumed/generated electrical and heat energy (Wh)
- `domestic_hot_water_255_data_<year>.csv` — DHW tank temperature
- `system_data_<year>.csv` — outdoor temperature
- `zone_0_data_<year>.csv` — room temperature setpoints and current room temperature
