import type { Metric } from "../api/mapData";

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
