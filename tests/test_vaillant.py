import datetime

import pytest

import vaillant

# ---------------------------------------------------------------------------
# Column names
# ---------------------------------------------------------------------------


def test_energy_column_uses_csv_spelling():
    assert (
        vaillant.energy_column(vaillant.CONSUMED, vaillant.HEATING)
        == "ConsumedElectricalEnergy:Heating"
    )


def test_energy_columns_cover_every_metric_and_domain():
    assert len(vaillant.ENERGY_COLUMNS) == len(vaillant.ENERGY_METRICS) * len(
        vaillant.ENERGY_DOMAINS
    )
    assert "ConsumedElectricalEnergy:Heating" in vaillant.ENERGY_COLUMNS


def test_attr_name_replaces_colon():
    assert (
        vaillant.attr_name("ConsumedElectricalEnergy:Heating")
        == "ConsumedElectricalEnergy_Heating"
    )


def test_record_attrs_cover_energy_and_sensor_columns():
    assert vaillant.RECORD_ATTRS[0] == "DateTime"
    for column in vaillant.ENERGY_COLUMNS + vaillant.SENSOR_COLUMNS:
        assert vaillant.attr_name(column) in vaillant.RECORD_ATTRS


def test_record_attrs_have_no_colons():
    assert all(":" not in attr for attr in vaillant.RECORD_ATTRS)


# ---------------------------------------------------------------------------
# COP
# ---------------------------------------------------------------------------


def test_cop_is_generated_over_consumed():
    assert vaillant.cop(3000.0, 1000.0) == 3.0


def test_cop_zero_consumed_is_zero():
    assert vaillant.cop(500.0, 0.0) == 0.0


def test_cop_is_not_clamped():
    # The raw ratio is kept so that aggregates (SCOP) are unaffected.
    assert vaillant.cop(9000.0, 1000.0) == 9.0


def test_reading_cop_limits_implausible_values():
    assert vaillant.reading_cop(9400.0, 1000.0) == vaillant.MAX_COP


def test_reading_cop_leaves_plausible_values():
    assert vaillant.reading_cop(3200.0, 1000.0) == 3.2


# ---------------------------------------------------------------------------
# Sensor plausibility
# ---------------------------------------------------------------------------


def test_parse_value_reads_float():
    assert vaillant.parse_value("OutdoorTemperature", "5.5") == 5.5


def test_parse_value_blank_is_none():
    assert vaillant.parse_value("OutdoorTemperature", "") is None
    assert vaillant.parse_value("OutdoorTemperature", "  ") is None


def test_parse_value_drops_outdoor_sensor_spike():
    # The outdoor sensor logs occasional -40 C glitches.
    assert vaillant.parse_value("OutdoorTemperature", "-40.0") is None


def test_parse_value_keeps_cold_but_plausible_reading():
    assert vaillant.parse_value("OutdoorTemperature", "-5.0") == -5.0


def test_parse_value_tank_runs_hotter_than_air():
    assert vaillant.parse_value("DhwTankTemperature", "55.0") == 55.0
    assert vaillant.parse_value("DhwTankTemperature", "-40.0") is None


def test_parse_value_energy_column_is_unfiltered():
    assert vaillant.parse_value("HeatGenerated:Heating", "40000.0") == 40000.0


# ---------------------------------------------------------------------------
# Daily means
# ---------------------------------------------------------------------------


def test_daily_means_averages_per_day():
    samples = [
        (datetime.datetime(2024, 1, 1, 0), 10.0),
        (datetime.datetime(2024, 1, 1, 12), 20.0),
        (datetime.datetime(2024, 1, 2, 0), 4.0),
    ]
    assert vaillant.daily_means(samples) == {
        datetime.date(2024, 1, 1): 15.0,
        datetime.date(2024, 1, 2): 4.0,
    }


def test_daily_means_empty():
    assert vaillant.daily_means([]) == {}


# ---------------------------------------------------------------------------
# File layout
# ---------------------------------------------------------------------------


