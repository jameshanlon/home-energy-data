#!/usr/bin/env python3
"""
Analyse Vaillant energy data and produce some graphs.
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
from typing import Iterator


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


class Chart:
    def __init__(self, name: str):
        self.name = name
        self.labels = []
        self.series = {}

    def add_label(self, label: str):
        self.labels.append(label)

    def add_series(self, name: str):
        self.series[name] = []

    def add_datapoint(self, series_name: str, value: float):
        self.series[series_name].append(value)

    def get_symbol(self):
        return self.name.lower().replace(" ", "_").replace("(", "_").replace(")", "_")


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

    def iter_year(self, year: int) -> Iterator[Record]:
        for record in self.records.values():
            if record.DateTime.year == year:
                yield record

    def total(self, year: int, metric: str):
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


def generate_html(charts: list[Chart], annual_stats: list[Stats], output_path: Path):
    environment = Environment(loader=FileSystemLoader("templates/"))
    template = environment.get_template("index.html")
    content = template.render(charts=charts, annual_stats=annual_stats)

    output_file = output_path / "index.html"
    with open(output_file, mode="w", encoding="utf-8") as f:
        f.write(content)
        logging.info(f"Wrote {output_file}")


def main(args):
    dataset = Dataset()

    for year in [2023, 2024]:
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
            * 5,
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

    if args.dump:
        dataset.dump()
        return

    charts = []

    # Prepare consumed chart data.
    chart = Chart("Heat energy consumed")
    chart.add_series("Heat consumed heating (kWh)")
    chart.add_series("Heat consumed hot water (kWh)")
    for record in dataset.records.values():
        if (
            record.ConsumedElectricalEnergy_Heating != None
            and record.ConsumedElectricalEnergy_DomesticHotWater != None
        ):
            chart.add_label(record.DateTime.strftime("%m %Y"))
            chart.add_datapoint(
                "Heat consumed heating (kWh)", record.ConsumedElectricalEnergy_Heating
            )
            chart.add_datapoint(
                "Heat consumed hot water (kWh)",
                record.ConsumedElectricalEnergy_DomesticHotWater,
            )
    charts.append(chart)

    # Prepare generated chart data.
    chart = Chart("Heat energy generated")
    chart.add_series("Heat generated heating (kWh)")
    chart.add_series("Heat generated hot water (kWh)")
    for record in dataset.records.values():
        if (
            record.HeatGenerated_Heating != None
            and record.HeatGenerated_DomesticHotWater != None
        ):
            chart.add_label(record.DateTime.strftime("%m %Y"))
            chart.add_datapoint(
                "Heat generated heating (kWh)", record.HeatGenerated_Heating
            )
            chart.add_datapoint(
                "Heat generated hot water (kWh)", record.HeatGenerated_DomesticHotWater
            )
    charts.append(chart)

    # Prepare the COP chart data.
    chart = Chart("COP")
    chart.add_series("COP heating")
    chart.add_series("COP hot water")
    for record in dataset.records.values():
        if (
            record.ConsumedElectricalEnergy_Heating != None
            and record.ConsumedElectricalEnergy_DomesticHotWater != None
            and record.HeatGenerated_Heating != None
            and record.HeatGenerated_DomesticHotWater != None
        ):
            chart.add_label(record.DateTime.strftime("%m %Y"))
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
            chart.add_datapoint("COP heating", cop_heating)
            chart.add_datapoint("COP hot water", cop_water)
    charts.append(chart)

    # Prepare the DHW chart data.
    chart = Chart("Hot water temperature (C)")
    chart.add_series("DHW")
    for record in dataset.records.values():
        if record.DhwTankTemperature != None:
            chart.add_label(record.DateTime.strftime("%m %Y"))
            chart.add_datapoint("DHW", record.DhwTankTemperature)
    charts.append(chart)

    # Prepare the internal/external temperature chart.
    chart = Chart("Ambient temperature")
    chart.add_series("Internal")
    chart.add_series("External")
    for record in dataset.records.values():
        if record.OutdoorTemperature != None and record.CurrentRoomTemperature != None:
            chart.add_label(record.DateTime.strftime("%m %Y"))
            chart.add_datapoint("Internal", record.CurrentRoomTemperature)
            chart.add_datapoint("External", record.OutdoorTemperature)
    charts.append(chart)

    # Prepare chart of heat output vs COP
    chart = Chart("Heat output vs COP")
    chart.add_series("Heat output (heating) vs COP")
    for record in dataset.records.values():
        if record.HeatGenerated_Heating != None:
            cop_heating = (
                0
                if record.ConsumedElectricalEnergy_Heating == 0
                else record.HeatGenerated_Heating
                / record.ConsumedElectricalEnergy_Heating
            )
            chart.add_label(record.HeatGenerated_Heating)
            chart.add_datapoint("Heat output (heating) vs COP", cop_heating)
    charts.append(chart)

    # Prepare stats.
    annual_stats = []
    for year in [2023, 2024]:
        s = Stats(year)
        s.annual_heating_consumed = dataset.total(
            year, "ConsumedElectricalEnergy_Heating"
        )
        s.annual_water_consumed = dataset.total(
            year, "ConsumedElectricalEnergy_DomesticHotWater"
        )
        s.annual_total_consumed = s.annual_heating_consumed + s.annual_water_consumed
        s.annual_heating_generated = dataset.total(year, "HeatGenerated_Heating")
        s.annual_water_generated = dataset.total(year, "HeatGenerated_Heating")
        s.annual_total_generated = s.annual_heating_consumed + s.annual_water_consumed
        s.heating_scop = s.annual_heating_generated / s.annual_heating_consumed
        s.water_scop = s.annual_water_generated / s.annual_water_consumed
        s.scop = (s.annual_heating_generated + s.annual_water_generated) / (
            s.annual_heating_consumed + s.annual_water_consumed
        )
        annual_stats.append(s)

    # Output path.
    output_path = Path(args.output_dir)
    output_path.mkdir(exist_ok=True)

    # Generate HTML
    generate_html(charts, annual_stats, output_path)


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
    parser.add_argument("--debug", action="store_true", help="Print debugging messages")
    args = parser.parse_args()
    # Setup logging.
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    main(args)
