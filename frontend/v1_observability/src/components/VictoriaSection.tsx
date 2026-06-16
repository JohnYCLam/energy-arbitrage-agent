import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchVictoriaData,
  type EnergyMetric,
  type VictoriaDataResponse,
  type WeatherMetric,
} from "../api/victoriaData";
import { VICTORIA_REGION_NAMES } from "../constants/victoriaRegions";
import { METRIC_THEMES, WEATHER_METRIC_THEMES } from "../theme/metricTheme";
import { VictoriaLineChart } from "./VictoriaLineChart";
import { VictoriaRegionMap } from "./VictoriaRegionMap";

const ENERGY_METRICS: EnergyMetric[] = ["demand", "price"];
const WEATHER_METRICS: WeatherMetric[] = [
  "temperature",
  "solar_irradiance",
  "cloudcover",
  "wind_speed",
];

const METRIC_LABEL: Record<EnergyMetric | WeatherMetric, string> = {
  demand: "Demand (MW)",
  price: "Price ($/MWh)",
  temperature: "Temperature (°C)",
  solar_irradiance: "Solar Irradiance (W/m2)",
  cloudcover: "Cloud Cover (%)",
  wind_speed: "Wind Speed (km/h)",
};

export function VictoriaSection() {
  const [dataset, setDataset] = useState<VictoriaDataResponse>({
    locations: [],
    energy: [],
    weather: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [selectedEnergyMetrics, setSelectedEnergyMetrics] = useState<EnergyMetric[]>(["demand"]);
  const [selectedWeatherMetrics, setSelectedWeatherMetrics] = useState<WeatherMetric[]>([
    "temperature",
  ]);
  const [selectedRegions, setSelectedRegions] = useState<string[]>(["Melbourne"]);

  const loadVictoriaData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchVictoriaData(24);
      setDataset(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Victoria data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadVictoriaData();
  }, [loadVictoriaData]);

  const latestDataTimestamp = useMemo(() => {
    const allTimestamps = [
      ...dataset.energy.map((item) => item.timestampMs),
      ...dataset.weather.map((item) => item.timestampMs),
    ];
    if (allTimestamps.length === 0) {
      return null;
    }
    return new Date(Math.max(...allTimestamps));
  }, [dataset.energy, dataset.weather]);

  const toggleEnergyMetric = (metric: EnergyMetric) => {
    setSelectedEnergyMetrics((prev) =>
      prev.includes(metric)
        ? prev.length === 1
          ? prev
          : prev.filter((item) => item !== metric)
        : [...prev, metric],
    );
  };

  const toggleWeatherMetric = (metric: WeatherMetric) => {
    setSelectedWeatherMetrics((prev) =>
      prev.includes(metric)
        ? prev.length === 1
          ? prev
          : prev.filter((item) => item !== metric)
        : [...prev, metric],
    );
  };

  const toggleRegion = (region: string) => {
    setSelectedRegions((prev) =>
      prev.includes(region)
        ? prev.length === 1
          ? prev
          : prev.filter((item) => item !== region)
        : [...prev, region],
    );
  };

  return (
    <section>
      <p className="section-description">
        Victoria-focused view from <code>/api/v1/victoria-data</code>, combining
        VIC1 energy with weather from the five representative locations.
      </p>
      {loading && <p className="status">Loading Victoria data...</p>}
      {error && <p className="status error">{error}</p>}
      {!loading && !error && dataset.energy.length === 0 && dataset.weather.length === 0 && (
        <p className="status">No data available from /api/v1/victoria-data.</p>
      )}
      {!loading && !error && (dataset.energy.length > 0 || dataset.weather.length > 0) && (
        <div className={`content-grid ${panelCollapsed ? "panel-collapsed" : ""}`}>
          <section className="visuals-column">
            <VictoriaLineChart
              energyRecords={dataset.energy}
              weatherRecords={dataset.weather}
              selectedEnergyMetrics={selectedEnergyMetrics}
              selectedWeatherMetrics={selectedWeatherMetrics}
              selectedRegions={selectedRegions}
            />
            <VictoriaRegionMap
              energyRecords={dataset.energy}
              weatherRecords={dataset.weather}
            />
          </section>

          <aside className={`filter-panel ${panelCollapsed ? "collapsed" : ""}`}>
            <div className="filter-panel-header">
              {!panelCollapsed && <h2 className="filter-panel-title">Filters</h2>}
              <button
                type="button"
                className="panel-toggle"
                onClick={() => setPanelCollapsed((prev) => !prev)}
                aria-label={panelCollapsed ? "Expand filters panel" : "Collapse filters panel"}
                title={panelCollapsed ? "Expand panel" : "Collapse panel"}
              >
                {panelCollapsed ? "◀" : "▶"}
              </button>
            </div>

            {!panelCollapsed && (
              <section className="controls">
                <div className="control-group stacked">
                  <span className="label">Energy Metrics</span>
                  <div className="option-row">
                    {ENERGY_METRICS.map((metric) => (
                      <button
                        key={metric}
                        type="button"
                        className={`metric-btn ${
                          selectedEnergyMetrics.includes(metric)
                            ? `active ${METRIC_THEMES[metric].buttonClass}`
                            : ""
                        }`}
                        onClick={() => toggleEnergyMetric(metric)}
                      >
                        {METRIC_LABEL[metric]}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="control-group stacked">
                  <span className="label">Weather Metrics</span>
                  <div className="option-row">
                    {WEATHER_METRICS.map((metric) => (
                      <button
                        key={metric}
                        type="button"
                        className={`metric-btn ${
                          selectedWeatherMetrics.includes(metric)
                            ? `active ${WEATHER_METRIC_THEMES[metric].buttonClass}`
                            : ""
                        }`}
                        onClick={() => toggleWeatherMetric(metric)}
                      >
                        {METRIC_LABEL[metric]}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="control-group stacked">
                  <span className="label">Regions</span>
                  <div className="region-list">
                    {VICTORIA_REGION_NAMES.map((region) => (
                      <button
                        key={region}
                        type="button"
                        className={selectedRegions.includes(region) ? "active" : ""}
                        onClick={() => toggleRegion(region)}
                      >
                        {region}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="control-group">
                  <button type="button" onClick={() => void loadVictoriaData()} disabled={loading}>
                    {loading ? "Refreshing..." : "Refresh Data"}
                  </button>
                </div>
              </section>
            )}
          </aside>
        </div>
      )}
      <footer className="last-updated">
        Latest update:{" "}
        {latestDataTimestamp ? latestDataTimestamp.toLocaleString() : "Not loaded yet"}
      </footer>
    </section>
  );
}
