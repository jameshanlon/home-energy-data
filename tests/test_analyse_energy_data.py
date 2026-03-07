import datetime
import json
import pytest
import aed


# ---------------------------------------------------------------------------
# format_kwh
# ---------------------------------------------------------------------------


def test_format_kwh_wh():
    assert aed.format_kwh(500) == "500.00 Wh"


def test_format_kwh_exactly_1wh():
    assert aed.format_kwh(1) == "1.00 Wh"


def test_format_kwh_kwh():
    assert aed.format_kwh(1500) == "1.50 kWh"


def test_format_kwh_exactly_1kwh():
    assert aed.format_kwh(1000) == "1.00 kWh"


def test_format_kwh_mwh():
    assert aed.format_kwh(2_000_000) == "2.00 MWh"


def test_format_kwh_gwh():
    assert aed.format_kwh(3_000_000_000) == "3.00 GWh"


def test_format_kwh_sub_1wh_edge_case():
    # Values < 1 fall through all thresholds; the function multiplies by 1000.
    result = aed.format_kwh(0.5)
    assert result == "500.00 Wh"


# ---------------------------------------------------------------------------
# Dataset.add
# ---------------------------------------------------------------------------


def test_dataset_add_sets_datetime():
    ds = aed.Dataset()
    dt = datetime.datetime(2024, 1, 1)
    ds.add(dt, "ConsumedElectricalEnergy:Heating", 100.0)
    assert ds.records[dt].DateTime == dt


def test_dataset_add_colon_to_underscore():
    ds = aed.Dataset()
    dt = datetime.datetime(2024, 1, 1)
    ds.add(dt, "ConsumedElectricalEnergy:Heating", 42.0)
    assert ds.records[dt].ConsumedElectricalEnergy_Heating == 42.0


def test_dataset_add_duplicate_raises():
    ds = aed.Dataset()
    dt = datetime.datetime(2024, 1, 1)
    ds.add(dt, "ConsumedElectricalEnergy:Heating", 100.0)
    with pytest.raises(AssertionError):
        ds.add(dt, "ConsumedElectricalEnergy:Heating", 200.0)


def test_dataset_add_different_metrics_same_datetime():
    ds = aed.Dataset()
    dt = datetime.datetime(2024, 1, 1)
    ds.add(dt, "ConsumedElectricalEnergy:Heating", 100.0)
    ds.add(dt, "ConsumedElectricalEnergy:DomesticHotWater", 50.0)
    assert ds.records[dt].ConsumedElectricalEnergy_Heating == 100.0
    assert ds.records[dt].ConsumedElectricalEnergy_DomesticHotWater == 50.0


# ---------------------------------------------------------------------------
# Dataset.iter_records
# ---------------------------------------------------------------------------


def _make_dataset_with_datetimes(*datetimes):
    """Build a Dataset whose records have only DateTime set (no metrics)."""
    ds = aed.Dataset()
    for dt in datetimes:
        # We can't use add() since it requires a metric; set directly.
        ds.records[dt].DateTime = dt
    return ds


def test_iter_records_sorted():
    dt1 = datetime.datetime(2024, 1, 3)
    dt2 = datetime.datetime(2024, 1, 1)
    dt3 = datetime.datetime(2024, 1, 2)
    ds = _make_dataset_with_datetimes(dt1, dt2, dt3)
    result = [r.DateTime for r in ds.iter_records(None, None)]
    assert result == [dt2, dt3, dt1]


def test_iter_records_sorted_when_inserted_out_of_order():
    # Simulates the real-world case where energy CSV is read first, then
    # temperature CSVs append non-overlapping timestamps later.
    dt_later = datetime.datetime(2024, 6, 1)
    dt_earlier = datetime.datetime(2024, 1, 1)
    ds = aed.Dataset()
    ds.add(dt_later, "OutdoorTemperature", 20.0)
    ds.add(dt_earlier, "OutdoorTemperature", 5.0)
    result = [r.DateTime for r in ds.iter_records(None, None)]
    assert result == [dt_earlier, dt_later]


def test_iter_records_date_from_filter():
    dt1 = datetime.datetime(2024, 1, 1)
    dt2 = datetime.datetime(2024, 1, 2)
    dt3 = datetime.datetime(2024, 1, 3)
    ds = _make_dataset_with_datetimes(dt1, dt2, dt3)
    result = [r.DateTime for r in ds.iter_records(dt2, None)]
    assert result == [dt2, dt3]


def test_iter_records_date_to_filter():
    dt1 = datetime.datetime(2024, 1, 1)
    dt2 = datetime.datetime(2024, 1, 2)
    dt3 = datetime.datetime(2024, 1, 3)
    ds = _make_dataset_with_datetimes(dt1, dt2, dt3)
    result = [r.DateTime for r in ds.iter_records(None, dt2)]
    assert result == [dt1, dt2]


