import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import * as echarts from "echarts";
import dayjs from "dayjs";
import type { EChartsOption } from "echarts";
import type {
  EnergyMetric,
  VictoriaEnergyRecord,
  VictoriaWeatherRecord,
  WeatherMetric,
} from "../api/victoriaData";
import { VICTORIA_REGIONS } from "../constants/victoriaRegions";
import { METRIC_THEMES, WEATHER_METRIC_THEMES } from "../theme/metricTheme";

interface VictoriaRegionMapProps {
  energyRecords: VictoriaEnergyRecord[];
  weatherRecords: VictoriaWeatherRecord[];
}

const MAP_NAME = "australia_with_vic_regions";
const AUSTRALIA_STATES_URL =
  "https://raw.githubusercontent.com/rowanhogan/australian-states/master/states.geojson";

const METRIC_LABEL: Record<EnergyMetric | WeatherMetric, string> = {
  demand: "Demand (MW)",
  price: "Price ($/MWh)",
  temperature: "Temperature (°C)",
  solar_irradiance: "Solar Irradiance (W/m2)",
  cloudcover: "Cloud Cover (%)",
  wind_speed: "Wind Speed (km/h)",
};

function latestValueAtOrBefore<T extends { timestampMs: number }>(
  rows: T[],
  selectedTimestamp: number,
): T | null {
  let candidate: T | null = null;
  for (const row of rows) {
    if (row.timestampMs <= selectedTimestamp) {
      candidate = row;
    } else {
      break;
    }
  }
  return candidate;
}

