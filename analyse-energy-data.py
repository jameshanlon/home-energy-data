#!/usr/bin/env python3
"""
Analyse Vaillant energy data and produce some graphs.

Inspired partly by
  https://protonsforbreakfast.wordpress.com/2024/08/21/2024-summer-summary/
"""

__author__ = "James Hanlon"
__version__ = "0.0.1"
__license__ = "UNLICENSE"

import argparse
import csv
import datetime
import logging
from tabulate import tabulate
from rich import print
from dataclasses import dataclass
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from collections import defaultdict
from typing import Iterator, TypeAlias
from enum import Enum, auto


class Record:
    def __init__(self):
        self.DateTime: datetime.datetime = None
        self.ConsumedElectricalEnergy_Heating: float = None
        self.ConsumedElectricalEnergy_DomesticHotWater: float = None
        self.HeatGenerated_Heating: float = None
        self.HeatGenerated_DomesticHotWater: float = None
        self.EarnedEnvironmentEnergy_Heating: float = None
        self.EarnedEnvironmentEnergy_DomesticHotWater: float = None
        self.DhwTankTemperature: float = None
        self.OutdoorTemperature: float = None
        self.ManualModeSetpointHeating: float = None
        self.RoomTemperatureSetpoint: float = None
        self.CurrentRoomTemperature: float = None


class ChartType(Enum):
    LINE = auto()
    SCATTER = auto()


class LineChart:
    def __init__(self, name: str):
        self.name = name
        self.labels = []
        self.series = {}

    @staticmethod
    def is_type(chart_type: ChartType):
        return chart_type == ChartType.LINE

    def add_label(self, label: str):
        self.labels.append(label)

    def add_series(self, name: str):
        self.series[name] = []

    def add_datapoint(self, series_name: str, value: float):
        self.series[series_name].append(value)

    def get_symbol(self):
        return self.name.lower().replace(" ", "_").replace("(", "_").replace(")", "_")


class ScatterChart:
    def __init__(self, name: str):
        self.name = name
        self.series = {}

    @staticmethod
    def is_type(chart_type: ChartType):
        return chart_type == ChartType.SCATTER

    def add_series(self, name: str):
        self.series[name] = []

    def add_datapoint(self, series_name: str, value: tuple[float, float]):
        self.series[series_name].append(value)

    def get_symbol(self):
        return self.name.lower().replace(" ", "_").replace("(", "_").replace(")", "_")


Chart: TypeAlias = LineChart | ScatterChart


class Stats:
    def __init__(self, year: int):
        self.year = year


class Dataset:
    def __init__(self):
        self.records = defaultdict(Record)

    def add(self, date, metric, value):
        # Set the date.
        if self.records[date].DateTime == None:
            self.records[date].DateTime = date
        # Set the metric.
        attr_name = metric.replace(":", "_")
        assert getattr(self.records[date], attr_name) == None, "overwriting data point"
        setattr(self.records[date], attr_name, value)

    def iter_records(
        self, date_from: datetime.datetime, date_to: datetime.datetime
    ) -> Iterator[Record]:
        for record in self.records.values():
            if date_from != None and record.DateTime < date_from:
                continue
            if date_to != None and record.DateTime > date_to:
                continue
            yield record

    def iter_year(self, year: int) -> Iterator[Record]:
        for record in self.records.values():
            if record.DateTime.year == year:
                yield record

    def total(
        self,
        year: int,
        metric: str,
        date_from: datetime.datetime,
        date_to: datetime.datetime,
    ):
        return sum(
            getattr(record, metric) if getattr(record, metric) != None else 0
            for record in self.iter_records(date_from, date_to)
        )

    def total_year(self, year: int, metric: str):
        return sum(
            getattr(record, metric) if getattr(record, metric) != None else 0
            for record in self.iter_year(year)
        )

    def dump(self):
        metrics = [
            "DateTime",
            "ConsumedElectricalEnergy_Heating",
            "ConsumedElectricalEnergy_DomesticHotWater",
            "HeatGenerated_Heating",
            "HeatGenerated_DomesticHotWater",
            "EarnedEnvironmentEnergy_Heating",
            "EarnedEnvironmentEnergy_DomesticHotWater",
            "DhwTankTemperature",
            "OutdoorTemperature",
            "ManualModeSetpointHeating",
            "RoomTemperatureSetpoint",
            "CurrentRoomTemperature",
        ]
        table = [[getattr(r, x) for x in metrics] for r in self.records.values()]
        print(tabulate(table, metrics, tablefmt="simple_outline"))


