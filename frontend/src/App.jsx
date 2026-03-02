import { useEffect, useState } from "react";
import {
  LineChart,
  ScatterChart,
} from "@mui/x-charts";
import {
  Box,
  Container,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";

function formatWh(wh) {
  if (wh == null) return "";
  if (wh >= 1e9) return `${(wh / 1e9).toFixed(2)} GWh`;
  if (wh >= 1e6) return `${(wh / 1e6).toFixed(2)} MWh`;
  if (wh >= 1e3) return `${(wh / 1e3).toFixed(2)} kWh`;
  return `${wh.toFixed(2)} Wh`;
}

function StatsTable({ annualStats, totalStats }) {
  const cols = [
    { key: "year", label: "Year" },
    { key: "length_days", label: "Days" },
    {
      key: "annual_heating_consumed",
      label: "Heating consumed",
      fmt: formatWh,
    },
    { key: "annual_water_consumed", label: "DHW consumed", fmt: formatWh },
    { key: "annual_total_consumed", label: "Total consumed", fmt: formatWh },
    {
      key: "annual_heating_generated",
      label: "Heating generated",
      fmt: formatWh,
    },
    { key: "annual_water_generated", label: "DHW generated", fmt: formatWh },
    { key: "annual_total_generated", label: "Total generated", fmt: formatWh },
    { key: "heating_scop", label: "Heating SCOP", fmt: (v) => v.toFixed(2) },
    { key: "water_scop", label: "DHW SCOP", fmt: (v) => v.toFixed(2) },
    { key: "scop", label: "Combined SCOP", fmt: (v) => v.toFixed(2) },
  ];

  const rows = [
    ...annualStats,
    { ...totalStats, year: "Total" },
  ];

  return (
    <TableContainer component={Paper} sx={{ mb: 4 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            {cols.map((c) => (
              <TableCell key={c.key} sx={{ fontWeight: "bold" }}>
                {c.label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row, i) => (
            <TableRow key={i}>
              {cols.map((c) => (
                <TableCell key={c.key}>
                  {c.fmt ? c.fmt(row[c.key]) : row[c.key]}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

function ChartCard({ chart }) {
  if (chart.type === "line") {
    const seriesNames = Object.keys(chart.series);
    const series = seriesNames.map((name) => ({
      label: name,
      data: chart.series[name],
      showMark: false,
    }));

    return (
      <Paper sx={{ p: 2, mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          {chart.name}
        </Typography>
        <LineChart
          xAxis={[{ scaleType: "point", data: chart.labels }]}
          series={series}
          height={350}
        />
      </Paper>
    );
  }

  if (chart.type === "scatter") {
    const seriesNames = Object.keys(chart.series);
    const series = seriesNames.map((name) => ({
      label: name,
      data: chart.series[name].map((pt, i) => ({ id: `${name}-${i}`, x: pt.x, y: pt.y })),
    }));

    return (
      <Paper sx={{ p: 2, mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          {chart.name}
        </Typography>
        <ScatterChart
          series={series}
          height={350}
          xAxis={[{ label: "Heat generated (Wh)" }]}
          yAxis={[{ label: "COP" }]}
        />
      </Paper>
    );
  }

  return null;
}

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("./data.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <Container sx={{ mt: 4 }}>
        <Typography color="error">Failed to load data: {error}</Typography>
      </Container>
    );
  }

  if (!data) {
    return (
      <Container sx={{ mt: 4 }}>
        <Typography>Loading...</Typography>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 8 }}>
      <Typography variant="h4" gutterBottom>
        Home Energy Data
      </Typography>
      <StatsTable annualStats={data.annual_stats} totalStats={data.total_stats} />
      <Box>
        {data.charts.map((chart) => (
          <ChartCard key={chart.name} chart={chart} />
        ))}
      </Box>
    </Container>
  );
}
