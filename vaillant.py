"""
Shared reading and efficiency definitions for Vaillant CSV exports.

This module is the single source of truth for the export layout: the CSV
dialect, the column and file names, the plausible range of each sensor, and
the COP definition.
"""

import csv
import datetime
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Iterator

# The metrics and domains the heat pump reports, which together name the
# columns of the energy export.
CONSUMED = "ConsumedElectricalEnergy"
GENERATED = "HeatGenerated"
EARNED = "EarnedEnvironmentEnergy"
ENERGY_METRICS = (CONSUMED, GENERATED, EARNED)

HEATING = "Heating"
WATER = "DomesticHotWater"
ENERGY_DOMAINS = (HEATING, WATER)

# The temperature columns, spread across the hot water, system and zone files.
SENSOR_COLUMNS = [
    "DhwTankTemperature",
    "OutdoorTemperature",
    "ManualModeSetpointHeating",
    "RoomTemperatureSetpoint",
    "CurrentRoomTemperature",
]

# Filename patterns within data/<year>/. The energy export carries the unit's
# serial number, so it has to be matched rather than named.
ENERGY_GLOB = "energy_data_{year}_ArothermPlus_*.csv"
DHW_CSV = "domestic_hot_water_255_data_{year}.csv"
SYSTEM_CSV = "system_data_{year}.csv"
ZONE_CSV = "zone_0_data_{year}.csv"
SENSOR_CSVS = (DHW_CSV, SYSTEM_CSV, ZONE_CSV)

# Vaillant occasionally logs absurd COP values. Clipping rather than dropping
# the day keeps its heat output in the energy totals.
MAX_COP = 6.0

# Plausible ranges per sensor, used to drop logging glitches. The outdoor
# sensor logs occasional -40 C spikes; the tank runs far hotter than the air.
AIR_RANGE = (-30.0, 50.0)
TANK_RANGE = (0.0, 90.0)

SENSOR_RANGES = {
    "DhwTankTemperature": TANK_RANGE,
    "OutdoorTemperature": AIR_RANGE,
    "ManualModeSetpointHeating": AIR_RANGE,
    "RoomTemperatureSetpoint": AIR_RANGE,
    "CurrentRoomTemperature": AIR_RANGE,
}


def energy_column(metric: str, domain: str) -> str:
    """
    Name the energy column reporting one metric for one domain.
    """
    return f"{metric}:{domain}"


def attr_name(column: str) -> str:
    """
    Convert a CSV column name into a Python attribute name.
    """
    return column.replace(":", "_")


ENERGY_COLUMNS = [
    energy_column(metric, domain)
    for metric in ENERGY_METRICS
    for domain in ENERGY_DOMAINS
]

# The attributes of one data point, in the order they are reported.
RECORD_ATTRS = (
    ["DateTime"] + [attr_name(column) for column in ENERGY_COLUMNS] + SENSOR_COLUMNS
)


def energy_csv(data_dir: Path, year: int) -> Path:
    """
    Locate a year's energy export, whose name includes the unit's serial.
    """
    pattern = ENERGY_GLOB.format(year=year)
    matches = sorted(Path(data_dir, str(year)).glob(pattern))
    if len(matches) != 1:
        raise ValueError(
            f"expected one {pattern} in {data_dir}/{year}, found {len(matches)}"
        )
    return matches[0]


def sensor_csv(data_dir: Path, year: int, pattern: str) -> Path:
    """
    Resolve one of the per-year sensor export filenames.
    """
    return Path(data_dir, str(year), pattern.format(year=year))


def cop(generated: float, consumed: float) -> float:
    """
    Coefficient of performance, zero when nothing was consumed.

    The raw ratio is returned, so it is also the seasonal (SCOP) definition
    when applied to totals. Use reading_cop() for a single reading.
    """
    return 0.0 if not consumed else generated / consumed


def reading_cop(generated: float, consumed: float) -> float:
    """
    Coefficient of performance of a single reading, clipped to MAX_COP.
    """
    return min(cop(generated, consumed), MAX_COP)


def parse_value(column: str, text: str) -> float | None:
    """
    Parse one CSV cell, returning None if it is blank or implausible.
    """
    if not text.strip():
        return None
    value = float(text)
    limits = SENSOR_RANGES.get(column)
    if limits is None:
        return value
    low, high = limits
    return value if low < value < high else None


def _rows(path: Path) -> Iterator[list[str]]:
    """
    Yield the rows of an export, header included, skipping blanks and comments.
    """
    with open(path, newline="") as f:
        for row in csv.reader(f, delimiter=";", quotechar='"'):
            if row and not row[0].startswith("#"):
                yield row


def read_records(path: Path) -> Iterator[tuple[datetime.datetime, dict[str, float]]]:
    """
    Yield the timestamp and populated values of each data row of an export.

    Columns are taken from the file's own header, so the repeated column
    blocks of the 2023 energy export need no special handling. Blank and
    implausible readings are left out.
    """
    columns = None
    for row in _rows(path):
        if row[0].startswith("DateTime"):
            columns = row
            continue
        if columns is None:
            raise ValueError(f"{path} has no header row")
        values = {}
        for column, text in zip(columns[1:], row[1:]):
            value = parse_value(column, text)
            if value is not None:
                values[column] = value
        yield datetime.datetime.fromisoformat(row[0]), values


def read_column(path: Path, column: str) -> Iterator[tuple[datetime.datetime, float]]:
    """
    Yield the timestamped readings of one named column of an export.

    Blank and implausible readings are dropped.
    """
    for timestamp, values in read_records(path):
        if column in values:
            yield timestamp, values[column]


def daily_means(
    samples: Iterable[tuple[datetime.datetime, float]],
) -> dict[datetime.date, float]:
    """
    Average timestamped readings over each calendar day.
    """
    by_day = defaultdict(list)
    for timestamp, value in samples:
        by_day[timestamp.date()].append(value)
    return {date: sum(values) / len(values) for date, values in by_day.items()}
