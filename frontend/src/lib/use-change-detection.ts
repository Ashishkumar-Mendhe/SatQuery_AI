"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { AOIGeometry, AnalysisWarning } from "./analysis-contracts";
import { calculateChangeDetection, ChangeClientError, listChangeMethods } from "./change-client";
import type {
  ChangeDetectionDefinition,
  ChangeDetectionMethod,
  ChangeDetectionResult,
  ChangeRegion,
  ChangeThresholdConfig,
  MaskOptions,
  ThresholdStrategy,
} from "./change-contracts";
import type { PreparedTemporalPair } from "./preparation-contracts";

export type ChangeOverlayDisplayMode = "continuous" | "classified" | "none";

export interface UseChangeDetectionProps {
  aoi: AOIGeometry | null;
  preparedPair: PreparedTemporalPair | null;
}

export interface UseChangeDetectionReturn {
  // Methods & selection
  methods: readonly ChangeDetectionDefinition[];
  selectedMethod: ChangeDetectionMethod;
  setSelectedMethod: (method: ChangeDetectionMethod) => void;
  currentDefinition: ChangeDetectionDefinition | null;
  isLoadingMethods: boolean;

  // Thresholds & config
  thresholdConfig: ChangeThresholdConfig;
  setThresholdStrategy: (strategy: ThresholdStrategy) => void;
  setPositiveThreshold: (threshold: number) => void;
  setNegativeThreshold: (threshold: number) => void;
  setStdMultiplier: (multiplier: number) => void;
  setMinClusterSizePixels: (size: number) => void;
  maskOptions: MaskOptions;
  setMaskOptions: (options: MaskOptions) => void;

  // Execution state
  isCalculating: boolean;
  result: ChangeDetectionResult | null;
  error: string | null;
  warnings: readonly AnalysisWarning[];

  // Interactivity & regions
  selectedRegion: ChangeRegion | null;
  setSelectedRegion: (region: ChangeRegion | null) => void;

  // Map overlay controls
  overlayMode: ChangeOverlayDisplayMode;
  setOverlayMode: (mode: ChangeOverlayDisplayMode) => void;
  overlayOpacity: number;
  setOverlayOpacity: (opacity: number) => void;

  // Actions
  calculateChange: () => Promise<void>;
  cancelCalculation: () => void;
  reset: () => void;
}

const DEFAULT_THRESHOLD_CONFIG: ChangeThresholdConfig = {
  strategy: "fixed",
  positive_threshold: 0.15,
  negative_threshold: -0.15,
  std_multiplier: 1.5,
  percentile_cutoff: 95.0,
  min_cluster_size_pixels: 5,
  simplify_tolerance_meters: 5.0,
};

const DEFAULT_MASK_OPTIONS: MaskOptions = {
  apply_no_data_mask: true,
  apply_cloud_mask: true,
  apply_quality_mask: true,
  include_shadow_mask: false,
  minimum_valid_data_percent: 1.0,
  custom_mask_asset_id: null,
};

