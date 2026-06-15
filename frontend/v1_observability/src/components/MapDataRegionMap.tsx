import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import * as echarts from "echarts";
import dayjs from "dayjs";
import type { EChartsOption } from "echarts";
import type { MapDataRecord, Metric } from "../api/mapData";
import { METRIC_THEMES } from "../theme/metricTheme";

interface MapDataRegionMapProps {
  records: MapDataRecord[];
  metric: Metric;
  visibleRegions: string[];
  highlightedRegion: string | null;
}

const METRIC_LABEL: Record<Metric, string> = {
  price: "Price ($/MWh)",
  demand: "Demand (MW)",
};

const GEOJSON_URL =
  "https://raw.githubusercontent.com/rowanhogan/australian-states/master/states.geojson";
const MAP_NAME = "australia_states";
const NAME_PROPERTY = "STATE_NAME";

const REGION_TO_STATE_NAMES: Record<string, string[]> = {
  QLD1: ["Queensland"],
  NSW1: ["New South Wales", "Australian Capital Territory"],
  VIC1: ["Victoria"],
  SA1: ["South Australia"],
  TAS1: ["Tasmania"],
};

export function MapDataRegionMap({
  records,
  metric,
  visibleRegions,
  highlightedRegion,
}: MapDataRegionMapProps) {
  const timestamps = useMemo(
    () =>
      [...new Set(records.map((item) => item.timestampMs))].sort(
        (a, b) => a - b,
      ),
    [records],
  );
  const [selectedTimeIndex, setSelectedTimeIndex] = useState(
    Math.max(timestamps.length - 1, 0),
  );
  const [isRunning, setIsRunning] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);

  useEffect(() => {
    setSelectedTimeIndex(Math.max(timestamps.length - 1, 0));
    setIsRunning(false);
  }, [timestamps]);

  useEffect(() => {
    let cancelled = false;

    const registerMap = async () => {
      setMapError(null);
      try {
        const response = await fetch(GEOJSON_URL);
        if (!response.ok) {
          throw new Error(`Failed to load map (${response.status})`);
        }
        const geoJson = (await response.json()) as object;
        if (!cancelled) {
          echarts.registerMap(MAP_NAME, geoJson as any);
          setMapReady(true);
        }
      } catch (error) {
        if (!cancelled) {
          setMapError(
            error instanceof Error ? error.message : "Map data loading failed.",
          );
        }
      }
    };

    void registerMap();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!isRunning || timestamps.length <= 1) {
      return;
    }

    const timer = window.setInterval(() => {
      setSelectedTimeIndex((prev) => (prev + 1) % timestamps.length);
    }, 350);

    return () => window.clearInterval(timer);
  }, [isRunning, timestamps]);

  const selectedTimestamp =
    timestamps[Math.min(selectedTimeIndex, Math.max(timestamps.length - 1, 0))];

  const snapshot = useMemo(() => {
    const map = new Map<string, MapDataRecord>();
    if (!Number.isFinite(selectedTimestamp)) {
      return map;
    }
    for (const row of records) {
      if (row.timestampMs === selectedTimestamp) {
        map.set(row.network_region, row);
      }
    }
    return map;
  }, [records, selectedTimestamp]);

  const visibleSet = useMemo(() => new Set(visibleRegions), [visibleRegions]);

  const values = [...snapshot.values()]
    .filter((row) => visibleSet.has(row.network_region))
    .map((row) => row[metric]);
  const minValue = values.length ? Math.min(...values) : 0;
  const maxValue = values.length ? Math.max(...values) : 1;

  const mapOption = useMemo<EChartsOption>(() => {
    const metricTheme = METRIC_THEMES[metric];
    const regionCodeByState = new Map<string, string>();
    const data = [...snapshot.values()]
      .filter((row) => visibleSet.has(row.network_region))
      .flatMap((row) => {
        const stateNames = REGION_TO_STATE_NAMES[row.network_region] ?? [];
        return stateNames.map((stateName) => {
          regionCodeByState.set(stateName, row.network_region);
          return { name: stateName, value: row[metric] };
        });
      });

    const highlightedStateNames = highlightedRegion
      ? REGION_TO_STATE_NAMES[highlightedRegion] ?? []
      : [];

    return {
      textStyle: {
        color: "#1e293b",
      },
      tooltip: {
        trigger: "item",
        backgroundColor: "#ffffff",
        borderColor: "#cfd7e2",
        borderWidth: 1,
        textStyle: { color: "#1e293b" },
        formatter: (params) => {
          if (Array.isArray(params)) {
            return "";
          }
          const stateName = String(params.name ?? "");
          const regionCode = regionCodeByState.get(stateName);
          const value = params.value;
          const valueText =
            typeof value === "number"
              ? metric === "price"
                ? value.toFixed(2)
                : value.toFixed(0)
              : "N/A";
          return [
            `<strong>${stateName}</strong>`,
            regionCode ? `Region: ${regionCode}` : "Region: Not in NEM set",
            `${METRIC_LABEL[metric]}: ${valueText}`,
          ].join("<br/>");
        },
      },
      visualMap: {
        min: minValue,
        max: maxValue === minValue ? minValue + 1 : maxValue,
        text: ["High", "Low"],
        textStyle: { color: "#5f6f84" },
        left: 10,
        bottom: 12,
        calculable: true,
        inRange: {
          color: metricTheme.mapGradient,
        },
      },
      series: [
        {
          name: METRIC_LABEL[metric],
          type: "map",
          map: MAP_NAME,
          nameProperty: NAME_PROPERTY,
          roam: true,
          emphasis: {
            label: { show: true, color: "#0f172a" },
            itemStyle: { borderColor: "#1e293b", borderWidth: 1.8 },
          },
          itemStyle: {
            borderColor: "#aeb9c7",
            borderWidth: 1,
            areaColor: "#edf1f5",
          },
          select: { disabled: true },
          data,
        },
      ],
      geo: {
        map: MAP_NAME,
        nameProperty: NAME_PROPERTY,
        roam: true,
        itemStyle: {
          areaColor: "#f7f9fc",
          borderColor: "#b2bece",
        },
        emphasis: { disabled: true },
        selectedMode: false,
        regions: highlightedStateNames.map((stateName) => ({
          name: stateName,
          itemStyle: {
            borderColor: "#1e293b",
            borderWidth: 2.2,
          },
        })),
      },
    };
  }, [highlightedRegion, maxValue, metric, minValue, snapshot, visibleSet]);

  return (
    <section className="chart-card">
      <div className="map-header">
        <h2>{METRIC_LABEL[metric]} Region Map</h2>
        <p>
          Snapshot:{" "}
          {selectedTimestamp
            ? dayjs(selectedTimestamp).format("YYYY-MM-DD HH:mm")
            : "No timestamp"}
        </p>
      </div>

      <div className="timeline-controls">
        <input
          type="range"
          min={0}
          max={Math.max(timestamps.length - 1, 0)}
          value={Math.min(selectedTimeIndex, Math.max(timestamps.length - 1, 0))}
          onChange={(event) => {
            setSelectedTimeIndex(Number(event.target.value));
            setIsRunning(false);
          }}
          disabled={timestamps.length <= 1}
        />
        <div className="timeline-buttons">
          <button
            type="button"
            aria-label="Run timeline"
            title="Run"
            onClick={() => {
              if (timestamps.length > 1) {
                setIsRunning(true);
              }
            }}
            disabled={timestamps.length <= 1 || isRunning}
          >
            ▶
          </button>
          <button
            type="button"
            aria-label="Pause timeline"
            title="Pause"
            onClick={() => setIsRunning(false)}
            disabled={!isRunning}
          >
            ⏸
          </button>
          <button
            type="button"
            aria-label="Stop timeline"
            title="Stop"
            onClick={() => {
              setIsRunning(false);
              setSelectedTimeIndex(Math.max(timestamps.length - 1, 0));
            }}
            disabled={timestamps.length === 0}
          >
            ⏹
          </button>
        </div>
      </div>

      {!mapReady && !mapError && (
        <p className="status">Loading Australia map polygons...</p>
      )}
      {mapError && <p className="status error">{mapError}</p>}
      {mapReady && (
        <ReactECharts
          option={mapOption}
          style={{ height: "480px", width: "100%" }}
          opts={{ renderer: "canvas" }}
        />
      )}
    </section>
  );
}
