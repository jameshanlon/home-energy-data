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


class Record:
    def __init__(self):
        # self.DateTime: datetime.datetime = None
        self.ConsumedElectricalEnergy_Heating: float = None
        self.ConsumedElectricalEnergy_DomesticHotWater: float = None
        self.HeatGenerated_Heating: float = None
        self.HeatGenerated_DomesticHotWater: float = None
        self.EarnedEnvironmentEnergy_Heating: float = None
        self.EarnedEnvironmentEnergy_DomesticHotWater: float = None
        self.DhwTankTemperature: float = None
        self.OutdoorTemperature: float = None
        self.RoomTemperatureSetpoint: float = None
        self.CurrentRoomTemperature: float = None


class Dataset:
    def __init__(self):
        self.records = defaultdict(Record)

    def add(self, date, metric, value):
        attr_name = metric.replace(":", "_")
        assert getattr(self.records[date], attr_name) == None, "overwriting data point"
        setattr(self.records[date], attr_name, value)

    def dump(self):
        headers = [
            "Date",
            "Electricity consumed heating (kWh)",
            "Electricity consumed hot water (kWh)",
            "Heat generated heating (kWh)",
            "Heat generated hot water (kWh)",
        ]
        table = [
            [
                r.date,
                r.consumed_heating_kwh,
                r.consumed_water_kwh,
                r.generated_heating_kwh,
                r.generated_water_kwh,
            ]
            for r in self.records
        ]
        print(tabulate(table, headers, tablefmt="simple_outline"))


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


def generate_html(dataset: Dataset, output_path: Path):
    environment = Environment(loader=FileSystemLoader("templates/"))
    template = environment.get_template("index.html")
    content = template.render(dataset=dataset)

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
                "ConsumedElectricalEnergy:Heating",
                "ConsumedElectricalEnergy:DomesticHotWater",
                "HeatGenerated:Heating",
                "HeatGenerated:DomesticHotWater",
                "EarnedEnvironmentEnergy:Heating",
                "EarnedEnvironmentEnergy:DomesticHotWater",
            ],
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
                "RoomTemperatureSetpoint",
                "CurrentRoomTemperature",
            ],
        )

    if args.dump:
        dataset.dump()

    ## Output path.
    # output_path = Path(args.output_dir)
    # output_path.mkdir(exist_ok=True)

    # generate_html(dataset, output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", help="Dump the contents of the CSV file in a table")
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
