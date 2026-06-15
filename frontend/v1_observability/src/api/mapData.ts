import axios from "axios";

export type Metric = "price" | "demand";

export interface MapDataRecord {
  interval: string;
  timestampMs: number;
  network_region: string;
  price: number;
  demand: number;
}

interface RawMapDataRecord {
  interval: string;
  network_region: string;
  price: number | null;
  demand: number | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function fetchMapData(): Promise<MapDataRecord[]> {
  const response = await axios.get<RawMapDataRecord[]>(
    `${API_BASE_URL}/api/v1/map-data`,
  );

  return response.data
    .map((item) => {
      const timestampMs = new Date(item.interval).getTime();
      return {
        interval: item.interval,
        timestampMs,
        network_region: item.network_region,
        price: Number(item.price ?? 0),
        demand: Number(item.demand ?? 0),
      };
    })
    .filter((item) => Number.isFinite(item.timestampMs))
    .sort((a, b) =>
      a.timestampMs === b.timestampMs
        ? a.network_region.localeCompare(b.network_region)
        : a.timestampMs - b.timestampMs,
    );
}
