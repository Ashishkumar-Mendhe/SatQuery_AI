import type { DataOrigin } from "./provider-contracts";

export interface DataOriginDisplay {
  origin: DataOrigin;
  label: string;
  badgeClass: string;
  dotColor: string;
  description: string;
  isSynthetic: boolean;
}

export const DATA_ORIGIN_CONFIG: Record<DataOrigin, DataOriginDisplay> = {
  real: {
    origin: "real",
    label: "REAL DATA",
    badgeClass: "bg-emerald-950/60 text-emerald-300 border-emerald-700/50",
    dotColor: "bg-emerald-400",
    description: "Verified real satellite imagery from live constellation STAC catalog.",
    isSynthetic: false,
  },
  mock: {
    origin: "mock",
    label: "DEMO DATA",
    badgeClass: "bg-amber-950/60 text-amber-300 border-amber-700/50",
    dotColor: "bg-amber-400",
    description: "Synthetic imagery generated for offline demonstration and testing.",
    isSynthetic: true,
  },
  fallback: {
    origin: "fallback",
    label: "FALLBACK DATA",
    badgeClass: "bg-purple-950/60 text-purple-300 border-purple-700/50",
    dotColor: "bg-purple-400",
    description: "Synthetic fallback data used because live provider was unreachable.",
    isSynthetic: true,
  },
  uploaded: {
    origin: "uploaded",
    label: "UPLOADED DATA",
    badgeClass: "bg-sky-950/60 text-sky-300 border-sky-700/50",
    dotColor: "bg-sky-400",
    description: "User-supplied GeoTIFF or local image file.",
    isSynthetic: false,
  },
  cached: {
    origin: "cached",
    label: "CACHED DATA",
    badgeClass: "bg-slate-900/60 text-slate-300 border-slate-700/50",
    dotColor: "bg-slate-400",
    description: "Locally cached imagery result from a prior search.",
    isSynthetic: false,
  },
};

export function getDataOriginDisplay(origin: DataOrigin): DataOriginDisplay {
  return DATA_ORIGIN_CONFIG[origin] || DATA_ORIGIN_CONFIG.mock;
}