def test_energy_csv_matches_serial_numbered_export(tmp_path):
    year_dir = tmp_path / "2024"
    year_dir.mkdir()
    expected = (
        year_dir / "energy_data_2024_ArothermPlus_21222500100211330001005519N3.csv"
    )
    expected.touch()
    assert vaillant.energy_csv(tmp_path, 2024) == expected


def test_sensor_csv_fills_in_the_year(tmp_path):
    assert vaillant.sensor_csv(tmp_path, 2024, vaillant.SYSTEM_CSV) == (
        tmp_path / "2024" / "system_data_2024.csv"
    )


# ---------------------------------------------------------------------------
# read_records
# ---------------------------------------------------------------------------


def _write(tmp_path, text):
    path = tmp_path / "export.csv"
    path.write_text(text)
    return path


def test_read_records_keys_values_by_column(tmp_path):
    path = _write(
        tmp_path,
        "# exported by something\n"
        "DateTime;OutdoorTemperature\n"
        "2024-01-01 00:00:00;5.0\n",
    )
    assert list(vaillant.read_records(path)) == [
        (datetime.datetime(2024, 1, 1), {"OutdoorTemperature": 5.0})
    ]


def test_read_records_skips_blank_lines(tmp_path):
    path = _write(tmp_path, "DateTime;OutdoorTemperature\n\n2024-01-01 00:00:00;5.0\n")
    assert len(list(vaillant.read_records(path))) == 1


def test_read_records_omits_blank_and_implausible_cells(tmp_path):
    path = _write(
        tmp_path,
        "DateTime;OutdoorTemperature;DhwTankTemperature\n"
        "2024-01-01 00:00:00;;45.0\n"
        "2024-01-01 01:00:00;-40.0;45.0\n",
    )
    assert [values for _, values in vaillant.read_records(path)] == [
        {"DhwTankTemperature": 45.0},
        {"DhwTankTemperature": 45.0},
    ]


def test_read_records_reads_repeated_column_blocks(tmp_path):
    # The 2023 energy export repeats its column block, with one block filled.
    columns = ";".join(["ConsumedElectricalEnergy:Heating"] * 3)
    path = _write(
        tmp_path,
        f"DateTime;{columns}\n2023-07-01 00:00:00;;;7.0\n",
    )
    assert list(vaillant.read_records(path)) == [
        (
            datetime.datetime(2023, 7, 1),
            {"ConsumedElectricalEnergy:Heating": 7.0},
        )
    ]


def test_read_records_tolerates_short_rows(tmp_path):
    path = _write(
        tmp_path,
        "DateTime;OutdoorTemperature;DhwTankTemperature\n2024-01-01 00:00:00;5.0\n",
    )
    assert list(vaillant.read_records(path)) == [
        (datetime.datetime(2024, 1, 1), {"OutdoorTemperature": 5.0})
    ]


def test_read_records_without_header_raises(tmp_path):
    path = _write(tmp_path, "# only a comment\n2024-01-01 00:00:00;5.0\n")
    with pytest.raises(ValueError):
        list(vaillant.read_records(path))


# ---------------------------------------------------------------------------
# read_column
# ---------------------------------------------------------------------------


def test_read_column_finds_column_by_header(tmp_path):
    path = _write(
        tmp_path,
        "DateTime;ManualModeSetpointHeating;CurrentRoomTemperature\n"
        "2024-01-01 00:00:00;20.0;19.5\n",
    )
    assert list(vaillant.read_column(path, "CurrentRoomTemperature")) == [
        (datetime.datetime(2024, 1, 1), 19.5)
    ]


def test_read_column_drops_blank_and_implausible(tmp_path):
    path = _write(
        tmp_path,
        "DateTime;OutdoorTemperature\n"
        "2024-01-01 00:00:00;5.0\n"
        "2024-01-01 01:00:00;\n"
        "2024-01-01 02:00:00;-40.0\n",
    )
    assert list(vaillant.read_column(path, "OutdoorTemperature")) == [
        (datetime.datetime(2024, 1, 1), 5.0)
    ]


def test_energy_csv_reports_a_missing_export(tmp_path):
    (tmp_path / "2024").mkdir()
    with pytest.raises(ValueError, match="expected one"):
        vaillant.energy_csv(tmp_path, 2024)
