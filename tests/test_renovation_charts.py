import datetime


import renovation
import vaillant

# Dates either side of the comparison window, derived from the window constants
# so these tests follow the window if it moves.
YEAR = renovation.YEARS[-1]
IN_WINDOW = datetime.date(YEAR, *renovation.WINDOW_FROM)
NEXT_IN_WINDOW = IN_WINDOW + datetime.timedelta(days=1)
OUT_OF_WINDOW = IN_WINDOW - datetime.timedelta(days=1)

# ---------------------------------------------------------------------------
# Comparison window
# ---------------------------------------------------------------------------


def test_in_window_includes_start_and_end():
    assert renovation.in_window(IN_WINDOW)
    assert renovation.in_window(datetime.date(YEAR, *renovation.WINDOW_TO))


def test_in_window_excludes_the_day_after_it_closes():
    closes = datetime.date(YEAR, *renovation.WINDOW_TO)
    assert not renovation.in_window(closes + datetime.timedelta(days=1))


def test_in_window_excludes_the_day_before_it_opens():
    assert not renovation.in_window(OUT_OF_WINDOW)


def test_window_label_reads_as_a_date_range():
    opens = datetime.date(YEAR, *renovation.WINDOW_FROM)
    closes = datetime.date(YEAR, *renovation.WINDOW_TO)
    assert (
        renovation.window_label()
        == f"{opens.day} {opens:%b} – {closes.day} {closes:%b}"
    )


def test_window_days_keeps_only_dates_inside_the_window():
    energy = {
        OUT_OF_WINDOW: {"a": 1.0},
        IN_WINDOW: {"a": 2.0},
    }
    assert renovation.window_days(energy) == [(IN_WINDOW, {"a": 2.0})]


# ---------------------------------------------------------------------------
# binned_means
# ---------------------------------------------------------------------------


def test_binned_means_averages_within_a_bin():
    # Three points that round to the same bin centre, so the bin qualifies.
    points = [(10.0, 1.0), (10.2, 2.0), (9.8, 3.0)]
    centres, means = renovation.binned_means(points)
    assert centres == [10.0]
    assert means == [2.0]


def test_binned_means_drops_undersampled_bins():
    points = [(10.0, 1.0), (10.2, 2.0)]
    assert renovation.binned_means(points) == ([], [])


def test_binned_means_returns_bins_in_order():
    points = [(20.0, 1.0)] * renovation.MIN_BIN_SAMPLES + [
        (0.0, 2.0)
    ] * renovation.MIN_BIN_SAMPLES
    centres, _ = renovation.binned_means(points)
    assert centres == sorted(centres)


# ---------------------------------------------------------------------------
# COP and demand points
# ---------------------------------------------------------------------------


def _energy_day(consumed_heating, generated_heating=0.0):
    return {
        "ConsumedElectricalEnergy:Heating": consumed_heating,
        "HeatGenerated:Heating": generated_heating,
    }


def test_heating_cop_points_pairs_temperature_with_cop():
    date = IN_WINDOW
    energy = {date: _energy_day(10_000.0, 30_000.0)}
    points = renovation.heating_cop_points(energy, {date: 12.5})
    assert points == [(12.5, 3.0)]


def test_heating_cop_points_clamps_implausible_cop():
    date = IN_WINDOW
    energy = {date: _energy_day(10_000.0, 100_000.0)}
    points = renovation.heating_cop_points(energy, {date: 12.5})
    assert points == [(12.5, vaillant.MAX_COP)]


def test_heating_cop_points_skips_low_demand_days():
    date = IN_WINDOW
    consumed = renovation.MIN_DAILY_HEATING_WH - 1
    energy = {date: _energy_day(consumed, 3000.0)}
    assert renovation.heating_cop_points(energy, {date: 12.5}) == []


def test_heating_cop_points_skips_days_without_a_temperature():
    date = IN_WINDOW
    energy = {date: _energy_day(10_000.0, 30_000.0)}
    assert renovation.heating_cop_points(energy, {}) == []