def test_iter_records_none_filters_returns_all():
    dt1 = datetime.datetime(2024, 1, 1)
    dt2 = datetime.datetime(2024, 1, 2)
    ds = _make_dataset_with_datetimes(dt1, dt2)
    result = [r.DateTime for r in ds.iter_records(None, None)]
    assert result == [dt1, dt2]


# ---------------------------------------------------------------------------
# Dataset.iter_year
# ---------------------------------------------------------------------------


def test_iter_year_returns_only_matching_year():
    ds = aed.Dataset()
    dt2023 = datetime.datetime(2023, 6, 1)
    dt2024 = datetime.datetime(2024, 6, 1)
    ds.add(dt2023, "OutdoorTemperature", 15.0)
    ds.add(dt2024, "OutdoorTemperature", 18.0)
    result = [r.DateTime for r in ds.iter_year(2024)]
    assert result == [dt2024]


def test_iter_year_empty_for_missing_year():
    ds = aed.Dataset()
    dt = datetime.datetime(2023, 1, 1)
    ds.add(dt, "OutdoorTemperature", 5.0)
    result = list(ds.iter_year(2025))
    assert result == []


# ---------------------------------------------------------------------------
# Dataset.total_year
# ---------------------------------------------------------------------------


def test_total_year_sums_metric():
    ds = aed.Dataset()
    for day in range(1, 4):
        ds.add(datetime.datetime(2024, 1, day), "OutdoorTemperature", float(day * 10))
    total = ds.total_year(2024, "OutdoorTemperature")
    assert total == 60.0


def test_total_year_treats_none_as_zero():
    ds = aed.Dataset()
    dt1 = datetime.datetime(2024, 1, 1)
    dt2 = datetime.datetime(2024, 1, 2)
    ds.add(dt1, "OutdoorTemperature", 10.0)
    # dt2 has OutdoorTemperature = None (never set)
    ds.records[dt2].DateTime = dt2
    total = ds.total_year(2024, "OutdoorTemperature")
    assert total == 10.0


def test_total_year_ignores_other_years():
    ds = aed.Dataset()
    ds.add(datetime.datetime(2023, 1, 1), "OutdoorTemperature", 100.0)
    ds.add(datetime.datetime(2024, 1, 1), "OutdoorTemperature", 5.0)
    assert ds.total_year(2024, "OutdoorTemperature") == 5.0


# ---------------------------------------------------------------------------
# Dataset.total
# ---------------------------------------------------------------------------


def test_total_sums_within_date_range():
    ds = aed.Dataset()
    for day in range(1, 6):
        ds.add(datetime.datetime(2024, 1, day), "OutdoorTemperature", 10.0)
    result = ds.total(
        2024,
        "OutdoorTemperature",
        datetime.datetime(2024, 1, 2),
        datetime.datetime(2024, 1, 4),
    )
    assert result == 30.0


def test_total_none_filters():
    ds = aed.Dataset()
    for day in range(1, 4):
        ds.add(datetime.datetime(2024, 1, day), "OutdoorTemperature", 10.0)
    result = ds.total(2024, "OutdoorTemperature", None, None)
    assert result == 30.0


# ---------------------------------------------------------------------------
# LineChart
# ---------------------------------------------------------------------------


def test_linechart_add_series_and_datapoint():
    chart = aed.LineChart("Test chart")
    chart.add_series("Series A")
    chart.add_datapoint("Series A", 42.0)
    assert chart.series["Series A"] == [42.0]


def test_linechart_add_label():
    chart = aed.LineChart("Test chart")
    chart.add_label("Jan 2024")
    assert chart.labels == ["Jan 2024"]


def test_linechart_get_symbol():
    chart = aed.LineChart("Energy consumed (Wh)")
    assert chart.get_symbol() == "energy_consumed__wh_"


def test_linechart_null_datapoint_preserved():
    chart = aed.LineChart("Test")
    chart.add_series("S")
    chart.add_datapoint("S", None)
    assert chart.series["S"] == [None]


# ---------------------------------------------------------------------------
# ScatterChart
# ---------------------------------------------------------------------------


def test_scatterchart_add_series_and_datapoint():
    chart = aed.ScatterChart("Scatter test")
    chart.add_series("2024")
    chart.add_datapoint("2024", (1.5, 3.2))
    assert chart.series["2024"] == [(1.5, 3.2)]


def test_scatterchart_get_symbol():
    chart = aed.ScatterChart("Heat output vs COP")
    assert chart.get_symbol() == "heat_output_vs_cop"


# ---------------------------------------------------------------------------
# generate_json
# ---------------------------------------------------------------------------


