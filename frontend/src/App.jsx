import { useEffect, useState } from "react";
import {
  LineChart,
  ScatterChart,
} from "@mui/x-charts";
import {
  Box,
  Container,
  Link,
  Paper,
  Stack,
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

function chartSlug(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function ChartCard({ chart }) {
  const id = chartSlug(chart.name);

  if (chart.type === "line") {
    const seriesNames = Object.keys(chart.series);
    const series = seriesNames.map((name) => ({
      label: name,
      data: chart.series[name],
      showMark: false,
    }));

    const hasDateLabels = chart.labels.length > 0 && /[a-zA-Z]/.test(chart.labels[0]);

    return (
      <Paper id={id} sx={{ p: 2, mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          {chart.name}
        </Typography>
        <LineChart
          xAxis={[{
            scaleType: "point",
            data: chart.labels,
            tickLabelStyle: hasDateLabels ? { angle: -45, textAnchor: "end", fontSize: 11 } : {},
          }]}
          yAxis={chart.y_label ? [{ label: chart.y_label }] : undefined}
          series={series}
          height={350}
          margin={hasDateLabels ? { bottom: 80 } : undefined}
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
      <Paper id={id} sx={{ p: 2, mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          {chart.name}
        </Typography>
        <ScatterChart
          series={series}
          height={chart.height ?? 350}
          xAxis={chart.x_label ? [{ label: chart.x_label }] : undefined}
          yAxis={chart.y_label ? [{ label: chart.y_label }] : undefined}
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
      <Typography variant="h4" gutterBottom id="top">
        Home Energy Data
      </Typography>
      <StatsTable annualStats={data.annual_stats} totalStats={data.total_stats} />
      <Stack direction="row" spacing={3} sx={{ mb: 4 }}>
        {data.chart_groups.map((group) => (
          <Link key={group.name} href={`#${group.name}`} underline="hover">
            {group.name}
          </Link>
        ))}
      </Stack>
      {data.chart_groups.map((group) => (
        <Box key={group.name} id={group.name} sx={{ mb: 4 }}>
          <Typography variant="h5" gutterBottom sx={{ mt: 4 }}>
            {group.name}
          </Typography>
          <Stack direction="row" spacing={3} flexWrap="wrap" sx={{ mb: 3 }}>
            {group.charts.map((chart) => (
              <Link key={chart.name} href={`#${chartSlug(chart.name)}`} underline="hover" sx={{ fontSize: "0.875rem" }}>
                {chart.name}
              </Link>
            ))}
          </Stack>
          {group.charts.map((chart) => (
            <ChartCard key={chart.name} chart={chart} />
          ))}
          <Link href="#top" underline="hover" sx={{ fontSize: "0.875rem" }}>
            Back to top
          </Link>
        </Box>
      ))}
    </Container>
  );
}