def test_heat_demand_points_converts_wh_to_kwh():
    date = IN_WINDOW
    energy = {date: _energy_day(10_000.0, 25_000.0)}
    assert renovation.heat_demand_points(energy, {date: 9.0}) == [(9.0, 25.0)]


# ---------------------------------------------------------------------------
# monthly_scop
# ---------------------------------------------------------------------------


def test_monthly_scop_aggregates_the_whole_month():
    energy = {
        IN_WINDOW: {
            "ConsumedElectricalEnergy:Heating": 1000.0,
            "HeatGenerated:Heating": 2000.0,
        },
        NEXT_IN_WINDOW: {
            "ConsumedElectricalEnergy:Heating": 1000.0,
            "HeatGenerated:Heating": 6000.0,
        },
    }
    assert renovation.monthly_scop(energy, "Heating") == {IN_WINDOW.month: 4.0}


def test_monthly_scop_omits_months_with_no_consumption():
    energy = {
        IN_WINDOW: {
            "ConsumedElectricalEnergy:Heating": 0.0,
            "HeatGenerated:Heating": 0.0,
        }
    }
    assert renovation.monthly_scop(energy, "Heating") == {}


def test_monthly_scop_ignores_days_outside_the_window():
    energy = {
        OUT_OF_WINDOW: {
            "ConsumedElectricalEnergy:Heating": 1000.0,
            "HeatGenerated:Heating": 9000.0,
        }
    }
    assert renovation.monthly_scop(energy, "Heating") == {}


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def _write_export(data_dir, year, name, text):
    year_dir = data_dir / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    (year_dir / name).write_text(text)


def test_read_energy_keys_rows_by_date(tmp_path):
    columns = ";".join(vaillant.ENERGY_COLUMNS)
    values = ";".join(["100.0"] * len(vaillant.ENERGY_COLUMNS))
    _write_export(
        tmp_path,
        2025,
        "energy_data_2025_ArothermPlus_ABC123.csv",
        f"DateTime;{columns}\n2025-08-01 00:00:00;{values}\n",
    )
    energy = renovation.read_energy(tmp_path, 2025)
    assert list(energy) == [datetime.date(2025, 8, 1)]
    assert energy[datetime.date(2025, 8, 1)]["HeatGenerated:Heating"] == 100.0


def test_read_energy_treats_blank_cells_as_zero(tmp_path):
    columns = ";".join(vaillant.ENERGY_COLUMNS)
    values = ";".join([""] * len(vaillant.ENERGY_COLUMNS))
    _write_export(
        tmp_path,
        2025,
        "energy_data_2025_ArothermPlus_ABC123.csv",
        f"DateTime;{columns}\n2025-08-01 00:00:00;{values}\n",
    )
    energy = renovation.read_energy(tmp_path, 2025)
    assert energy[datetime.date(2025, 8, 1)]["HeatGenerated:Heating"] == 0.0


def test_read_daily_mean_averages_the_day(tmp_path):
    _write_export(
        tmp_path,
        2025,
        "system_data_2025.csv",
        "DateTime;OutdoorTemperature\n"
        "2025-08-01 00:00:00;10.0\n"
        "2025-08-01 01:00:00;20.0\n",
    )
    result = renovation.read_daily_mean(
        tmp_path, 2025, vaillant.SYSTEM_CSV, "OutdoorTemperature"
    )
    assert result == {datetime.date(2025, 8, 1): 15.0}


def test_read_daily_mean_excludes_sensor_glitches_from_the_average(tmp_path):
    _write_export(
        tmp_path,
        2025,
        "system_data_2025.csv",
        "DateTime;OutdoorTemperature\n"
        "2025-08-01 00:00:00;10.0\n"
        "2025-08-01 01:00:00;-40.0\n",
    )
    result = renovation.read_daily_mean(
        tmp_path, 2025, vaillant.SYSTEM_CSV, "OutdoorTemperature"
    )
    assert result == {datetime.date(2025, 8, 1): 10.0}
