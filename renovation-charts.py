#!/usr/bin/env python3
"""
Render the charts comparing heat pump performance before and after the 2025
renovation.

Building work ran from 10 February to 15 July 2025, during which the system was
drained and the gateway stopped logging. The comparison window is therefore 16
July to 31 December in each year: the longest span that is fully logged in both
2024 and 2025 and lies entirely after recommissioning.
"""

__author__ = "James Hanlon"
__license__ = "UNLICENSE"

import argparse
import datetime
import statistics
from collections import defaultdict
from pathlib import Path

import vaillant

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

YEARS = (2024, 2026)

# Building work started on 10 February 2025 and the system was recommissioned
# on 15 July.
RENOVATION_YEAR = 2025
RENOVATION_START = datetime.date(RENOVATION_YEAR, 2, 10)
RECOMMISSIONED = datetime.date(RENOVATION_YEAR, 7, 15)

# Comparison window, as (month, day), inclusive: the heating season, which is
# where the difference between the two years actually shows up. 2024 is the
# last full season before the renovation and 2026 the first full one after it.
WINDOW_FROM = (1, 1)
WINDOW_TO = (4, 30)

# Days using less than this much electricity for heating say more about
# cycling and standby losses than about heating efficiency, and the kWh
# quantisation in the export makes their COP very noisy. Applied only to the
# COP charts; the energy totals include every logged day.
MIN_DAILY_HEATING_WH = 3000.0

# Trend lines average COP over bins this wide, in degrees C, and a bin needs at
# least this many days before it is plotted.
BIN_WIDTH_C = 2.0
MIN_BIN_SAMPLES = 3

# Degree-day base temperature.
HDD_BASE = 15.5

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#dedddd"

# A two-colour categorical palette, validated for colour-vision deficiency
# against the light surface above.
PALETTE = ("#2a78d6", "#eb6834")
SERIES = dict(zip(YEARS, PALETTE))
ROOM_COLOUR, TANK_COLOUR = PALETTE


# Output labels for the domains the heat pump reports separately.
DOMAIN_LABELS = (("heating", vaillant.HEATING), ("water", vaillant.WATER))


def window_label() -> str:
    """
    Describe the comparison window, for use in chart titles.
    """

    def render(month_day):
        date = datetime.date(2001, *month_day)
        return f"{date.day} {date:%b}"

    return f"{render(WINDOW_FROM)} – {render(WINDOW_TO)}"


def read_energy(data_dir: Path, year: int) -> dict[datetime.date, dict[str, float]]:
    """
    Read daily energy totals for a year, keyed by date.
    """
    return {
        timestamp.date(): {
            column: values.get(column, 0.0) for column in vaillant.ENERGY_COLUMNS
        }
        for timestamp, values in vaillant.read_records(
            vaillant.energy_csv(data_dir, year)
        )
    }


def read_daily_mean(
    data_dir: Path, year: int, filename: str, column: str
) -> dict[datetime.date, float]:
    """
    Read an hourly sensor column and average it per day.
    """
    path = vaillant.sensor_csv(data_dir, year, filename)
    return vaillant.daily_means(vaillant.read_column(path, column))


def in_window(date: datetime.date) -> bool:
    """
    Is this date inside the comparison window?

    The window does not wrap past the end of the year, so comparing
    (month, day) tuples is enough.
    """
    return WINDOW_FROM <= (date.month, date.day) <= WINDOW_TO


def window_days(energy: dict) -> list[tuple[datetime.date, dict]]:
    """
    The logged days of one year that fall inside the comparison window.
    """
    return [(date, v) for date, v in energy.items() if in_window(date)]


def configure_style():
    """
    Set the chart styling shared by every figure.
    """
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "figure.figsize": (7.0, 4.2),
            "savefig.dpi": 160,
            "savefig.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "axes.edgecolor": GRID,
            "axes.grid": True,
            "axes.axisbelow": True,
            "axes.labelcolor": TEXT_SECONDARY,
            "axes.labelsize": 9,
            "axes.titlecolor": TEXT_PRIMARY,
            "axes.titlesize": 11,
            "axes.titlelocation": "left",
            "axes.titlepad": 12,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "lines.linewidth": 2.0,
            "xtick.color": TEXT_SECONDARY,
            "ytick.color": TEXT_SECONDARY,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "legend.labelcolor": TEXT_SECONDARY,
            "font.size": 9,
            "text.color": TEXT_SECONDARY,
        }
    )


def finish(figure, axes, path: Path, title: str, xlabel: str, ylabel: str):
    """
    Label, lay out and write a figure.
    """
    axes.set_title(title)
    axes.set_xlabel(xlabel)
    axes.set_ylabel(ylabel)
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path)
    plt.close(figure)
    print(f"Wrote {path}")


