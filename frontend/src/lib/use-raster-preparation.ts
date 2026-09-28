"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { AOIGeometry, AnalysisWarning } from "./analysis-contracts";
import { prepareRaster, prepareTemporalPair, PreparationClientError } from "./preparation-client";
import type {
  PreparedRasterAsset,
  PreparedTemporalPair,
  PreparationStatus,
  ResamplingMethod,
  TargetGridStrategy,
} from "./preparation-contracts";

export interface UseRasterPreparationProps {
  aoi: AOIGeometry | null;
  mode: "single" | "temporal";
  singleAssetId?: string | null;
  singleSceneId?: string | null;
  beforeAssetId?: string | null;
  afterAssetId?: string | null;
  beforeSceneId?: string | null;
  afterSceneId?: string | null;
  pairId?: string | null;
}

export interface UseRasterPreparationReturn {
  // Configuration
  targetCrs: string;
  setTargetCrs: (crs: string) => void;
  targetResolutionMeters: number | null;
  setTargetResolutionMeters: (res: number | null) => void;
  resamplingMethod: ResamplingMethod;
  setResamplingMethod: (method: ResamplingMethod) => void;
  strategy: TargetGridStrategy;
  setStrategy: (strategy: TargetGridStrategy) => void;

  // Processing state
  isPreparing: boolean;
  status: PreparationStatus;
  preparedSingleAsset: PreparedRasterAsset | null;
  preparedPair: PreparedTemporalPair | null;
  error: string | null;
  warnings: AnalysisWarning[];
  blockingIssues: string[];
  isReadyForAnalysis: boolean;

  // Map preview control
  showPreparedPreview: boolean;
  setShowPreparedPreview: (show: boolean) => void;

  // Actions
  startPreparation: () => Promise<void>;
  cancelPreparation: () => void;
  reset: () => void;
}