export function useChangeDetection({
  aoi,
  preparedPair,
}: UseChangeDetectionProps): UseChangeDetectionReturn {
  const [methods, setMethods] = useState<ChangeDetectionDefinition[]>([]);
  const [isLoadingMethods, setIsLoadingMethods] = useState(false);
  const [selectedMethod, setSelectedMethodState] =
    useState<ChangeDetectionMethod>("ndvi_difference");

  const [thresholdConfig, setThresholdConfig] =
    useState<ChangeThresholdConfig>(DEFAULT_THRESHOLD_CONFIG);
  const [maskOptions, setMaskOptions] = useState<MaskOptions>(DEFAULT_MASK_OPTIONS);

  const [isCalculating, setIsCalculating] = useState(false);
  const [result, setResult] = useState<ChangeDetectionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<AnalysisWarning[]>([]);

  const [selectedRegion, setSelectedRegion] = useState<ChangeRegion | null>(null);
  const [overlayMode, setOverlayMode] = useState<ChangeOverlayDisplayMode>("continuous");
  const [overlayOpacity, setOverlayOpacity] = useState<number>(0.85);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Load methods registry on mount
  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    async function fetchMethods() {
      setIsLoadingMethods(true);
      try {
        const response = await listChangeMethods(controller.signal);
        if (isMounted && response.methods.length > 0) {
          setMethods(response.methods);
        }
      } catch {
        // Fallback definitions if network is offline or unmocked
      } finally {
        if (isMounted) {
          setIsLoadingMethods(false);
        }
      }
    }

    void fetchMethods();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, []);

  // Update default threshold config when method changes
  const setSelectedMethod = useCallback(
    (method: ChangeDetectionMethod) => {
      setSelectedMethodState(method);
      const def = methods.find((m) => m.method === method);
      if (def) {
        setThresholdConfig(def.default_threshold_config);
      }
    },
    [methods],
  );

  const currentDefinition = useMemo(() => {
    return methods.find((m) => m.method === selectedMethod) ?? null;
  }, [methods, selectedMethod]);

  // Setters for threshold configuration
  const setThresholdStrategy = useCallback((strategy: ThresholdStrategy) => {
    setThresholdConfig((prev) => ({ ...prev, strategy }));
  }, []);

  const setPositiveThreshold = useCallback((positive_threshold: number) => {
    setThresholdConfig((prev) => ({ ...prev, positive_threshold }));
  }, []);

  const setNegativeThreshold = useCallback((negative_threshold: number) => {
    setThresholdConfig((prev) => ({ ...prev, negative_threshold }));
  }, []);

  const setStdMultiplier = useCallback((std_multiplier: number) => {
    setThresholdConfig((prev) => ({ ...prev, std_multiplier }));
  }, []);

  const setMinClusterSizePixels = useCallback((min_cluster_size_pixels: number) => {
    setThresholdConfig((prev) => ({ ...prev, min_cluster_size_pixels }));
  }, []);

  // Invalidate result if input temporal pair changes
  const pairFingerprint = useMemo(() => {
    if (!preparedPair) return null;
    return `${preparedPair.preparation_id}_${preparedPair.before_asset.asset_id}_${preparedPair.after_asset.asset_id}`;
  }, [preparedPair]);

  useEffect(() => {
    if (pairFingerprint !== undefined) {
      setResult(null);
      setSelectedRegion(null);
      setError(null);
      setWarnings([]);
    }
  }, [pairFingerprint]);

  const cancelCalculation = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsCalculating(false);
  }, []);

  const reset = useCallback(() => {
    cancelCalculation();
    setResult(null);
    setSelectedRegion(null);
    setError(null);
    setWarnings([]);
    setThresholdConfig(DEFAULT_THRESHOLD_CONFIG);
  }, [cancelCalculation]);

  const calculateChange = useCallback(async () => {
    if (!aoi) {
      setError("An Area of Interest (AOI) must be selected before detecting change.");
      return;
    }

    if (!preparedPair) {
      setError("A prepared, co-registered temporal pair must be ready before calculating change.");
      return;
    }

    if (!preparedPair.ready_for_analysis) {
      setError("The prepared temporal pair has unresolved alignment issues or errors.");
      return;
    }

    cancelCalculation();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsCalculating(true);
    setError(null);
    setWarnings([]);
    setSelectedRegion(null);

    try {
      const response = await calculateChangeDetection(
        {
          prepared_pair_id: preparedPair.preparation_id,
          before_prepared_asset_id: preparedPair.before_asset.asset_id,
          after_prepared_asset_id: preparedPair.after_asset.asset_id,
          aoi,
          method: selectedMethod,
          threshold_config: thresholdConfig,
          mask_options: maskOptions,
          generate_overlay: true,
          generate_evidence: true,
          generate_regions: true,
          max_regions: 100,
        },
        controller.signal,
      );

      setResult(response);
      setWarnings(response.warnings);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      if (err instanceof ChangeClientError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred during change detection.");
      }
    } finally {
      setIsCalculating(false);
      abortControllerRef.current = null;
    }
  }, [aoi, preparedPair, selectedMethod, thresholdConfig, maskOptions, cancelCalculation]);

  return {
    methods,
    selectedMethod,
    setSelectedMethod,
    currentDefinition,
    isLoadingMethods,
    thresholdConfig,
    setThresholdStrategy,
    setPositiveThreshold,
    setNegativeThreshold,
    setStdMultiplier,
    setMinClusterSizePixels,
    maskOptions,
    setMaskOptions,
    isCalculating,
    result,
    error,
    warnings,
    selectedRegion,
    setSelectedRegion,
    overlayMode,
    setOverlayMode,
    overlayOpacity,
    setOverlayOpacity,
    calculateChange,
    cancelCalculation,
    reset,
  };
}
