# Home Energy Data

Analysis and visualisation of home energy data from a Vaillant aroTHERM Plus heat pump.

A Python script reads CSV exports from the Vaillant system, computes statistics and
Coefficient of Performance (COP/SCOP), and writes `output/data.json`. A React frontend
reads that file and renders an interactive dashboard.

## Requirements

- Python 3.10+
- Node.js 20 (via [nvm](https://github.com/nvm-sh/nvm))

## Setup

```bash
make install
```

This creates a Python virtualenv, installs Python and npm dependencies, and sets up
pre-commit hooks (Black formatter).

## Usage

```bash
# Run analysis + build frontend in one step
make all

# Serve the dashboard locally at http://localhost:8001
make serve

# Run just the Python analysis (writes output/data.json)
make run

# Build just the React frontend (writes output/)
make build

# Run tests
make test
```

### Analysis options

```bash
./analyse-energy-data.py --from 2024-01-01 --to 2024-12-31   # filter date range
./analyse-energy-data.py --scale-consumed 1.1                 # scale consumed Wh readings
./analyse-energy-data.py --scale-generated 0.95               # scale generated Wh readings
./analyse-energy-data.py --dump                                # print raw data as a table
```

## Data files

CSV files exported from the Vaillant app live in `data/<year>/`:

| File | Contents |
|------|----------|
| `energy_data_<year>_ArothermPlus_*.csv` | Daily electrical energy consumed and heat energy generated (Wh) |
| `domestic_hot_water_255_data_<year>.csv` | Hourly DHW tank temperature |
| `system_data_<year>.csv` | Hourly outdoor temperature |
| `zone_0_data_<year>.csv` | Hourly room temperature and setpoints |

## Dashboard

The dashboard shows a stats table (annual and total SCOP, energy consumed/generated)
and the following charts:

**Weekly data per year** — one series per year, x-axis is week number (1–52):
- Weekly total energy consumed (Wh)
- Weekly total heat energy generated (Wh)
- Weekly averaged COP
- Weekly averaged DHW temperature
- Weekly averaged internal and external temperature
- Heat output vs COP scatter (weekly averages)
- Daily electrical energy consumed vs heat energy generated scatter

**All time** — x-axis is date:
- Energy consumed
- Heat energy generated
- Daily COP
- DHW tank temperature (daily average)
- Ambient temperature — internal and external (daily average)

## Adding a new year

1. Add the year to `YEARS` in `analyse-energy-data.py` (line 27).
2. Place the four CSV files in `data/<year>/` following the existing naming convention.
3. Run `make all`.

## Tests

```bash
make test
```

Unit tests cover the Python data-processing logic (`format_kwh`, `Dataset`, `LineChart`,
`ScatterChart`, `generate_json`, `read_csv`). Integration tests load the real data files
and verify record counts, sort order, value ranges, SCOP plausibility, and the full
end-to-end pipeline. Integration tests are skipped automatically if `data/` is absent.

Tests also run on every push and pull request via GitHub Actions.

## Licence

[The Unlicense](LICENSE) — public domain.
