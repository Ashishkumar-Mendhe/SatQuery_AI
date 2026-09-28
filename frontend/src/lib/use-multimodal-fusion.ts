import { useCallback, useEffect, useRef, useState } from "react";

import type { AOIGeometry } from "./analysis-contracts";
import {
  FusionClientError,
  analyzeFusion,
  getFusionCapabilities,
  getFusionOverlayUrl,
} from "./fusion-client";
import {
  DEFAULT_SAR_THRESHOLD_CONFIG,
  type FusionCapabilitiesResponse,
  type FusionRegion,
  type FusionResult,
  type SARThresholdConfig,
} from "./fusion-contracts";

export interface UseMultimodalFusionProps {
  initialOpticalResultId?: string | null;
  initialSarBeforeAssetId?: string | null;
  initialSarAfterAssetId?: string | null;
  aoi?: AOIGeometry | null;
}

export interface UseMultimodalFusionReturn {
  opticalResultId: string | null;
  setOpticalResultId: (id: string | null) => void;
  sarBeforeAssetId: string | null;
  setSarBeforeAssetId: (id: string | null) => void;
  sarAfterAssetId: string | null;
  setSarAfterAssetId: (id: string | null) => void;
  temporalToleranceDays: number;
  setTemporalToleranceDays: (days: number) => void;
  sarThresholdConfig: SARThresholdConfig;
  setSarThresholdConfig: (config: SARThresholdConfig) => void;
  eventTimestamp: string | null;
  setEventTimestamp: (timestamp: string | null) => void;
  allowPartial: boolean;
  setAllowPartial: (allow: boolean) => void;
  capabilities: FusionCapabilitiesResponse | null;
  isExecuting: boolean;
  result: FusionResult | null;
  error: string | null;
  selectedRegionId: string | null;
  selectedRegion: FusionRegion | null;
  selectRegion: (regionId: string | null) => void;
  overlayVisible: boolean;
  setOverlayVisible: (visible: boolean) => void;
  overlayOpacity: number;
  setOverlayOpacity: (opacity: number) => void;
  overlayUrl: string | null;
  executeFusion: (aoiOverride?: AOIGeometry) => Promise<FusionResult | null>;
  clearResult: () => void;
  canExecute: boolean;
}

export function useMultimodalFusion({
  initialOpticalResultId = null,
  initialSarBeforeAssetId = null,
  initialSarAfterAssetId = null,
  aoi = null,
}: UseMultimodalFusionProps = {}): UseMultimodalFusionReturn {
  const [opticalResultId, setOpticalResultId] = useState<string | null>(initialOpticalResultId);
  const [sarBeforeAssetId, setSarBeforeAssetId] = useState<string | null>(initialSarBeforeAssetId);
  const [sarAfterAssetId, setSarAfterAssetId] = useState<string | null>(initialSarAfterAssetId);
  const [temporalToleranceDays, setTemporalToleranceDays] = useState<number>(30.0);
  const [sarThresholdConfig, setSarThresholdConfig] = useState<SARThresholdConfig>(
    DEFAULT_SAR_THRESHOLD_CONFIG,
  );
  const [eventTimestamp, setEventTimestamp] = useState<string | null>(null);
  const [allowPartial, setAllowPartial] = useState<boolean>(true);

  const [capabilities, setCapabilities] = useState<FusionCapabilitiesResponse | null>(null);
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [result, setResult] = useState<FusionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);

  const [overlayVisible, setOverlayVisible] = useState<boolean>(true);
  const [overlayOpacity, setOverlayOpacity] = useState<number>(0.85);

  const abortControllerRef = useRef<AbortController | null>(null);
  const lastAoiRef = useRef<AOIGeometry | null>(aoi);

  // Fetch capabilities on mount
  useEffect(() => {
    let isMounted = true;
    getFusionCapabilities()
      .then((caps) => {
        if (isMounted) setCapabilities(caps);
      })
      .catch(() => {
        // Silently tolerate if service capabilities unavailable in offline tests
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Automatic stale result invalidation on AOI or input change
  useEffect(() => {
    if (result && lastAoiRef.current !== aoi) {
      setResult(null);
      setSelectedRegionId(null);
    }
    lastAoiRef.current = aoi;
  }, [aoi, result]);

  const clearResult = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setResult(null);
    setError(null);
    setSelectedRegionId(null);
    setIsExecuting(false);
  }, []);

  const canExecute = Boolean(
    (opticalResultId || (sarBeforeAssetId && sarAfterAssetId)) &&
      (aoi || lastAoiRef.current) &&
      !isExecuting,
  );

  const executeFusion = useCallback(
    async (aoiOverride?: AOIGeometry): Promise<FusionResult | null> => {
      const activeAoi = aoiOverride || aoi || lastAoiRef.current;
      if (!activeAoi) {
        setError("An active AOI geometry is required for multimodal evidence fusion.");
        return null;
      }
      if (!opticalResultId && (!sarBeforeAssetId || !sarAfterAssetId)) {
        setError("Select an optical change result or a prepared SAR pair to run fusion.");
        return null;
      }

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setIsExecuting(true);
      setError(null);

      try {
        const fusionRes = await analyzeFusion(
          {
            optical_change_result_id: opticalResultId,
            sar_before_asset_id: sarBeforeAssetId,
            sar_after_asset_id: sarAfterAssetId,
            aoi: activeAoi,
            rule_id: "co_observed_response_change",
            temporal_tolerance_days: temporalToleranceDays,
            sar_threshold_config: sarThresholdConfig,
            event_timestamp: eventTimestamp,
            allow_partial: allowPartial,
          },
          controller.signal,
        );

        setResult(fusionRes);
        setSelectedRegionId(null);
        return fusionRes;
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return null;
        }
        const message =
          err instanceof FusionClientError ? err.message : "Failed to execute multimodal fusion.";
        setError(message);
        return null;
      } finally {
        setIsExecuting(false);
      }
    },
    [
      aoi,
      opticalResultId,
      sarBeforeAssetId,
      sarAfterAssetId,
      temporalToleranceDays,
      sarThresholdConfig,
      eventTimestamp,
      allowPartial,
    ],
  );

  const selectedRegion = result?.regions.find((r) => r.id === selectedRegionId) || null;

  const overlayUrl = result?.result_id ? getFusionOverlayUrl(result.result_id) : null;

  return {
    opticalResultId,
    setOpticalResultId,
    sarBeforeAssetId,
    setSarBeforeAssetId,
    sarAfterAssetId,
    setSarAfterAssetId,
    temporalToleranceDays,
    setTemporalToleranceDays,
    sarThresholdConfig,
    setSarThresholdConfig,
    eventTimestamp,
    setEventTimestamp,
    allowPartial,
    setAllowPartial,
    capabilities,
    isExecuting,
    result,
    error,
    selectedRegionId,
    selectedRegion,
    selectRegion: setSelectedRegionId,
    overlayVisible,
    setOverlayVisible,
    overlayOpacity,
    setOverlayOpacity,
    overlayUrl,
    executeFusion,
    clearResult,
    canExecute,
  };
}
