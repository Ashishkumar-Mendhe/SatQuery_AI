export const featureAvailability = {
  analysis: {
    available: true,
    label: "Single-image interpretation available",
    explanation:
      "A selected supported Sentinel-2 scene and AOI can be sent to the bounded question, caption, or grounding pipeline. Measurements and broader analysis remain unavailable.",
  },
  interactiveMap: {
    available: true,
    label: "Map and local AOI tools available",
    explanation:
      "Phase 3 provides map navigation and one browser-saved area of interest; imagery remains separate.",
  },
  history: {
    available: false,
    label: "History planned",
    explanation: "No analysis history exists because analysis sessions are not implemented yet.",
  },
  savedAois: {
    available: false,
    label: "Server-saved AOIs planned",
    explanation:
      "The active AOI is saved only in this browser; account-backed AOI lists are not implemented.",
  },
  missions: {
    available: false,
    label: "Missions planned",
    explanation: "Mission organization is not available in the current workspace.",
  },
  reports: {
    available: false,
    label: "Reports planned",
    explanation: "Reports require real, traceable analysis results and are not available yet.",
  },
} as const;
