export interface VictoriaRegion {
  name: string;
  latitude: number;
  longitude: number;
  role: string;
  color: string;
}

export const VICTORIA_REGIONS: VictoriaRegion[] = [
  {
    name: "Melbourne",
    latitude: -37.8136,
    longitude: 144.9631,
    role: "demand_core_home_site",
    color: "#1d4ed8",
  },
  {
    name: "Mildura",
    latitude: -34.19,
    longitude: 142.16,
    role: "northwest_solar",
    color: "#b45309",
  },
  {
    name: "Ararat",
    latitude: -37.29,
    longitude: 142.93,
    role: "western_wind",
    color: "#0f766e",
  },
  {
    name: "Bendigo",
    latitude: -36.76,
    longitude: 144.28,
    role: "central_regional_load",
    color: "#7c3aed",
  },
  {
    name: "Traralgon",
    latitude: -38.2,
    longitude: 146.54,
    role: "gippsland_generation",
    color: "#be123c",
  },
];

export const VICTORIA_REGION_NAMES = VICTORIA_REGIONS.map((region) => region.name);
