import type { Metric } from "../api/mapData";
import type { WeatherMetric } from "../api/victoriaData";

export interface MetricTheme {
  lineSeriesPalette: string[];
  mapGradient: string[];
  buttonClass: string;
}

export const METRIC_THEMES: Record<Metric, MetricTheme> = {
  price: {
    lineSeriesPalette: ["#b45309", "#c2410c", "#9a3412", "#b91c1c", "#92400e"],
    mapGradient: ["#fef3c7", "#f59e0b", "#b91c1c"],
    buttonClass: "active-price",
  },
  demand: {
    lineSeriesPalette: ["#1e3a8a", "#1d4ed8", "#2563eb", "#0f766e", "#274c77"],
    mapGradient: ["#dbeafe", "#60a5fa", "#1e3a8a"],
    buttonClass: "active-demand",
  },
};

export const WEATHER_METRIC_THEMES: Record<WeatherMetric, MetricTheme> = {
  temperature: {
    lineSeriesPalette: ["#ef4444", "#dc2626", "#f97316", "#e11d48", "#fb7185"],
    mapGradient: ["#fee2e2", "#fb923c", "#b91c1c"],
    buttonClass: "active-temperature",
  },
  solar_irradiance: {
    lineSeriesPalette: ["#f59e0b", "#f97316", "#d97706", "#b45309", "#92400e"],
    mapGradient: ["#fef3c7", "#f59e0b", "#b45309"],
    buttonClass: "active-solar",
  },
  cloudcover: {
    lineSeriesPalette: ["#64748b", "#475569", "#334155", "#1f2937", "#94a3b8"],
    mapGradient: ["#e2e8f0", "#94a3b8", "#334155"],
    buttonClass: "active-cloudcover",
  },
  wind_speed: {
    lineSeriesPalette: ["#0f766e", "#0ea5a4", "#14b8a6", "#0369a1", "#0f172a"],
    mapGradient: ["#ccfbf1", "#14b8a6", "#115e59"],
    buttonClass: "active-wind",
  },
};
