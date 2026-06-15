import { useCallback, useEffect, useMemo, useState } from "react";
import "./App.css";
import {
  fetchMapData,
  type MapDataRecord,
  type Metric,
} from "./api/mapData";
import { MapDataLineChart } from "./components/MapDataLineChart";
import { MapDataRegionMap } from "./components/MapDataRegionMap.tsx";
import { METRIC_THEMES } from "./theme/metricTheme";

function App() {
  const [records, setRecords] = useState<MapDataRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metric, setMetric] = useState<Metric>("price");
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [visibleRegions, setVisibleRegions] = useState<string[]>([]);
  const [highlightedRegion, setHighlightedRegion] = useState<string | null>(
    null,
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchMapData();
      setRecords(data);
      const regions = [...new Set(data.map((item) => item.network_region))];
      setVisibleRegions((prev) => {
        if (prev.length === 0) {
          return regions;
        }
        const retained = prev.filter((region) => regions.includes(region));
        const added = regions.filter((region) => !retained.includes(region));
        return [...retained, ...added];
      });
      setHighlightedRegion((prev) =>
        prev && !regions.includes(prev) ? null : prev,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load map data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const allRegions = useMemo(
    () => [...new Set(records.map((item) => item.network_region))],
    [records],
  );
  const latestDataTimestamp = useMemo(() => {
    if (records.length === 0) {
      return null;
    }
    const maxTs = records.reduce(
      (max, item) => (item.timestampMs > max ? item.timestampMs : max),
      records[0].timestampMs,
    );
    return new Date(maxTs);
  }, [records]);

  const toggleRegion = (region: string) => {
    setVisibleRegions((prev) =>
      prev.includes(region) ? prev.filter((item) => item !== region) : [...prev, region],
    );
  };

  return (
    <main className="page">
      <header className="page-header">
        <h1>NEM Regional Trends</h1>
        <p>Line chart from /api/v1/map-data with region controls.</p>
      </header>

      <div className={`content-grid ${panelCollapsed ? "panel-collapsed" : ""}`}>
        <section className="visuals-column">
          {loading && <p className="status">Loading map data...</p>}
          {error && <p className="status error">{error}</p>}
          {!loading && !error && records.length === 0 && (
            <p className="status">No data available from /api/v1/map-data.</p>
          )}

          {!loading && !error && records.length > 0 && (
            <>
              <MapDataLineChart
                records={records}
                metric={metric}
                visibleRegions={visibleRegions}
                highlightedRegion={highlightedRegion}
              />
              <MapDataRegionMap
                records={records}
                metric={metric}
                visibleRegions={visibleRegions}
                highlightedRegion={highlightedRegion}
              />
            </>
          )}

          <footer className="last-updated">
            Latest update:{" "}
            {latestDataTimestamp
              ? latestDataTimestamp.toLocaleString()
              : "Not loaded yet"}
          </footer>
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
              <div className="control-group">
                <span className="label">Metric</span>
                <button
                  type="button"
                  className={`metric-btn ${
                    metric === "price"
                      ? `active ${METRIC_THEMES.price.buttonClass}`
                      : ""
                  }`}
                  onClick={() => setMetric("price")}
                >
                  Price
                </button>
                <button
                  type="button"
                  className={`metric-btn ${
                    metric === "demand"
                      ? `active ${METRIC_THEMES.demand.buttonClass}`
                      : ""
                  }`}
                  onClick={() => setMetric("demand")}
                >
                  Demand
                </button>
              </div>

              <div className="control-group">
                <label className="label" htmlFor="highlight-region">
                  Highlight Region
                </label>
                <select
                  id="highlight-region"
                  value={highlightedRegion ?? ""}
                  onChange={(event) =>
                    setHighlightedRegion(event.target.value || null)
                  }
                >
                  <option value="">None</option>
                  {allRegions.map((region) => (
                    <option key={region} value={region}>
                      {region}
                    </option>
                  ))}
                </select>
              </div>

              <div className="control-group regions">
                <span className="label">Visible Regions</span>
                <div className="region-list">
                  {allRegions.map((region) => (
                    <label key={region}>
                      <input
                        type="checkbox"
                        checked={visibleRegions.includes(region)}
                        onChange={() => toggleRegion(region)}
                      />
                      {region}
                    </label>
                  ))}
                </div>
              </div>

              <div className="control-group">
                <button
                  type="button"
                  onClick={() => void loadData()}
                  disabled={loading}
                >
                  {loading ? "Refreshing..." : "Refresh Data"}
                </button>
              </div>
            </section>
          )}
        </aside>
      </div>
    </main>
  );
}

export default App;
