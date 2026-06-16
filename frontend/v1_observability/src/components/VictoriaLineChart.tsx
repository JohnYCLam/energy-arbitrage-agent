import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import dayjs from "dayjs";
import type { EChartsOption } from "echarts";
import type {
  EnergyMetric,
  VictoriaEnergyRecord,
  VictoriaWeatherRecord,
  WeatherMetric,
} from "../api/victoriaData";
import { METRIC_THEMES, WEATHER_METRIC_THEMES } from "../theme/metricTheme";

interface VictoriaLineChartProps {
  energyRecords: VictoriaEnergyRecord[];
  weatherRecords: VictoriaWeatherRecord[];
  selectedEnergyMetrics: EnergyMetric[];
  selectedWeatherMetrics: WeatherMetric[];
  selectedRegions: string[];
}

const METRIC_LABEL: Record<EnergyMetric | WeatherMetric, string> = {
  demand: "Demand (MW)",
  price: "Price ($/MWh)",
  temperature: "Temperature (°C)",
  solar_irradiance: "Solar Irradiance (W/m2)",
  cloudcover: "Cloud Cover (%)",
  wind_speed: "Wind Speed (km/h)",
};

export function VictoriaLineChart({
  energyRecords,
  weatherRecords,
  selectedEnergyMetrics,
  selectedWeatherMetrics,
  selectedRegions,
}: VictoriaLineChartProps) {
  const weatherByRegion = useMemo(() => {
    const grouped = new Map<string, VictoriaWeatherRecord[]>();
    for (const row of weatherRecords) {
      if (!grouped.has(row.region)) {
        grouped.set(row.region, []);
      }
      grouped.get(row.region)?.push(row);
    }
    for (const rows of grouped.values()) {
      rows.sort((a, b) => a.timestampMs - b.timestampMs);
    }
    return grouped;
  }, [weatherRecords]);

  const option = useMemo<EChartsOption>(() => {
    const selectedMetrics: Array<EnergyMetric | WeatherMetric> = [
      ...selectedEnergyMetrics,
      ...selectedWeatherMetrics,
    ];
    const axisIndexByMetric = new Map<EnergyMetric | WeatherMetric, number>();
    const yAxis: NonNullable<EChartsOption["yAxis"]> = [];
    let leftAxisOffset = 0;
    let rightAxisOffset = 0;

    for (const metric of selectedMetrics) {
      const isEnergy = metric === "demand" || metric === "price";
      axisIndexByMetric.set(metric, yAxis.length);
      yAxis.push({
        type: "value",
        name: METRIC_LABEL[metric],
        position: isEnergy ? "left" : "right",
        offset: isEnergy ? leftAxisOffset : rightAxisOffset,
        nameTextStyle: { color: "#475569" },
        axisLine: { lineStyle: { color: "#b8c3d1" } },
        axisLabel: { color: "#5f6f84" },
        splitLine: { show: yAxis.length === 0, lineStyle: { color: "#e5eaf1" } },
      });
      if (isEnergy) {
        leftAxisOffset += 54;
      } else {
        rightAxisOffset += 54;
      }
    }

    const series: NonNullable<EChartsOption["series"]> = [];

    for (const metric of selectedEnergyMetrics) {
      const color = METRIC_THEMES[metric].lineSeriesPalette[0];
      series.push({
        name: `VIC1 ${METRIC_LABEL[metric]}`,
        type: "line",
        showSymbol: false,
        yAxisIndex: axisIndexByMetric.get(metric),
        lineStyle: { width: 2.6, color },
        itemStyle: { color },
        data: energyRecords.map((row) => [row.timestampMs, row[metric]]),
      });
    }

    for (const metric of selectedWeatherMetrics) {
      const palette = WEATHER_METRIC_THEMES[metric].lineSeriesPalette;
      selectedRegions.forEach((region, regionIdx) => {
        const rows = weatherByRegion.get(region) ?? [];
        if (rows.length === 0) {
          return;
        }
        const color = palette[regionIdx % palette.length];
        series.push({
          name: `${region} ${METRIC_LABEL[metric]}`,
          type: "line",
          showSymbol: false,
          yAxisIndex: axisIndexByMetric.get(metric),
          lineStyle: { width: 2, color },
          itemStyle: { color },
          data: rows.map((row) => [row.timestampMs, row[metric]]),
        });
      });
    }

    return {
      animation: false,
      textStyle: { color: "#1e293b" },
      grid: {
        top: 58,
        right: Math.max(70, rightAxisOffset + 18),
        bottom: 54,
        left: Math.max(70, leftAxisOffset + 18),
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#ffffff",
        borderColor: "#cfd7e2",
        borderWidth: 1,
        textStyle: { color: "#1e293b" },
        valueFormatter: (value) => {
          if (typeof value !== "number") {
            return String(value ?? "");
          }
          return value.toFixed(2);
        },
      },
      legend: {
        type: "scroll",
        top: 12,
        textStyle: { color: "#334155" },
      },
      xAxis: {
        type: "time",
        axisLine: { lineStyle: { color: "#b8c3d1" } },
        axisLabel: {
          color: "#5f6f84",
          formatter: (value: number) => dayjs(value).format("MM-DD HH:mm"),
        },
      },
      yAxis,
      dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 8 }],
      series,
    };
  }, [
    energyRecords,
    selectedEnergyMetrics,
    selectedRegions,
    selectedWeatherMetrics,
    weatherByRegion,
  ]);

  return (
    <section className="chart-card">
      <h2>Victoria Focus - Energy and Weather Trends</h2>

      <ReactECharts
        option={option}
        replaceMerge={["series", "yAxis"]}
        style={{ height: "500px", width: "100%" }}
      />
    </section>
  );
}
