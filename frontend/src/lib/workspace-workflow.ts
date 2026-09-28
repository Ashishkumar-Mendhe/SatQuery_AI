import type { AnalysisMode } from "./analysis-contracts";
import type { SelectedAoi } from "./aoi";
import type { AoiValidationResponse } from "./aoi-validation-contracts";

export type WorkflowStep =
  | "awaiting_aoi"
  | "drawing_aoi"
  | "validating_aoi"
  | "aoi_invalid"
  | "aoi_ready"
  | "awaiting_date_range"
  | "ready_for_scene_discovery"
  | "ready_for_pairing"
  | "pair_selected"
  | "ready_for_raster_prep"
  | "rasters_prepared"
  | "ready_for_analysis"
  | "analysis_completed"
  | "ready_for_export";

export interface WorkflowAction {
  readonly stepNumber: number;
  readonly title: string;
  readonly description: string;
  readonly actionLabel: string;
  readonly actionType:
    | "select_mode"
    | "draw_aoi"
    | "fix_aoi"
    | "set_dates"
    | "discover_scenes"
    | "pair_scenes"
    | "prepare_raster"
    | "calculate_change"
    | "analyze_fusion"
    | "ask_question"
    | "export_report";
  readonly isReady: boolean;
  readonly availabilityNote?: string;
}

export interface WorkflowReadiness {
  readonly isModeReady: boolean;
  readonly isAoiReady: boolean;
  readonly isDateRangeReady: boolean;
  readonly isScenesReady: boolean;
  readonly isPreparationReady: boolean;
  readonly isAnalysisReady: boolean;
  readonly isQuestionReady: boolean;
  readonly isReportReady: boolean;
  readonly canDiscoverScenes: boolean;
}

export interface WorkflowState {
  readonly step: WorkflowStep;
  readonly stepNumber: number;
  readonly totalSteps: number;
  readonly readiness: WorkflowReadiness;
  readonly nextAction: WorkflowAction;
  readonly statusMessage: string;
}

export interface WorkflowContext {
  readonly mode: AnalysisMode;
  readonly selectedAoi: SelectedAoi | null;
  readonly isDrawingAoi?: boolean;
  readonly isValidatingAoi?: boolean;
  readonly aoiValidationResult?: AoiValidationResponse | null;
  readonly dateRange?: { start_date: string; end_date: string } | null;
  readonly beforeWindow?: { start_date: string; end_date: string } | null;
  readonly afterWindow?: { start_date: string; end_date: string } | null;
  readonly hasSelectedScene?: boolean;
  readonly hasSelectedPair?: boolean;
  readonly isPairValidated?: boolean;
  readonly isRasterPrepared?: boolean;
  readonly hasAnalysisResult?: boolean;
  readonly hasAnswer?: boolean;
  readonly questionDraft?: string;
}

export function isDateRangeValid(
  dateRange?: { start_date: string; end_date: string } | null,
): boolean {
  if (!dateRange?.start_date?.trim() || !dateRange.end_date?.trim()) {
    return false;
  }
  const start = Date.parse(
    dateRange.start_date.endsWith("Z") ? dateRange.start_date : `${dateRange.start_date}T00:00:00Z`,
  );
  const end = Date.parse(
    dateRange.end_date.endsWith("Z") ? dateRange.end_date : `${dateRange.end_date}T00:00:00Z`,
  );
  return Number.isFinite(start) && Number.isFinite(end) && start <= end;
}