def format_kwh(kwh: float) -> str:

    # Define the SI units and their corresponding power of 10 values
    units = [(1e9, "GWh"), (1e6, "MWh"), (1e3, "kWh"), (1, "Wh")]

    # Loop through the units and find the appropriate one
    for factor, unit in units:
        if kwh >= factor:
            value = kwh / factor
            return f"{value:.2f} {unit}"

    # If the kWh is too small, just return it in Wh
    return f"{kwh * 1000:.2f} Wh"


def read_csv(dataset, filename: str, headers: list[str]) -> Dataset:
    """
    Read a CSV file with the specified columns.
    """
    with open(filename, "r") as f:
        contents = csv.reader(f, delimiter=";", quotechar='"')
        count = 0
        for row in contents:
            if row[0].startswith("#") or row[0].startswith("DateTime"):
                continue
            # Date
            date = datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            # Values
            for i in range(1, len(headers)):
                if row[i] != "":
                    dataset.add(date, headers[i], float(row[i]))
            count += 1
        logging.info(f"Read {count} rows from {filename}")


def generate_html(
    charts: list[Chart],
    annual_stats: list[Stats],
    total_stats: Stats,
    output_path: Path,
):
    environment = Environment(loader=FileSystemLoader("templates/"))
    environment.filters["format_kwh"] = format_kwh
    template = environment.get_template("index.html")
    content = template.render(
        charts=charts,
        annual_stats=annual_stats,
        total_stats=total_stats,
        ChartType=ChartType,
    )

    output_file = output_path / "index.html"
    with open(output_file, mode="w", encoding="utf-8") as f:
        f.write(content)
        logging.info(f"Wrote {output_file}")


