import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import dayjs from "dayjs";
import type { EChartsOption } from "echarts";
import type { MapDataRecord, Metric } from "../api/mapData";
import { METRIC_THEMES } from "../theme/metricTheme";

interface MapDataLineChartProps {
  records: MapDataRecord[];
  metric: Metric;
  visibleRegions: string[];
  highlightedRegion: string | null;
}

const METRIC_LABEL: Record<Metric, string> = {
  price: "Price ($/MWh)",
  demand: "Demand (MW)",
};

export function MapDataLineChart({
  records,
  metric,
  visibleRegions,
  highlightedRegion,
}: MapDataLineChartProps) {
  const option = useMemo<EChartsOption>(() => {
    const metricTheme = METRIC_THEMES[metric];
    const visibleSet = new Set(visibleRegions);
    const grouped = new Map<string, Array<[number, number]>>();

    for (const row of records) {
      if (!visibleSet.has(row.network_region)) {
        continue;
      }
      if (!grouped.has(row.network_region)) {
        grouped.set(row.network_region, []);
      }
      grouped.get(row.network_region)?.push([row.timestampMs, row[metric]]);
    }

    const series = [...grouped.entries()].map(([region, points]) => {
      const isHighlighted = highlightedRegion === region;
      const deEmphasized = highlightedRegion !== null && !isHighlighted;
      return {
        name: region,
        type: "line" as const,
        smooth: false,
        showSymbol: false,
        lineStyle: {
          width: isHighlighted ? 4 : 2,
          opacity: deEmphasized ? 0.25 : 1,
        },
        emphasis: {
          focus: "series" as const,
        },
        data: points,
      };
    });

    return {
      animation: false,
      color: metricTheme.lineSeriesPalette,
      textStyle: {
        color: "#1e293b",
      },
      grid: { top: 40, right: 24, bottom: 48, left: 64 },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#ffffff",
        borderColor: "#cfd7e2",
        borderWidth: 1,
        textStyle: { color: "#1e293b" },
        valueFormatter: (value) =>
          typeof value === "number" ? value.toFixed(2) : String(value ?? ""),
      },
      legend: {
        type: "scroll",
        top: 8,
        textStyle: { color: "#334155" },
      },
      xAxis: {
        type: "time",
        axisLine: { lineStyle: { color: "#b8c3d1" } },
        axisLabel: {
          color: "#5f6f84",
          formatter: (value: number) => dayjs(value).format("HH:mm"),
        },
      },
      yAxis: {
        type: "value",
        name: METRIC_LABEL[metric],
        nameTextStyle: { color: "#475569" },
        axisLine: { lineStyle: { color: "#b8c3d1" } },
        axisLabel: { color: "#5f6f84" },
        splitLine: { lineStyle: { color: "#e5eaf1" } },
      },
      dataZoom: [
        { type: "inside" },
        { type: "slider", height: 18, bottom: 8 },
      ],
      series,
    };
  }, [highlightedRegion, metric, records, visibleRegions]);

  return (
    <section className="chart-card">
      <h2>{METRIC_LABEL[metric]} by Region</h2>
      <ReactECharts option={option} style={{ height: "460px", width: "100%" }} />
    </section>
  );
}
