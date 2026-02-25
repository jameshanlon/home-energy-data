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

Code is formatted with `black` (enforced via pre-commit).

## Architecture

**Python layer** (`analyse-energy-data.py`): reads CSVs, computes stats and COP, writes `output/data.json`.

**Frontend** (`frontend/`): Vite+React app that fetches `data.json` and renders stats tables and charts using `@mui/x-charts`. Built output lands in `output/`.

**Data flow:**
1. `read_csv()` reads the semicolon-delimited CSVs into a `Dataset` (a `defaultdict` keyed by `datetime`).
2. Each row populates a `Record` object via `setattr`, using the column header as the attribute name (colons replaced with underscores).
3. The 2023 energy CSV has 6 repeated column blocks — handled by multiplying the headers list by `column_repeats = 6`.
4. After loading, consumed and generated Wh values are optionally scaled via `--scale-consumed` / `--scale-generated`.
5. `main()` builds `LineChart` and `ScatterChart` objects from the dataset, then passes them to `generate_json()`.
6. `generate_json()` serialises the charts and stats to `output/data.json`.
7. The React app (`frontend/src/App.jsx`) fetches `data.json` on mount and renders the dashboard.

**Key Python classes:**
- `Record` — one data point per datetime; fields map directly to CSV column names with `:` → `_`.
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

**Adding a new year:** Add the year to `YEARS` (line 27) and place the four CSV files in `data/<year>/` following the existing naming convention.

**Data files** (`data/<year>/`):
- `energy_data_<year>_ArothermPlus_*.csv` — consumed/generated electrical and heat energy (Wh)
- `domestic_hot_water_255_data_<year>.csv` — DHW tank temperature
- `system_data_<year>.csv` — outdoor temperature
- `zone_0_data_<year>.csv` — room temperature setpoints and current room temperature