def main(args):
    dataset = Dataset()

    for year in [2023, 2024]:
        # Oddly the colums are repeated for different parts of the dataset.
        column_repeats = 6 if year == 2023 else 10
        read_csv(
            dataset,
            f"data/{year}/energy_data_{year}_ArothermPlus_21222500100211330001005519N3.csv",
            [
                "DateTime",
            ]
            + [
                "ConsumedElectricalEnergy:Heating",
                "ConsumedElectricalEnergy:DomesticHotWater",
                "HeatGenerated:Heating",
                "HeatGenerated:DomesticHotWater",
                "EarnedEnvironmentEnergy:Heating",
                "EarnedEnvironmentEnergy:DomesticHotWater",
            ]
            * column_repeats,
        )
        read_csv(
            dataset,
            f"data/{year}/domestic_hot_water_255_data_{year}.csv",
            [
                "DateTime",
                "DhwTankTemperature",
            ],
        )
        read_csv(
            dataset,
            f"data/{year}/system_data_{year}.csv",
            ["DateTime", "OutdoorTemperature"],
        )
        read_csv(
            dataset,
            f"data/{year}/zone_0_data_{year}.csv",
            [
                "DateTime",
                "ManualModeSetpointHeating",
                "RoomTemperatureSetpoint",
                "CurrentRoomTemperature",
            ],
        )

    # Scale the measured Wh values.
    for record in dataset.records.values():
        if record.ConsumedElectricalEnergy_Heating:
            record.ConsumedElectricalEnergy_Heating *= args.scale_consumed
        if record.ConsumedElectricalEnergy_DomesticHotWater:
            record.ConsumedElectricalEnergy_DomesticHotWater *= args.scale_consumed
        if record.HeatGenerated_Heating:
            record.HeatGenerated_Heating *= args.scale_generated
        if record.HeatGenerated_DomesticHotWater:
            record.HeatGenerated_DomesticHotWater *= args.scale_generated

    if args.dump:
        dataset.dump()
        return

    charts = []

    # Prepare consumed chart data.
    chart = LineChart("Energy consumed")
    chart.add_series("Heating (Wh)")
    chart.add_series("Hot water (Wh)")
    chart.add_series("Total (Wh)")
    for record in dataset.iter_records(args.date_from, args.date_to):
        if (
            record.ConsumedElectricalEnergy_Heating != None
            and record.ConsumedElectricalEnergy_DomesticHotWater != None
        ):
            chart.add_label(record.DateTime.strftime("%d %m %Y"))
            chart.add_datapoint("Heating (Wh)", record.ConsumedElectricalEnergy_Heating)
            chart.add_datapoint(
                "Hot water (Wh)",
                record.ConsumedElectricalEnergy_DomesticHotWater,
            )
            chart.add_datapoint(
                "Total (Wh)",
                record.ConsumedElectricalEnergy_Heating
                + record.ConsumedElectricalEnergy_DomesticHotWater,
            )
    charts.append(chart)

    # Prepare generated chart data.
    chart = LineChart("Heat energy generated")
    chart.add_series("Heat generated heating (Wh)")
    chart.add_series("Heat generated hot water (Wh)")
    for record in dataset.iter_records(args.date_from, args.date_to):
        if (
            record.HeatGenerated_Heating != None
            and record.HeatGenerated_DomesticHotWater != None
        ):
            chart.add_label(record.DateTime.strftime("%d %m %Y"))
            chart.add_datapoint(
                "Heat generated heating (Wh)", record.HeatGenerated_Heating
            )
            chart.add_datapoint(
                "Heat generated hot water (Wh)", record.HeatGenerated_DomesticHotWater
            )
    charts.append(chart)

    # Prepare averaged combined COP per week.
    weekly_cop = {}
    for year in [2023, 2024]:
        weekly_cop[year] = [0] * 53
        for record in dataset.iter_year(year):
            if (
                record.ConsumedElectricalEnergy_Heating != None
                and record.ConsumedElectricalEnergy_DomesticHotWater != None
                and record.HeatGenerated_Heating != None
                and record.HeatGenerated_DomesticHotWater != None
            ):
                total_consumed = (
                    record.ConsumedElectricalEnergy_Heating
                    + record.ConsumedElectricalEnergy_DomesticHotWater
                )
                total_generated = (
                    record.HeatGenerated_Heating + record.HeatGenerated_DomesticHotWater
                )
                cop_combined = (
                    0 if total_consumed == 0 else total_generated / total_consumed
                )
                if cop_combined > 6:
                    # Erronious data point.
                    continue
                weekly_cop[year][record.DateTime.isocalendar().week] += cop_combined
        # Divide sums through for average.
        weekly_cop[year] = [x / 7 for x in weekly_cop[year]]

    # Prepare weekly COP
    chart = LineChart("Weekly averaged COP")
    for week in range(1, 53):
        chart.add_label(str(week))
    for year in [2023, 2024]:
        chart.add_series(str(year))
        for x in weekly_cop[year]:
            chart.add_datapoint(str(year), x)
    charts.append(chart)

    # Prepare the COP chart data.
    chart = LineChart("COP")
    chart.add_series("COP heating")
    chart.add_series("COP hot water")
    for record in dataset.iter_records(args.date_from, args.date_to):
        if (
            record.ConsumedElectricalEnergy_Heating != None
            and record.ConsumedElectricalEnergy_DomesticHotWater != None
            and record.HeatGenerated_Heating != None
            and record.HeatGenerated_DomesticHotWater != None
        ):
            cop_heating = (
                0
                if record.ConsumedElectricalEnergy_Heating == 0
                else record.HeatGenerated_Heating
                / record.ConsumedElectricalEnergy_Heating
            )
            cop_water = (
                0
                if record.ConsumedElectricalEnergy_DomesticHotWater == 0
                else record.HeatGenerated_DomesticHotWater
                / record.ConsumedElectricalEnergy_DomesticHotWater
            )
            if cop_heating > 6 or cop_water > 6:
                # Erronious data point.
                continue
            chart.add_label(record.DateTime.strftime("%d %m %Y"))
            chart.add_datapoint("COP heating", cop_heating)
            chart.add_datapoint("COP hot water", cop_water)
    charts.append(chart)

    # Prepare the DHW chart data.
    chart = LineChart("Hot water temperature (C)")
    chart.add_series("DHW")
    for record in dataset.iter_records(args.date_from, args.date_to):
        if record.DhwTankTemperature != None:
            chart.add_label(record.DateTime.strftime("%d %m %Y"))
            chart.add_datapoint("DHW", record.DhwTankTemperature)
    charts.append(chart)

    # Prepare the internal/external temperature chart.
    chart = LineChart("Ambient temperature")
    chart.add_series("Internal")
    chart.add_series("External")
    for record in dataset.iter_records(args.date_from, args.date_to):
        if record.OutdoorTemperature != None and record.CurrentRoomTemperature != None:
            chart.add_label(record.DateTime.strftime("%d %m %Y"))
            chart.add_datapoint("Internal", record.CurrentRoomTemperature)
            chart.add_datapoint("External", record.OutdoorTemperature)
    charts.append(chart)

    # Prepare chart of heat output vs COP
    chart = ScatterChart("Heat output vs COP averaged weekly")
    for year in [2023, 2024]:

        # Collect by week.
        heat_generated_weekly = [0] * 53
        for record in dataset.iter_year(year):
            if (
                record.HeatGenerated_Heating != None
                and record.HeatGenerated_DomesticHotWater != None
            ):
                total_generated = (
                    record.HeatGenerated_Heating + record.HeatGenerated_DomesticHotWater
                )
                heat_generated_weekly[
                    record.DateTime.isocalendar().week
                ] += total_generated

        # Divide sums through for average.
        heat_generated_weekly = [x / 7 for x in heat_generated_weekly]

        chart.add_series(str(year))
        for week in range(1, 53):
            cop = weekly_cop[year][week]
            heat = heat_generated_weekly[week]
            chart.add_datapoint(
                str(year),
                (heat, cop),
            )
    charts.append(chart)

    # Prepare year stats.
    annual_stats = []
    for year in [2023, 2024]:
        s = Stats(year)

        # Scale factors.
        s.scale_consumed = args.scale_consumed
        s.scale_generated = args.scale_generated

        # Calculate the number of days in the dataset.
        dates = [x.DateTime for x in dataset.iter_year(year)]
        diff = max(dates) - min(dates)
        seconds_in_day = 24 * 60 * 60
        s.length_days = diff.days

        # Dataset totals.
        s.annual_heating_consumed = dataset.total_year(
            year, "ConsumedElectricalEnergy_Heating"
        )
        s.annual_water_consumed = dataset.total_year(
            year, "ConsumedElectricalEnergy_DomesticHotWater"
        )
        s.annual_heating_generated = dataset.total_year(year, "HeatGenerated_Heating")
        s.annual_water_generated = dataset.total_year(
            year, "HeatGenerated_DomesticHotWater"
        )

        # Combined totals.
        s.annual_total_consumed = s.annual_heating_consumed + s.annual_water_consumed
        s.annual_total_generated = s.annual_heating_generated + s.annual_water_generated

        # COP
        s.heating_scop = s.annual_heating_generated / s.annual_heating_consumed
        s.water_scop = s.annual_water_generated / s.annual_water_consumed
        s.scop = (s.annual_heating_generated + s.annual_water_generated) / (
            s.annual_heating_consumed + s.annual_water_consumed
        )

        # Done
        annual_stats.append(s)

    # Prepare total stats.
    # TODO: refactor to remove duplication with above.
    s = Stats(year)

    # Scale factors.
    s.scale_consumed = args.scale_consumed
    s.scale_generated = args.scale_generated

    # Calculate the number of days in the dataset.
    dates = [x.DateTime for x in dataset.iter_records(args.date_from, args.date_to)]
    diff = max(dates) - min(dates)
    seconds_in_day = 24 * 60 * 60
    s.length_days = diff.days

    # Dataset totals.
    s.annual_heating_consumed = dataset.total(
        year, "ConsumedElectricalEnergy_Heating", args.date_from, args.date_to
    )
    s.annual_water_consumed = dataset.total(
        year, "ConsumedElectricalEnergy_DomesticHotWater", args.date_from, args.date_to
    )
    s.annual_heating_generated = dataset.total(
        year, "HeatGenerated_Heating", args.date_from, args.date_to
    )
    s.annual_water_generated = dataset.total(
        year, "HeatGenerated_DomesticHotWater", args.date_from, args.date_to
    )

    # Combined totals.
    s.annual_total_consumed = s.annual_heating_consumed + s.annual_water_consumed
    s.annual_total_generated = s.annual_heating_generated + s.annual_water_generated

    # COP
    s.heating_scop = s.annual_heating_generated / s.annual_heating_consumed
    s.water_scop = s.annual_water_generated / s.annual_water_consumed
    s.scop = (s.annual_heating_generated + s.annual_water_generated) / (
        s.annual_heating_consumed + s.annual_water_consumed
    )

    # Output path.
    output_path = Path(args.output_dir)
    output_path.mkdir(exist_ok=True)

    # Generate HTML
    generate_html(charts, annual_stats, s, output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Dump the contents of the CSV file in a table",
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Verbosity (-v, -vv, etc)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s (version {version})".format(version=__version__),
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Specify an output directory (default: 'output')",
    )
    parser.add_argument(
        "--scale-consumed",
        type=float,
        default=1.0,
        help="Scale measured energy consumed in Wh values, default=1.0",
    )
    parser.add_argument(
        "--scale-generated",
        type=float,
        default=1.0,
        help="Scale measured energy generated in Wh values, default=1.0",
    )
    parser.add_argument(
        "--from",
        type=lambda s: datetime.datetime.strptime(s, "%Y-%m-%d"),
        help="Only include data points from this date Y-m-d",
        dest="date_from",
    )
    parser.add_argument(
        "--to",
        type=lambda s: datetime.datetime.strptime(s, "%Y-%m-%d"),
        help="Only include data points to this date Y-m-d",
        dest="date_to",
    )
    parser.add_argument("--debug", action="store_true", help="Print debugging messages")
    args = parser.parse_args()
    # Setup logging.
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    main(args)