export function useRasterPreparation({
  aoi,
  mode,
  singleAssetId,
  singleSceneId,
  beforeAssetId,
  afterAssetId,
  beforeSceneId,
  afterSceneId,
  pairId,
}: UseRasterPreparationProps): UseRasterPreparationReturn {
  const [targetCrs, setTargetCrs] = useState<string>("AUTO");
  const [targetResolutionMeters, setTargetResolutionMeters] = useState<number | null>(10.0);
  const [resamplingMethod, setResamplingMethod] = useState<ResamplingMethod>("bilinear");
  const [strategy, setStrategy] = useState<TargetGridStrategy>("common_intersection");

  const [isPreparing, setIsPreparing] = useState(false);
  const [status, setStatus] = useState<PreparationStatus>("queued");
  const [preparedSingleAsset, setPreparedSingleAsset] = useState<PreparedRasterAsset | null>(null);
  const [preparedPair, setPreparedPair] = useState<PreparedTemporalPair | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<AnalysisWarning[]>([]);
  const [blockingIssues, setBlockingIssues] = useState<string[]>([]);
  const [showPreparedPreview, setShowPreparedPreview] = useState<boolean>(true);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Compute a dependency fingerprint of the source inputs
  const inputFingerprint = useMemo(() => {
    return JSON.stringify({
      mode,
      aoi: aoi ? { type: aoi.type, coordinates: aoi.coordinates } : null,
      singleAssetId,
      singleSceneId,
      beforeAssetId,
      afterAssetId,
      beforeSceneId,
      afterSceneId,
      pairId,
      targetCrs,
      targetResolutionMeters,
      resamplingMethod,
      strategy,
    });
  }, [
    mode,
    aoi,
    singleAssetId,
    singleSceneId,
    beforeAssetId,
    afterAssetId,
    beforeSceneId,
    afterSceneId,
    pairId,
    targetCrs,
    targetResolutionMeters,
    resamplingMethod,
    strategy,
  ]);

  const lastProcessedFingerprintRef = useRef<string | null>(null);

  // Automatically invalidate prepared state if inputs change
  useEffect(() => {
    if (
      lastProcessedFingerprintRef.current &&
      lastProcessedFingerprintRef.current !== inputFingerprint
    ) {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      setIsPreparing(false);
      setStatus("queued");
      setPreparedSingleAsset(null);
      setPreparedPair(null);
      setError(null);
      setWarnings([]);
      setBlockingIssues([]);
      lastProcessedFingerprintRef.current = null;
    }
  }, [inputFingerprint]);

  const cancelPreparation = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsPreparing(false);
    setStatus("cancelled");
  }, []);

  const reset = useCallback(() => {
    cancelPreparation();
    setStatus("queued");
    setPreparedSingleAsset(null);
    setPreparedPair(null);
    setError(null);
    setWarnings([]);
    setBlockingIssues([]);
    lastProcessedFingerprintRef.current = null;
  }, [cancelPreparation]);

  const startPreparation = useCallback(async () => {
    if (!aoi) {
      setError("Please select and validate an Area of Interest (AOI) first.");
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsPreparing(true);
    setError(null);
    setWarnings([]);
    setBlockingIssues([]);
    setStatus("validating_inputs");

    try {
      if (mode === "single") {
        if (!singleAssetId || !singleSceneId) {
          throw new Error("Missing single scene or analysis raster asset ID.");
        }

        setStatus("reprojecting");
        const asset = await prepareRaster(
          {
            source_asset_id: singleAssetId,
            scene_id: singleSceneId,
            aoi,
            target_crs: targetCrs === "AUTO" ? null : targetCrs,
            target_resolution_meters: targetResolutionMeters,
            resampling_method: resamplingMethod,
            clip_to_aoi: true,
            mask_no_data: true,
            generate_preview: true,
          },
          controller.signal,
        );

        setPreparedSingleAsset(asset);
        setPreparedPair(null);
        setWarnings(asset.warnings || []);
        setBlockingIssues([]);
        setStatus(asset.warnings?.length ? "ready_with_warnings" : "ready");
        lastProcessedFingerprintRef.current = inputFingerprint;
      } else {
        if (!beforeAssetId || !afterAssetId) {
          throw new Error("Missing before or after analysis raster asset IDs.");
        }

        setStatus("aligning");
        const pair = await prepareTemporalPair(
          {
            pair_id: pairId || `pair-${beforeAssetId}-${afterAssetId}`,
            before_asset_id: beforeAssetId,
            after_asset_id: afterAssetId,
            aoi,
            strategy,
            target_crs: targetCrs === "AUTO" ? null : targetCrs,
            target_resolution_meters: targetResolutionMeters,
            optical_resampling_method: resamplingMethod,
            use_common_intersection: true,
            generate_previews: true,
          },
          controller.signal,
        );

        setPreparedPair(pair);
        setPreparedSingleAsset(null);
        setWarnings(pair.warnings || []);
        setBlockingIssues(pair.blocking_issues || []);
        setStatus(
          pair.blocking_issues?.length
            ? "failed"
            : pair.warnings?.length
              ? "ready_with_warnings"
              : "ready",
        );
        lastProcessedFingerprintRef.current = inputFingerprint;
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setStatus("cancelled");
        return;
      }
      const msg =
        err instanceof PreparationClientError
          ? err.message
          : err instanceof Error
            ? err.message
            : "An unexpected error occurred during raster preparation.";
      setError(msg);
      setStatus("failed");
    } finally {
      setIsPreparing(false);
      abortControllerRef.current = null;
    }
  }, [
    aoi,
    mode,
    singleAssetId,
    singleSceneId,
    beforeAssetId,
    afterAssetId,
    pairId,
    targetCrs,
    targetResolutionMeters,
    resamplingMethod,
    strategy,
    inputFingerprint,
  ]);

  const isReadyForAnalysis = useMemo(() => {
    if (mode === "single") {
      return (
        preparedSingleAsset !== null && (status === "ready" || status === "ready_with_warnings")
      );
    }
    return (
      Boolean(preparedPair?.ready_for_analysis) &&
      (status === "ready" || status === "ready_with_warnings") &&
      blockingIssues.length === 0
    );
  }, [mode, preparedSingleAsset, preparedPair, status, blockingIssues]);

  return {
    targetCrs,
    setTargetCrs,
    targetResolutionMeters,
    setTargetResolutionMeters,
    resamplingMethod,
    setResamplingMethod,
    strategy,
    setStrategy,
    isPreparing,
    status,
    preparedSingleAsset,
    preparedPair,
    error,
    warnings,
    blockingIssues,
    isReadyForAnalysis,
    showPreparedPreview,
    setShowPreparedPreview,
    startPreparation,
    cancelPreparation,
    reset,
  };
}