def binned_means(points):
    """
    Average y over fixed-width bins of x, returning bin centres and means.
    """
    bins = defaultdict(list)
    for x, y in points:
        bins[round(x / BIN_WIDTH_C) * BIN_WIDTH_C].append(y)
    centres = sorted(b for b, v in bins.items() if len(v) >= MIN_BIN_SAMPLES)
    return centres, [statistics.mean(bins[c]) for c in centres]


def scatter_with_trend(
    points_by_year, path: Path, title: str, xlabel: str, ylabel: str
):
    """
    Plot daily points per year, overlaid with a binned trend line.
    """
    figure, axes = plt.subplots()
    for year, points in points_by_year.items():
        axes.scatter(*zip(*points), s=16, color=SERIES[year], alpha=0.3, linewidths=0)
        centres, means = binned_means(points)
        axes.plot(
            centres,
            means,
            color=SERIES[year],
            marker="o",
            markersize=5,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
            label=str(year),
        )
    axes.legend()
    finish(figure, axes, path, title, xlabel, ylabel)


def heating_cop_points(energy, outdoor):
    """
    Daily (outdoor temperature, heating COP) pairs within the window.
    """
    points = []
    for date, values in window_days(energy):
        consumed = values[vaillant.energy_column(vaillant.CONSUMED, vaillant.HEATING)]
        if consumed < MIN_DAILY_HEATING_WH or date not in outdoor:
            continue
        generated = values[vaillant.energy_column(vaillant.GENERATED, vaillant.HEATING)]
        points.append((outdoor[date], vaillant.reading_cop(generated, consumed)))
    return points


def heat_demand_points(energy, outdoor):
    """
    Daily (outdoor temperature, heat generated in kWh) pairs within the window.
    """
    generated = vaillant.energy_column(vaillant.GENERATED, vaillant.HEATING)
    return [
        (outdoor[date], values[generated] / 1000.0)
        for date, values in window_days(energy)
        if date in outdoor
    ]


def monthly_scop(energy, suffix):
    """
    SCOP per calendar month within the window, for one domain.
    """
    consumed = defaultdict(float)
    generated = defaultdict(float)
    consumed_column = vaillant.energy_column(vaillant.CONSUMED, suffix)
    generated_column = vaillant.energy_column(vaillant.GENERATED, suffix)
    for date, values in window_days(energy):
        consumed[date.month] += values[consumed_column]
        generated[date.month] += values[generated_column]
    return {m: vaillant.cop(generated[m], consumed[m]) for m in consumed if consumed[m]}


def grouped_bars(energy, path: Path, months, suffix: str, title: str, ylabel: str):
    """
    Draw monthly SCOP for both years as paired bars.
    """
    figure, axes = plt.subplots()
    # Leave a visible gap between the paired bars and between months.
    width = 0.32
    gap = 0.02
    peak = 0.0
    for offset, year in zip((-1, 1), YEARS):
        values = monthly_scop(energy[year], suffix)
        pairs = [(i, values[m]) for i, m in enumerate(months) if m in values]
        positions = [i + offset * (width / 2 + gap) for i, _ in pairs]
        heights = [h for _, h in pairs]
        peak = max([peak] + heights)
        bars = axes.bar(
            positions, heights, width=width, color=SERIES[year], label=str(year)
        )
        axes.bar_label(bars, fmt="%.2f", padding=3, fontsize=8)
    axes.set_xticks(range(len(months)))
    axes.set_xticklabels([datetime.date(2001, m, 1).strftime("%b") for m in months])
    axes.set_ylim(0, peak * 1.2)
    axes.grid(axis="x", visible=False)
    axes.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncols=2)
    finish(figure, axes, path, title, "", ylabel)


def chart_shutdown(room, tank, path: Path):
    """
    Room and tank temperature through the renovation shutdown and logging gap.
    """
    figure, axes = plt.subplots()
    end = RECOMMISSIONED + datetime.timedelta(days=17)
    for label, series, color in (
        ("Room temperature", room, ROOM_COLOUR),
        ("Hot water tank", tank, TANK_COLOUR),
    ):
        dates = sorted(d for d in series if d < end)
        # Break the line across the logging gap rather than interpolating it.
        xs, ys = [], []
        previous = None
        for date in dates:
            if previous and (date - previous).days > 1:
                xs.append(None)
                ys.append(None)
            xs.append(date)
            ys.append(series[date])
            previous = date
        axes.plot(xs, ys, color=color, label=label)
    axes.axvspan(
        RENOVATION_START, RECOMMISSIONED, color=GRID, alpha=0.5, linewidth=0, zorder=0
    )
    midpoint = RENOVATION_START + (RECOMMISSIONED - RENOVATION_START) / 2
    lower, upper = axes.get_ylim()
    axes.annotate(
        "Building work:\nsystem drained,\nlogging stopped",
        xy=(midpoint, lower + 0.55 * (upper - lower)),
        ha="center",
    )
    # Below the axes, clear of the traces whatever range the data covers.
    axes.legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), ncols=2)
    figure.autofmt_xdate(rotation=45)
    finish(
        figure,
        axes,
        path,
        f"Room and hot water temperature through the {RENOVATION_YEAR} renovation",
        "",
        "Temperature (°C)",
    )


