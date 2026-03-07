"""
Integration tests that load the real data files from data/.
All tests are skipped automatically if the data/ directory is not present.
"""

import json
import types
from pathlib import Path

import pytest

import aed

DATA_DIR = Path(__file__).parent.parent / "data"
YEARS = aed.YEARS  # [2023, 2024, 2025]

pytestmark = pytest.mark.skipif(
    not DATA_DIR.exists(), reason="data/ directory not found"
)


# ---------------------------------------------------------------------------
# Shared fixture: load all CSVs once per test session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_dataset():
    """Load all real CSV files exactly as main() does."""
    ds = aed.Dataset()
    for year in YEARS:
        column_repeats = 6 if year == 2023 else 1
        aed.read_csv(
            ds,
            str(
                DATA_DIR
                / f"{year}/energy_data_{year}_ArothermPlus_21222500100211330001005519N3.csv"
            ),
            ["DateTime"]
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
        aed.read_csv(
            ds,
            str(DATA_DIR / f"{year}/domestic_hot_water_255_data_{year}.csv"),
            ["DateTime", "DhwTankTemperature"],
        )
        aed.read_csv(
            ds,
            str(DATA_DIR / f"{year}/system_data_{year}.csv"),
            ["DateTime", "OutdoorTemperature"],
        )
        aed.read_csv(
            ds,
            str(DATA_DIR / f"{year}/zone_0_data_{year}.csv"),
            [
                "DateTime",
                "ManualModeSetpointHeating",
                "RoomTemperatureSetpoint",
                "CurrentRoomTemperature",
            ],
        )
    return ds


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_dataset_loads_without_errors(real_dataset):
    assert len(real_dataset.records) > 0


def test_total_record_count(real_dataset):
    # Hourly data across 3 years should produce tens of thousands of records.
    assert len(real_dataset.records) > 10_000


def test_records_per_year(real_dataset):
    for year in YEARS:
        count = sum(1 for _ in real_dataset.iter_year(year))
        assert count > 1_000, f"Too few records for {year}: {count}"


# ---------------------------------------------------------------------------
# Ordering (regression test for the out-of-order insertion bug)
# ---------------------------------------------------------------------------


def test_records_sorted_by_datetime(real_dataset):
    dts = [r.DateTime for r in real_dataset.iter_records(None, None)]
    assert dts == sorted(dts)


# ---------------------------------------------------------------------------
# Date coverage
# ---------------------------------------------------------------------------


def test_date_range_spans_each_year(real_dataset):
    for year in YEARS:
        dates = [r.DateTime for r in real_dataset.iter_year(year)]
        assert min(dates).year == year, f"Earliest record for {year} is in wrong year"
        assert max(dates).year == year, f"Latest record for {year} is in wrong year"


# ---------------------------------------------------------------------------
# Value sanity checks
# ---------------------------------------------------------------------------


def test_energy_consumed_non_negative(real_dataset):
    for record in real_dataset.iter_records(None, None):
        if record.ConsumedElectricalEnergy_Heating is not None:
            assert record.ConsumedElectricalEnergy_Heating >= 0
        if record.ConsumedElectricalEnergy_DomesticHotWater is not None:
            assert record.ConsumedElectricalEnergy_DomesticHotWater >= 0


def test_heat_generated_non_negative(real_dataset):
    for record in real_dataset.iter_records(None, None):
        if record.HeatGenerated_Heating is not None:
            assert record.HeatGenerated_Heating >= 0
        if record.HeatGenerated_DomesticHotWater is not None:
            assert record.HeatGenerated_DomesticHotWater >= 0


def test_dhw_temperature_in_range(real_dataset):
    temps = [
        r.DhwTankTemperature
        for r in real_dataset.iter_records(None, None)
        if r.DhwTankTemperature is not None
    ]
    assert len(temps) > 0, "No DHW temperature readings found"
    assert min(temps) >= 0, f"DHW temp too low: {min(temps)}"
    assert max(temps) <= 90, f"DHW temp too high: {max(temps)}"


def test_outdoor_temperature_in_range(real_dataset):
    temps = [
        r.OutdoorTemperature
        for r in real_dataset.iter_records(None, None)
        if r.OutdoorTemperature is not None
    ]
    assert len(temps) > 0, "No outdoor temperature readings found"
    assert min(temps) >= -50, f"Outdoor temp too low: {min(temps)}"
    assert max(temps) <= 60, f"Outdoor temp too high: {max(temps)}"


# ---------------------------------------------------------------------------
# Annual totals and COP
# ---------------------------------------------------------------------------


def test_total_heating_consumed_each_year(real_dataset):
    for year in YEARS:
        total = real_dataset.total_year(year, "ConsumedElectricalEnergy_Heating")
        assert total > 0, f"No heating energy consumed for {year}"


def test_total_heat_generated_each_year(real_dataset):
    for year in YEARS:
        total = real_dataset.total_year(year, "HeatGenerated_Heating")
        assert total > 0, f"No heat generated for {year}"


def test_heating_scop_plausible(real_dataset):
    """Seasonal COP for a heat pump should be between 1 and 6."""
    for year in YEARS:
        consumed = real_dataset.total_year(year, "ConsumedElectricalEnergy_Heating")
        generated = real_dataset.total_year(year, "HeatGenerated_Heating")
        if consumed > 0:
            scop = generated / consumed
            assert (
                1.0 <= scop <= 6.0
            ), f"Implausible heating SCOP for {year}: {scop:.2f}"


def test_dhw_scop_plausible(real_dataset):
    for year in YEARS:
        consumed = real_dataset.total_year(
            year, "ConsumedElectricalEnergy_DomesticHotWater"
        )
        generated = real_dataset.total_year(year, "HeatGenerated_DomesticHotWater")
        if consumed > 0:
            scop = generated / consumed
            assert 1.0 <= scop <= 6.0, f"Implausible DHW SCOP for {year}: {scop:.2f}"


# ---------------------------------------------------------------------------
# End-to-end pipeline
# ---------------------------------------------------------------------------


def test_main_end_to_end(tmp_path, monkeypatch):
    """Full pipeline: load CSVs → build charts → write data.json → parse it."""
    monkeypatch.chdir(Path(__file__).parent.parent)
    args = types.SimpleNamespace(
        dump=False,
        date_from=None,
        date_to=None,
        scale_consumed=1.0,
        scale_generated=1.0,
        output_dir=str(tmp_path),
    )
    aed.main(args)

    data = json.loads((tmp_path / "data.json").read_text())

    assert "chart_groups" in data
    assert "annual_stats" in data
    assert "total_stats" in data
    assert len(data["annual_stats"]) == len(YEARS)

    # Every year should have a plausible combined SCOP.
    for stat in data["annual_stats"]:
        assert stat["scop"] > 1.0, f"SCOP <= 1 for year {stat['year']}"

    # chart_groups should be non-empty with named groups.
    assert len(data["chart_groups"]) > 0
    group_names = [g["name"] for g in data["chart_groups"]]
    assert "All time" in group_names
