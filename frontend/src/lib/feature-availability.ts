export const featureAvailability = {
  analysis: {
    available: true,
    label: "Analytical pipelines available",
    explanation:
      "Change detection, spectral index analysis, and multimodal optical-SAR fusion with server validation.",
  },
  interactiveMap: {
    available: true,
    label: "Map and AOI tools available",
    explanation: "MapLibre interactive mapping, coordinate search, and geodesic area validation.",
  },
  history: {
    available: true,
    label: "Analysis history active",
    explanation: "Historical analysis runs and query findings are persisted to the database.",
  },
  savedAois: {
    available: true,
    label: "Saved AOIs active",
    explanation:
      "Authoritatively validated areas of interest are stored with geometry and geodesic metrics.",
  },
  missions: {
    available: false,
    label: "Missions scheduled for Phase 12",
    explanation: "Multi-target persistent campaign monitoring is scheduled for Roadmap Phase 12.",
  },
  reports: {
    available: true,
    label: "Evidence reports active",
    explanation:
      "Audit-ready ReportLab PDF dossiers and immutable JSON snapshots with SHA-256 verification.",
  },
} as const;