def print_summary(energy, outdoor, room):
    """
    Print the figures quoted in the write-up.
    """
    rows = []
    for year in YEARS:
        days = window_days(energy[year])
        row = {"year": year, "days": len(days)}
        consumed_total = generated_total = 0.0
        for label, suffix in DOMAIN_LABELS:
            consumed = sum(
                v[vaillant.energy_column(vaillant.CONSUMED, suffix)] for _, v in days
            )
            generated = sum(
                v[vaillant.energy_column(vaillant.GENERATED, suffix)] for _, v in days
            )
            row[f"{label} consumed (kWh)"] = consumed / 1000.0
            row[f"{label} generated (kWh)"] = generated / 1000.0
            row[f"{label} SCOP"] = vaillant.cop(generated, consumed)
            consumed_total += consumed
            generated_total += generated
        row["SCOP"] = vaillant.cop(generated_total, consumed_total)
        temps = [outdoor[year][d] for d, _ in days if d in outdoor[year]]
        hdd = sum(max(0.0, HDD_BASE - t) for t in temps)
        row["mean outdoor (C)"] = statistics.mean(temps)
        row["mean room (C)"] = statistics.mean(
            [room[year][d] for d, _ in days if d in room[year]]
        )
        row["degree days"] = hdd
        heating_generated = vaillant.energy_column(vaillant.GENERATED, vaillant.HEATING)
        row["heat per degree day (kWh)"] = (
            sum(v[heating_generated] for _, v in days) / 1000.0 / hdd
        )
        rows.append(row)
    print()
    for key in rows[0]:
        values = "  ".join(
            f"{r[key]:>10.2f}" if isinstance(r[key], float) else f"{r[key]:>10}"
            for r in rows
        )
        print(f"{key:>28}  {values}")
    print()


def main(args):
    data_dir = Path(args.data_dir)
    out_dir = Path(args.output_dir)
    configure_style()

    energy = {y: read_energy(data_dir, y) for y in YEARS}
    outdoor = {
        y: read_daily_mean(data_dir, y, vaillant.SYSTEM_CSV, "OutdoorTemperature")
        for y in YEARS
    }
    room = {
        y: read_daily_mean(data_dir, y, vaillant.ZONE_CSV, "CurrentRoomTemperature")
        for y in YEARS
    }
    # The shutdown chart covers the renovation year, which is not one of the
    # two years being compared.
    tank = read_daily_mean(
        data_dir, RENOVATION_YEAR, vaillant.DHW_CSV, "DhwTankTemperature"
    )
    shutdown_room = read_daily_mean(
        data_dir, RENOVATION_YEAR, vaillant.ZONE_CSV, "CurrentRoomTemperature"
    )

    print_summary(energy, outdoor, room)

    window = window_label()
    scatter_with_trend(
        {y: heating_cop_points(energy[y], outdoor[y]) for y in YEARS},
        out_dir / "cop-vs-outdoor-temperature.png",
        f"Daily heating COP against outdoor temperature ({window})",
        "Mean daily outdoor temperature (°C)",
        "Heating COP",
    )
    scatter_with_trend(
        {y: heat_demand_points(energy[y], outdoor[y]) for y in YEARS},
        out_dir / "heat-demand-vs-outdoor-temperature.png",
        f"Daily heat generated against outdoor temperature ({window})",
        "Mean daily outdoor temperature (°C)",
        "Heat generated for heating (kWh)",
    )
    grouped_bars(
        energy,
        out_dir / "monthly-heating-scop.png",
        months=[1, 2, 3, 4],
        suffix="Heating",
        title="Monthly heating SCOP",
        ylabel="Heating SCOP",
    )
    grouped_bars(
        energy,
        out_dir / "monthly-water-scop.png",
        months=[1, 2, 3, 4],
        suffix="DomesticHotWater",
        title="Monthly hot water SCOP",
        ylabel="Hot water SCOP",
    )
    chart_shutdown(shutdown_room, tank, out_dir / "shutdown.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data", help="Directory of CSV exports")
    parser.add_argument("--output-dir", default="charts", help="Where to write PNGs")
    main(parser.parse_args())
