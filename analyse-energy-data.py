#!/usr/bin/env python3
"""
Analyse Vaillant energy data.
"""

__author__ = "James Hanlon"
__version__ = "0.0.1"
__license__ = "MIT"

import argparse
import csv
import datetime
from tabulate import tabulate
from rich import print
from dataclasses import dataclass

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
            "Electricity consumed hot water (kWh)" "Heat generated heating (kWh)",
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


def main(args):
    dataset = read_csv(args.file)
    dataset.dump()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="CSV file")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Verbosity (-v, -vv, etc)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s (version {version})".format(version=__version__),
    )
    args = parser.parse_args()
    main(args)
