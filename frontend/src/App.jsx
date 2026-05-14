import { useEffect, useState } from "react";
import {
  LineChart,
  ScatterChart,
  useDrawingArea,
  useXScale,
  useYScale,
} from "@mui/x-charts";
import {
  Box,
  Container,
  Link,
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

function CopReferenceLines() {
  const xScale = useXScale();
  const yScale = useYScale();

  if (!xScale || !yScale) return null;

  const [xMin, xMax] = xScale.domain();
  const [, yMax] = yScale.domain();

  return (
    <>
      {[1, 2, 3, 4, 5].map((cop) => {
        const xStart = Math.max(xMin, 0);
        const yStart = cop * xStart;
        if (yStart > yMax) return null;

        // Clip line to chart bounds: exit through top or right edge
        const xEnd = Math.min(xMax, yMax / cop);
        const yEnd = cop * xEnd;

        const px1 = xScale(xStart);
        const py1 = yScale(yStart);
        const px2 = xScale(xEnd);
        const py2 = yScale(yEnd);

        // Place label at the line's endpoint, offset to avoid overlap
        const atTop = xEnd < xMax;

        return (
          <g key={cop}>
            <line
              x1={px1} y1={py1} x2={px2} y2={py2}
              stroke="#aaa"
              strokeWidth={1}
              strokeDasharray="5 3"
            />
            <text
              x={px2} y={py2}
              fontSize={11} fill="#888"
              dx={atTop ? 4 : -4}
              dy={atTop ? -4 : 12}
              textAnchor={atTop ? "start" : "end"}
            >
              COP {cop}
            </text>
          </g>
        );
      })}
    </>
  );
}

function chartSlug(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

const compactNumber = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
const formatYTick = (v) => (typeof v === "number" ? compactNumber.format(v) : v);

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
          yAxis={[{ label: chart.y_label ?? undefined, valueFormatter: formatYTick }]}
          series={series}
          height={350}
          margin={{ left: chart.left_margin ?? (chart.y_label ? 80 : 50), ...(hasDateLabels ? { bottom: 80 } : {}) }}
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
          margin={{ left: 80 }}
        >
          {chart.cop_reference_lines && <CopReferenceLines />}
        </ScatterChart>
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
      <Box
        component="ul"
        sx={{
          mb: 4,
          pl: 3,
          typography: "body1",
          lineHeight: 1.8,
        }}
      >
        {data.chart_groups.map((group) => (
          <li key={group.name}>
            <Link href={`#${group.name}`} underline="hover">
              {group.name}
            </Link>
          </li>
        ))}
      </Box>
      {data.chart_groups.map((group) => (
        <Box key={group.name} id={group.name} sx={{ mb: 4 }}>
          <Typography variant="h5" gutterBottom sx={{ mt: 4 }}>
            {group.name}
          </Typography>
          <Box
            component="ul"
            sx={{
              mb: 3,
              pl: 3,
              typography: "body1",
              lineHeight: 1.8,
            }}
          >
            {group.charts.map((chart) => (
              <li key={chart.name}>
                <Link href={`#${chartSlug(chart.name)}`} underline="hover">
                  {chart.name}
                </Link>
              </li>
            ))}
          </Box>
          {group.charts.map((chart) => (
            <Box key={chart.name}>
              <ChartCard chart={chart} />
              <Box sx={{ mb: 4 }}>
                <Link href="#top" underline="hover" sx={{ typography: "body1" }}>
                  Back to top
                </Link>
              </Box>
            </Box>
          ))}
        </Box>
      ))}
    </Container>
  );
}