export function deriveWorkflowState(context: WorkflowContext): WorkflowState {
  const {
    mode,
    selectedAoi,
    isDrawingAoi = false,
    isValidatingAoi = false,
    aoiValidationResult,
    dateRange,
    beforeWindow,
    afterWindow,
    hasSelectedScene = false,
    hasSelectedPair = false,
    isPairValidated = false,
    isRasterPrepared = false,
    hasAnalysisResult = false,
    hasAnswer = false,
    questionDraft = "",
  } = context;

  const isModeReady = true;
  const isAoiDefined = Boolean(selectedAoi);
  const isAoiInvalid = Boolean(aoiValidationResult && !aoiValidationResult.valid);
  const isAoiReady = isAoiDefined && !isAoiInvalid && !isValidatingAoi;

  const isTemporalMode = mode === "change_detection" || mode === "multimodal_analysis";
  const isDateRangeReady = isTemporalMode
    ? isDateRangeValid(beforeWindow) && isDateRangeValid(afterWindow)
    : isDateRangeValid(dateRange);

  const isScenesReady = isTemporalMode ? hasSelectedPair : hasSelectedScene;
  const isPreparationReady = isRasterPrepared;
  const isAnalysisReady = hasAnalysisResult;
  const isQuestionReady = questionDraft.trim().length >= 3 && questionDraft.trim().length <= 1000;
  const isReportReady = hasAnalysisResult || hasAnswer || isScenesReady;
  const canDiscoverScenes = isAoiReady && isDateRangeReady;

  const totalSteps = isTemporalMode ? 5 : 4;

  let step: WorkflowStep = "awaiting_aoi";
  let stepNumber = 1;
  let statusMessage = "Define an Area of Interest on the map to begin.";
  let nextAction: WorkflowAction = {
    stepNumber: 1,
    title: "Define Area of Interest",
    description:
      "Draw a polygon or rectangle on the interactive map, enter coordinate bounds, or import GeoJSON.",
    actionLabel: "Draw AOI",
    actionType: "draw_aoi",
    isReady: false,
  };

  if (isDrawingAoi) {
    step = "drawing_aoi";
    stepNumber = 1;
    statusMessage = "Drawing active: click map vertices to enclose your region of interest.";
    nextAction = {
      stepNumber: 1,
      title: "Complete AOI Drawing",
      description:
        "Click vertices on the map and double-click or reconnect the first point to finish the boundary.",
      actionLabel: "Complete Drawing",
      actionType: "draw_aoi",
      isReady: false,
    };
  } else if (isValidatingAoi) {
    step = "validating_aoi";
    stepNumber = 1;
    statusMessage = "Validating geometry with authoritative backend service…";
    nextAction = {
      stepNumber: 1,
      title: "Validating Geometry",
      description:
        "Verifying ring closure, topology, and geodesic area calculations with backend gateway.",
      actionLabel: "Validating…",
      actionType: "draw_aoi",
      isReady: false,
    };
  } else if (isAoiInvalid) {
    step = "aoi_invalid";
    stepNumber = 1;
    statusMessage = "Active AOI is invalid: review topological errors in the summary panel.";
    nextAction = {
      stepNumber: 1,
      title: "Repair Area of Interest",
      description:
        "The AOI contains self-intersections or exceeds the size limit. Redraw or adjust bounds.",
      actionLabel: "Fix AOI",
      actionType: "fix_aoi",
      isReady: false,
    };
  } else if (!isAoiReady) {
    step = "awaiting_aoi";
    stepNumber = 1;
    statusMessage = "Define an Area of Interest on the map to begin.";
    nextAction = {
      stepNumber: 1,
      title: "Define Area of Interest",
      description:
        "Draw a polygon or rectangle on the interactive map, enter coordinate bounds, or import GeoJSON.",
      actionLabel: "Draw AOI",
      actionType: "draw_aoi",
      isReady: false,
    };
  } else if (!isDateRangeReady) {
    step = "awaiting_date_range";
    stepNumber = 2;
    statusMessage = isTemporalMode
      ? "AOI validated. Specify before and after temporal windows for bi-temporal pairing."
      : "AOI validated. Specify an acquisition date range for satellite scene discovery.";
    nextAction = {
      stepNumber: 2,
      title: "Specify Date Range",
      description: isTemporalMode
        ? "Select before and after date intervals to discover temporally paired acquisitions."
        : "Select start and end dates for satellite scene acquisition over your validated AOI.",
      actionLabel: "Set Date Range",
      actionType: "set_dates",
      isReady: true,
    };
  } else if (isTemporalMode) {
    // Bi-temporal workflow steps (5 steps total)
    if (!hasSelectedPair) {
      step = "ready_for_pairing";
      stepNumber = 3;
      statusMessage = "Discover and pair before/after satellite acquisitions for the selected AOI.";
      nextAction = {
        stepNumber: 3,
        title: "Pair Temporal Acquisitions",
        description:
          "Search catalogue candidates across before/after periods and select a compatible pair.",
        actionLabel: "Pair Scenes",
        actionType: "pair_scenes",
        isReady: true,
      };
    } else if (!isRasterPrepared) {
      step = "ready_for_raster_prep";
      stepNumber = 4;
      statusMessage = isPairValidated
        ? "Temporal pair validated. Harmonise and strictly co-register rasters to metric grid."
        : "Pair selected. Harmonise and co-register rasters on an identical pixel grid.";
      nextAction = {
        stepNumber: 4,
        title: "Harmonise & Prepare Rasters",
        description:
          "Reproject to metric UTM CRS, snap to common pixel intervals, and compute shared validity mask.",
        actionLabel: "Prepare Rasters",
        actionType: "prepare_raster",
        isReady: true,
      };
    } else if (!hasAnalysisResult) {
      step = "ready_for_analysis";
      stepNumber = 5;
      statusMessage =
        mode === "change_detection"
          ? "Rasters co-registered on analysis grid. Execute pixel-level change differencing."
          : "Rasters prepared. Execute multimodal optical and SAR evidence fusion.";
      nextAction = {
        stepNumber: 5,
        title:
          mode === "change_detection" ? "Calculate Change Detection" : "Execute Fusion Analysis",
        description:
          mode === "change_detection"
            ? "Calculate spectral index difference, apply thresholding, and extract candidate change regions."
            : "Classify joint optical/SAR observation states and extract candidate fused anomaly regions.",
        actionLabel: mode === "change_detection" ? "Calculate Change" : "Analyze Fusion",
        actionType: mode === "change_detection" ? "calculate_change" : "analyze_fusion",
        isReady: true,
      };
    } else {
      step = "analysis_completed";
      stepNumber = 5;
      statusMessage =
        "Analysis complete with verified evidence. Ask grounded questions or export a signed dossier.";
      nextAction = {
        stepNumber: 5,
        title: "Export Analysis Dossier",
        description:
          "Generate an immutable, verifiable PDF and JSON report describing the complete evidence snapshot.",
        actionLabel: "Export Dossier",
        actionType: "export_report",
        isReady: true,
      };
    }
  } else {
    // Single scene / query / VQA workflow steps (4 steps total)
    if (!hasSelectedScene) {
      step = "ready_for_scene_discovery";
      stepNumber = 3;
      statusMessage = "Workspace ready for satellite imagery discovery.";
      nextAction = {
        stepNumber: 3,
        title: "Discover Satellite Imagery",
        description:
          "Query Sentinel-2 L2A scenes matching your geographic footprint and temporal range.",
        actionLabel: "Discover Imagery",
        actionType: "discover_scenes",
        isReady: true,
      };
    } else if (!hasAnswer && !isQuestionReady) {
      step = "ready_for_analysis";
      stepNumber = 4;
      statusMessage =
        "Satellite scene selected. Enter a question or select a feature observation query.";
      nextAction = {
        stepNumber: 4,
        title: "Ask Query Assistant",
        description:
          "Ask natural-language questions grounded in optical reflectance and verified spatial evidence.",
        actionLabel: "Ask Question",
        actionType: "ask_question",
        isReady: true,
      };
    } else {
      step = "analysis_completed";
      stepNumber = 4;
      statusMessage =
        "Evidence gathered. Download verifiable PDF and JSON exports describing this analysis snapshot.";
      nextAction = {
        stepNumber: 4,
        title: "Export Analysis Dossier",
        description:
          "Generate an immutable, verifiable PDF and JSON report describing the complete evidence snapshot.",
        actionLabel: "Export Dossier",
        actionType: "export_report",
        isReady: true,
      };
    }
  }

  return {
    step,
    stepNumber,
    totalSteps,
    readiness: {
      isModeReady,
      isAoiReady,
      isDateRangeReady,
      isScenesReady,
      isPreparationReady,
      isAnalysisReady,
      isQuestionReady,
      isReportReady,
      canDiscoverScenes,
    },
    nextAction,
    statusMessage,
  };
}