export function VictoriaRegionMap({
  energyRecords,
  weatherRecords,
}: VictoriaRegionMapProps) {
  const [energyMetric, setEnergyMetric] = useState<EnergyMetric>("demand");
  const [weatherMetric, setWeatherMetric] = useState<WeatherMetric>("temperature");
  const [selectedTimeIndex, setSelectedTimeIndex] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);

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

  const timestamps = useMemo(
    () =>
      [...new Set([...energyRecords.map((item) => item.timestampMs), ...weatherRecords.map((item) => item.timestampMs)])].sort(
        (a, b) => a - b,
      ),
    [energyRecords, weatherRecords],
  );

  useEffect(() => {
    setSelectedTimeIndex(Math.max(timestamps.length - 1, 0));
    setIsRunning(false);
  }, [timestamps]);

  useEffect(() => {
    let cancelled = false;
    const registerMap = async () => {
      setMapError(null);
      try {
        const ausResp = await fetch(AUSTRALIA_STATES_URL);
        if (!ausResp.ok) {
          throw new Error(`Failed map load (Australia=${ausResp.status})`);
        }
        const ausGeo = (await ausResp.json()) as {
          type: "FeatureCollection";
          features: Array<{
            type: "Feature";
            geometry: unknown;
            properties: Record<string, unknown>;
          }>;
        };

        if (!cancelled) {
          echarts.registerMap(MAP_NAME, ausGeo as any);
          setMapReady(true);
        }
      } catch (error) {
        if (!cancelled) {
          setMapError(error instanceof Error ? error.message : "Victoria map loading failed.");
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
    }, 450);
    return () => window.clearInterval(timer);
  }, [isRunning, timestamps]);

  const selectedTimestamp =
    timestamps[Math.min(selectedTimeIndex, Math.max(timestamps.length - 1, 0))];

  const buildEnergyMapData = (metric: EnergyMetric) => {
    if (!Number.isFinite(selectedTimestamp)) {
      return [] as Array<{ name: string; value: [number, number, number] }>;
    }
    const snapshot = latestValueAtOrBefore(energyRecords, selectedTimestamp);
    const value = snapshot ? snapshot[metric] : 0;
    return VICTORIA_REGIONS.map((region) => ({
      name: region.name,
      value: [region.longitude, region.latitude, value] as [number, number, number],
    }));
  };

  const buildWeatherMapData = (metric: WeatherMetric) => {
    if (!Number.isFinite(selectedTimestamp)) {
      return [] as Array<{ name: string; value: [number, number, number] }>;
    }
    return VICTORIA_REGIONS.map((region) => {
      const rows = weatherByRegion.get(region.name) ?? [];
      const snapshot = latestValueAtOrBefore(rows, selectedTimestamp);
      return {
        name: region.name,
        value: [region.longitude, region.latitude, snapshot ? snapshot[metric] : 0] as [
          number,
          number,
          number,
        ],
      };
    });
  };

  const makeMapOption = (
    metric: EnergyMetric | WeatherMetric,
    data: Array<{ name: string; value: [number, number, number] }>,
  ): EChartsOption => {
    const values = data.map((item) => item.value[2]);
    const min = values.length ? Math.min(...values) : 0;
    const maxRaw = values.length ? Math.max(...values) : 1;
    const max = maxRaw === min ? min + 1 : maxRaw;
    const gradient =
      metric === "demand" || metric === "price"
        ? METRIC_THEMES[metric].mapGradient
        : WEATHER_METRIC_THEMES[metric].mapGradient;

    return {
      animation: false,
      textStyle: { color: "#1e293b" },
      geo: {
        map: MAP_NAME,
        roam: true,
        center: [144.96, -36.85],
        zoom: 6.1,
        itemStyle: {
          areaColor: "rgba(241, 242, 244, 0.70)",
          borderColor: "#9aa3af",
          borderWidth: 1.1,
        },
        emphasis: {
          itemStyle: {
            areaColor: "rgba(230, 232, 236, 0.78)",
            borderColor: "#6b7280",
            borderWidth: 1.2,
          },
          label: { show: false },
        },
      },
      tooltip: {
        trigger: "item",
        formatter: (params) => {
          if (Array.isArray(params)) {
            return "";
          }
          const raw =
            Array.isArray(params.value) && params.value.length >= 3
              ? params.value[2]
              : params.value;
          const value = typeof raw === "number" ? raw : Number(raw ?? 0);
          const decimalPlaces = metric === "price" ? 2 : metric === "temperature" || metric === "wind_speed" ? 1 : 0;
          return `<strong>${params.name}</strong><br/>${METRIC_LABEL[metric]}: ${value.toFixed(decimalPlaces)}`;
        },
      },
      visualMap: {
        min,
        max,
        text: ["High", "Low"],
        textStyle: { color: "#5f6f84" },
        left: 10,
        bottom: 10,
        calculable: true,
        inRange: { color: gradient },
        seriesIndex: 1,
      },
      series: [
        {
          name: "Australia states",
          type: "map",
          map: MAP_NAME,
          geoIndex: 0,
          silent: true,
          label: { show: false },
          itemStyle: { opacity: 0 },
          data: [],
        },
        {
          name: METRIC_LABEL[metric],
          type: "scatter",
          coordinateSystem: "geo",
          z: 6,
          symbol: "circle",
          symbolSize: 30,
          itemStyle: {
            borderColor: "#0f172a",
            borderWidth: 1.1,
            opacity: 0.62,
          },
          label: {
            show: true,
            formatter: "{b}",
            position: "right",
            color: "#0b1220",
            fontSize: 12,
            fontWeight: 700,
            textBorderColor: "rgba(255,255,255,0.96)",
            textBorderWidth: 3,
            textShadowBlur: 2,
            textShadowColor: "rgba(255,255,255,0.45)",
          },
          emphasis: {
            scale: true,
            itemStyle: {
              opacity: 0.85,
              borderWidth: 1.5,
            },
            label: { show: true, fontWeight: "bold" },
          },
          data,
        },
      ],
    };
  };

  return (
    <section className="chart-card">
      <div className="map-header">
        <h2>Victoria Region Maps (Small Multiples)</h2>
        <p>
          Snapshot:{" "}
          {selectedTimestamp ? dayjs(selectedTimestamp).format("YYYY-MM-DD HH:mm") : "No timestamp"}
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

      <div className="victoria-map-grid">
          <div className="vic-map-card">
            <div className="vic-map-header">
              <h3>Map A - Energy ({METRIC_LABEL[energyMetric]})</h3>
              <select
                value={energyMetric}
                onChange={(event) => setEnergyMetric(event.target.value as EnergyMetric)}
              >
                <option value="demand">{METRIC_LABEL.demand}</option>
                <option value="price">{METRIC_LABEL.price}</option>
              </select>
            </div>
            {!mapReady && !mapError && <p className="status">Loading Victoria region polygons...</p>}
            {mapError && <p className="status error">{mapError}</p>}
            {mapReady && (
              <ReactECharts
                option={makeMapOption(energyMetric, buildEnergyMapData(energyMetric))}
                replaceMerge={["series"]}
                style={{ height: "430px", width: "100%" }}
              />
            )}
          </div>

          <div className="vic-map-card">
            <div className="vic-map-header">
              <h3>Map B - Weather ({METRIC_LABEL[weatherMetric]})</h3>
              <select
                value={weatherMetric}
                onChange={(event) => setWeatherMetric(event.target.value as WeatherMetric)}
              >
                <option value="temperature">{METRIC_LABEL.temperature}</option>
                <option value="solar_irradiance">{METRIC_LABEL.solar_irradiance}</option>
                <option value="cloudcover">{METRIC_LABEL.cloudcover}</option>
                <option value="wind_speed">{METRIC_LABEL.wind_speed}</option>
              </select>
            </div>
            {!mapReady && !mapError && <p className="status">Loading Victoria region polygons...</p>}
            {mapError && <p className="status error">{mapError}</p>}
            {mapReady && (
              <ReactECharts
                option={makeMapOption(weatherMetric, buildWeatherMapData(weatherMetric))}
                replaceMerge={["series"]}
                style={{ height: "430px", width: "100%" }}
              />
            )}
          </div>
      </div>
    </section>
  );
}