def _make_stats(year=2024):
    s = aed.Stats(year)
    s.length_days = 365
    s.scale_consumed = 1.0
    s.scale_generated = 1.0
    s.annual_heating_consumed = 1000.0
    s.annual_water_consumed = 500.0
    s.annual_heating_generated = 3000.0
    s.annual_water_generated = 1500.0
    s.annual_total_consumed = 1500.0
    s.annual_total_generated = 4500.0
    s.heating_scop = 3.0
    s.water_scop = 3.0
    s.scop = 3.0
    return s


def test_generate_json_top_level_structure(tmp_path):
    aed.generate_json({}, [], _make_stats(), tmp_path)
    data = json.loads((tmp_path / "data.json").read_text())
    assert "chart_groups" in data
    assert "annual_stats" in data
    assert "total_stats" in data


def test_generate_json_linechart_serialised(tmp_path):
    chart = aed.LineChart("My line chart")
    chart.y_label = "Wh"
    chart.add_series("Series A")
    chart.add_label("Jan")
    chart.add_datapoint("Series A", 100.0)

    aed.generate_json({"Group": [chart]}, [], _make_stats(), tmp_path)
    data = json.loads((tmp_path / "data.json").read_text())

    groups = data["chart_groups"]
    assert len(groups) == 1
    assert groups[0]["name"] == "Group"
    c = groups[0]["charts"][0]
    assert c["type"] == "line"
    assert c["y_label"] == "Wh"
    assert c["labels"] == ["Jan"]
    assert c["series"] == {"Series A": [100.0]}


def test_generate_json_scatterchart_serialised(tmp_path):
    chart = aed.ScatterChart("My scatter")
    chart.add_series("2024")
    chart.add_datapoint("2024", (1.0, 2.5))

    aed.generate_json({"G": [chart]}, [], _make_stats(), tmp_path)
    data = json.loads((tmp_path / "data.json").read_text())

    c = data["chart_groups"][0]["charts"][0]
    assert c["type"] == "scatter"
    assert c["series"]["2024"] == [{"x": 1.0, "y": 2.5}]


def test_generate_json_null_values_preserved(tmp_path):
    chart = aed.LineChart("Nulls")
    chart.add_series("S")
    chart.add_datapoint("S", None)
    chart.add_datapoint("S", 5.0)
    chart.add_datapoint("S", None)

    aed.generate_json({"G": [chart]}, [], _make_stats(), tmp_path)
    data = json.loads((tmp_path / "data.json").read_text())

    series_data = data["chart_groups"][0]["charts"][0]["series"]["S"]
    assert series_data == [None, 5.0, None]


def test_generate_json_annual_stats(tmp_path):
    s = _make_stats(2024)
    aed.generate_json({}, [s], _make_stats(), tmp_path)
    data = json.loads((tmp_path / "data.json").read_text())
    assert len(data["annual_stats"]) == 1
    assert data["annual_stats"][0]["year"] == 2024
    assert data["annual_stats"][0]["scop"] == 3.0


# ---------------------------------------------------------------------------
# read_csv
# ---------------------------------------------------------------------------


def test_read_csv_populates_dataset(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "DateTime;ConsumedElectricalEnergy:Heating;ConsumedElectricalEnergy:DomesticHotWater\n"
        "2024-03-15 12:00:00;100.0;50.0\n"
    )
    ds = aed.Dataset()
    aed.read_csv(
        ds,
        str(csv_file),
        [
            "DateTime",
            "ConsumedElectricalEnergy:Heating",
            "ConsumedElectricalEnergy:DomesticHotWater",
        ],
    )
    dt = datetime.datetime(2024, 3, 15, 12, 0, 0)
    assert ds.records[dt].DateTime == dt
    assert ds.records[dt].ConsumedElectricalEnergy_Heating == 100.0
    assert ds.records[dt].ConsumedElectricalEnergy_DomesticHotWater == 50.0


def test_read_csv_skips_comment_rows(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "# this is a comment\n"
        "DateTime;OutdoorTemperature\n"
        "2024-01-01 00:00:00;5.0\n"
    )
    ds = aed.Dataset()
    aed.read_csv(ds, str(csv_file), ["DateTime", "OutdoorTemperature"])
    assert len(ds.records) == 1


def test_read_csv_skips_empty_values(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "DateTime;OutdoorTemperature;DhwTankTemperature\n" "2024-01-01 00:00:00;;45.0\n"
    )
    ds = aed.Dataset()
    aed.read_csv(
        ds, str(csv_file), ["DateTime", "OutdoorTemperature", "DhwTankTemperature"]
    )
    dt = datetime.datetime(2024, 1, 1)
    assert ds.records[dt].OutdoorTemperature is None
    assert ds.records[dt].DhwTankTemperature == 45.0
