import type { IconName } from "@/components/icon";
import type { AnalysisMode } from "./analysis-contracts";

export interface AnalysisModeDefinition {
  readonly key: AnalysisMode;
  readonly label: string;
  readonly badge: string;
  readonly description: string;
  readonly icon: IconName;
  readonly requiredInputs: readonly string[];
  readonly temporalRequirement: "single" | "bi_temporal" | "interval";
  readonly status: "ready" | "upcoming" | "experimental";
  readonly questionPlaceholder: string;
  readonly workflowHint: string;
}

export const ANALYSIS_MODE_DEFINITIONS: Record<AnalysisMode, AnalysisModeDefinition> = {
  visual_question_answering: {
    key: "visual_question_answering",
    label: "Single Image Analysis",
    badge: "Single Scene",
    description:
      "Study one satellite acquisition over the selected AOI with natural language VQA, feature location, and spectral indices.",
    icon: "spark",
    requiredInputs: ["Active AOI", "1 Date Window", "1 Selected Scene", "Question / Action"],
    temporalRequirement: "single",
    status: "ready",
    questionPlaceholder:
      "e.g. 'Describe the land-cover patterns' or 'Where is vegetation visible?'",
    workflowHint: "Requires an active AOI, one selected acquisition, and an inquisitive query.",
  },
  change_detection: {
    key: "change_detection",
    label: "Change Detection",
    badge: "Bi-Temporal",
    description:
      "Compare two acquisitions of the same AOI across time to quantify surface differences (ΔNDVI / ΔNDWI).",
    icon: "layers",
    requiredInputs: ["Active AOI", "Before & After Dates", "Validated Scene Pair"],
    temporalRequirement: "bi_temporal",
    status: "ready",
    questionPlaceholder:
      "e.g. 'What changed between Date A and Date B?' or 'Highlight vegetation loss'",
    workflowHint: "Requires two distinct acquisition dates to compute difference rasters.",
  },
  multimodal_analysis: {
    key: "multimodal_analysis",
    label: "Optical + SAR Analysis",
    badge: "Optical & SAR",
    description:
      "Combine complementary optical reflectance with radar microwave backscatter for all-weather flood & structure analysis.",
    icon: "evidence",
    requiredInputs: ["Active AOI", "Optical Scene (Sentinel-2)", "SAR Scene (Sentinel-1)"],
    temporalRequirement: "single",
    status: "ready",
    questionPlaceholder: "e.g. 'Correlate optical land features with radar dielectric backscatter'",
    workflowHint: "Combines Sentinel-2 optical imagery with Sentinel-1 SAR backscatter.",
  },
  spatial_grounding: {
    key: "spatial_grounding",
    label: "Spatial Grounding",
    badge: "Bounding Boxes",
    description:
      "Identify and ground specific physical objects, parcels, or features with visual polygons.",
    icon: "target",
    requiredInputs: ["Active AOI", "Single Scene", "Target Feature Query"],
    temporalRequirement: "single",
    status: "ready",
    questionPlaceholder: "e.g., Highlight all water bodies and agricultural boundaries.",
    workflowHint: "Emits vector bounding boxes and segmented features.",
  },
  spectral_analysis: {
    key: "spectral_analysis",
    label: "Spectral Index Analysis",
    badge: "Multi-Band",
    description:
      "Compute surface reflectance indices including NDVI (vegetation), NDWI (water), and NDBI (built-up).",
    icon: "activity",
    requiredInputs: ["Active AOI", "Sentinel-2 Multi-Band Scene", "Spectral Focus"],
    temporalRequirement: "single",
    status: "ready",
    questionPlaceholder: "e.g., Calculate NDVI mean and distribution.",
    workflowHint: "Requires calibrated multispectral bands.",
  },
  vegetation_health: {
    key: "vegetation_health",
    label: "Vegetation Health Monitoring",
    badge: "Agriculture",
    description:
      "Track photosynthetic vitality, canopy moisture, and drought stress across agricultural plots.",
    icon: "spark",
    requiredInputs: ["Active AOI", "Date Range", "Vegetation Thresholds"],
    temporalRequirement: "interval",
    status: "upcoming",
    questionPlaceholder: "e.g., Identify crop stress and canopy greenness degradation.",
    workflowHint: "Optimized for precision agriculture and forestry management.",
  },
  water_body_monitoring: {
    key: "water_body_monitoring",
    label: "Water Body & Flood Extent",
    badge: "Hydrology",
    description:
      "Map surface water dynamics, shoreline recession, and inundation zones using NDWI masks.",
    icon: "target",
    requiredInputs: ["Active AOI", "Date Range", "Water Thresholds"],
    temporalRequirement: "interval",
    status: "upcoming",
    questionPlaceholder: "e.g., Delineate seasonal water body shrinkage and flood risk zones.",
    workflowHint: "Uses NDWI thresholding to delineate clear vs turbid open water.",
  },
};

export const PRIMARY_ANALYSIS_MODES: AnalysisModeDefinition[] = [
  ANALYSIS_MODE_DEFINITIONS.visual_question_answering,
  ANALYSIS_MODE_DEFINITIONS.change_detection,
  ANALYSIS_MODE_DEFINITIONS.multimodal_analysis,
];

export const ANALYSIS_MODE_OPTIONS = PRIMARY_ANALYSIS_MODES;

export function getAnalysisModeDefinition(mode: AnalysisMode): AnalysisModeDefinition {
  return ANALYSIS_MODE_DEFINITIONS[mode] ?? ANALYSIS_MODE_DEFINITIONS.visual_question_answering;
}
