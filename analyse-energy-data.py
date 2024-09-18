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


@dataclass
class Record:
    date: datetime.datetime
    consumed_heating_kwh: float
    consumed_water_kwh: float
    generated_heating_kwh: float
    generated_water_kwh: float


class Dataset:

    def __init__(self):
        self.records = []

    def add(self, record: Record):
        self.records.append(record)

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


def read_csv(filename: str) -> Dataset:
    dataset = Dataset()
    with open(filename, "r") as f:
        contents = csv.reader(f, delimiter=",", quotechar='"')
        for row in contents:
            # DateTime,
            # Date,
            # EarnedEnvironmentEnergy:Heating,
            # EarnedEnvironmentEnergy:DomesticHotWater,
            # ConsumedElectricalEnergy:Heating,
            # ConsumedElectricalEnergy:DomesticHotWater,
            # HeatGenerated:Heating,
            # HeatGenerated:DomesticHotWater,
            # COP,
            # COP (sanitised)
            if row[0].startswith("#"):
                continue
            if row[1] == "":
                continue
            date = datetime.datetime.strptime(row[1], "%Y-%m-%d")
            consumed_heating_kwh = float(row[4])
            consumed_water_kwh = float(row[5])
            generated_heating_kwh = float(row[6])
            generated_water_kwh = float(row[7])
            dataset.add(
                Record(
                    date,
                    consumed_heating_kwh,
                    consumed_water_kwh,
                    generated_heating_kwh,
                    generated_water_kwh,
                )
            )
    return dataset


def generate_html(dataset: Dataset, output_path: Path):
    environment = Environment(loader=FileSystemLoader("templates/"))
    template = environment.get_template("index.html")
    content = template.render(dataset=dataset)

    output_file = output_path / "index.html"
    with open(output_file, mode="w", encoding="utf-8") as f:
        f.write(content)
        logging.info(f"Wrote {output_file}")


def main(args):
    dataset = read_csv(args.file)

    if args.dump:
        dataset.dump()

    # Output path.
    output_path = Path(args.output_dir)
    output_path.mkdir(exist_ok=True)

    generate_html(dataset, output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="CSV file")
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
