import axios from "axios";

export type EnergyMetric = "demand" | "price";
export type WeatherMetric =
  | "temperature"
  | "solar_irradiance"
  | "cloudcover"
  | "wind_speed";
export type VictoriaMetric = EnergyMetric | WeatherMetric;

export interface VictoriaLocation {
  name: string;
  latitude: number;
  longitude: number;
  role: string;
}

export interface VictoriaEnergyRecord {
  timestamp: string;
  timestampMs: number;
  demand: number;
  price: number;
}

export interface VictoriaWeatherRecord {
  timestamp: string;
  timestampMs: number;
  region: string;
  temperature: number;
  solar_irradiance: number;
  cloudcover: number;
  wind_speed: number;
}

export interface VictoriaDataResponse {
  locations: VictoriaLocation[];
  energy: VictoriaEnergyRecord[];
  weather: VictoriaWeatherRecord[];
}

interface RawVictoriaEnergyRecord {
  timestamp: string;
  demand: number | null;
  price: number | null;
}

interface RawVictoriaWeatherRecord {
  timestamp: string;
  region: string;
  temperature: number | null;
  solar_irradiance: number | null;
  cloudcover: number | null;
  wind_speed: number | null;
}

interface RawVictoriaDataResponse {
  locations: VictoriaLocation[];
  energy: RawVictoriaEnergyRecord[];
  weather: RawVictoriaWeatherRecord[];
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function fetchVictoriaData(hours = 24): Promise<VictoriaDataResponse> {
  const response = await axios.get<RawVictoriaDataResponse>(
    `${API_BASE_URL}/api/v1/victoria-data`,
    { params: { hours } },
  );

  const energy = response.data.energy
    .map((item) => {
      const timestampMs = new Date(item.timestamp).getTime();
      return {
        timestamp: item.timestamp,
        timestampMs,
        demand: Number(item.demand ?? 0),
        price: Number(item.price ?? 0),
      };
    })
    .filter((item) => Number.isFinite(item.timestampMs))
    .sort((a, b) => a.timestampMs - b.timestampMs);

  const weather = response.data.weather
    .map((item) => {
      const timestampMs = new Date(item.timestamp).getTime();
      return {
        timestamp: item.timestamp,
        timestampMs,
        region: item.region,
        temperature: Number(item.temperature ?? 0),
        solar_irradiance: Number(item.solar_irradiance ?? 0),
        cloudcover: Number(item.cloudcover ?? 0),
        wind_speed: Number(item.wind_speed ?? 0),
      };
    })
    .filter((item) => Number.isFinite(item.timestampMs))
    .sort((a, b) =>
      a.timestampMs === b.timestampMs
        ? a.region.localeCompare(b.region)
        : a.timestampMs - b.timestampMs,
    );

  return {
    locations: response.data.locations ?? [],
    energy,
    weather,
  };
}
