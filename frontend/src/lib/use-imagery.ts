"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { SelectedAoi } from "./aoi";
import { selectedAoiToContract } from "./aoi";
import { requestImagery, requestTemporalImagery } from "./imagery-client";
import type {
  AlignmentStatus,
  ImageryAsset,
  ImageryProductType,
  TemporalImageryResponse,
  VisualizationPreset,
} from "./imagery-contracts";

export type ComparisonMode = "swipe" | "split" | "blend";

export interface UseImageryOptions {
  readonly selectedAoi?: SelectedAoi | null;
  readonly sceneId?: string | null;
  readonly beforeSceneId?: string | null;
  readonly afterSceneId?: string | null;
  readonly sensorType?: string | null;
}

export function getCompatiblePresets(sensorType?: string | null): VisualizationPreset[] {
  const isSar =
    sensorType?.toLowerCase().includes("sar") || sensorType?.toLowerCase().includes("radar");
  if (isSar) {
    return ["sar_grayscale", "sar_vv", "sar_vh"];
  }
  return ["true_color", "false_color", "vegetation", "water", "urban"];
}

export function useImagery(options: UseImageryOptions = {}) {
  const { selectedAoi, sceneId, beforeSceneId, afterSceneId, sensorType } = options;

  // Single Scene State
  const [activeAsset, setActiveAsset] = useState<ImageryAsset | null>(null);
  const [singleStatus, setSingleStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [singleError, setSingleError] = useState<string | null>(null);
  const [selectedPreset, setSelectedPreset] = useState<VisualizationPreset>(() => {
    const presets = getCompatiblePresets(sensorType);
    return presets[0] ?? "true_color";
  });
  const [productType, setProductType] = useState<ImageryProductType>("map_preview");
  const [opacity, setOpacity] = useState<number>(1.0);
  const [visible, setVisible] = useState<boolean>(true);

  // Multitemporal Comparison State
  const [temporalResponse, setTemporalResponse] = useState<TemporalImageryResponse | null>(null);
  const [temporalStatus, setTemporalStatus] = useState<"idle" | "loading" | "ready" | "error">(
    "idle",
  );
  const [temporalError, setTemporalError] = useState<string | null>(null);
  const [beforePreset, setBeforePreset] = useState<VisualizationPreset>("true_color");
  const [afterPreset, setAfterPreset] = useState<VisualizationPreset>("true_color");
  const [comparisonMode, setComparisonMode] = useState<ComparisonMode>("swipe");
  const [swipePosition, setSwipePosition] = useState<number>(50);
  const [blendOpacity, setBlendOpacity] = useState<number>(0.5);

  const singleAbortRef = useRef<AbortController | null>(null);
  const temporalAbortRef = useRef<AbortController | null>(null);
  const singleSeqRef = useRef<number>(0);
  const temporalSeqRef = useRef<number>(0);

  // Track dependency changes for automatic invalidation
  const aoiKey = selectedAoi ? JSON.stringify(selectedAoi.feature.geometry) : null;
  const prevAoiKeyRef = useRef<string | null>(aoiKey);
  const prevSceneIdRef = useRef<string | null>(sceneId ?? null);
  const prevBeforeIdRef = useRef<string | null>(beforeSceneId ?? null);
  const prevAfterIdRef = useRef<string | null>(afterSceneId ?? null);

  // Update default preset if sensor type changes
  useEffect(() => {
    const compatible = getCompatiblePresets(sensorType);
    if (!compatible.includes(selectedPreset)) {
      setSelectedPreset(compatible[0] ?? "true_color");
    }
  }, [sensorType, selectedPreset]);

  // Invalidate when AOI changes
  useEffect(() => {
    if (prevAoiKeyRef.current !== aoiKey) {
      prevAoiKeyRef.current = aoiKey;
      if (singleAbortRef.current) {
        singleAbortRef.current.abort();
        singleAbortRef.current = null;
      }
      if (temporalAbortRef.current) {
        temporalAbortRef.current.abort();
        temporalAbortRef.current = null;
      }
      setActiveAsset(null);
      setSingleStatus("idle");
      setSingleError(null);
      setTemporalResponse(null);
      setTemporalStatus("idle");
      setTemporalError(null);
    }
  }, [aoiKey]);

  // Invalidate single scene when sceneId changes
  useEffect(() => {
    if (prevSceneIdRef.current !== (sceneId ?? null)) {
      prevSceneIdRef.current = sceneId ?? null;
      if (singleAbortRef.current) {
        singleAbortRef.current.abort();
        singleAbortRef.current = null;
      }
      setActiveAsset(null);
      setSingleStatus("idle");
      setSingleError(null);
    }
  }, [sceneId]);

  // Invalidate temporal pair when before/after changes
  useEffect(() => {
    const curBefore = beforeSceneId ?? null;
    const curAfter = afterSceneId ?? null;
    if (prevBeforeIdRef.current !== curBefore || prevAfterIdRef.current !== curAfter) {
      prevBeforeIdRef.current = curBefore;
      prevAfterIdRef.current = curAfter;
      if (temporalAbortRef.current) {
        temporalAbortRef.current.abort();
        temporalAbortRef.current = null;
      }
      setTemporalResponse(null);
      setTemporalStatus("idle");
      setTemporalError(null);
    }
  }, [beforeSceneId, afterSceneId]);

  // Fetch Single Scene Imagery
  const fetchImagery = useCallback(
    async (
      targetSceneId: string,
      targetAoi: SelectedAoi,
      targetPreset?: VisualizationPreset,
      targetProductType?: ImageryProductType,
    ): Promise<ImageryAsset | null> => {
      if (singleAbortRef.current) {
        singleAbortRef.current.abort();
      }
      const controller = new AbortController();
      singleAbortRef.current = controller;
      const seq = ++singleSeqRef.current;

      setSingleStatus("loading");
      setSingleError(null);

      const chosenPreset = targetPreset ?? selectedPreset;
      const chosenProduct = targetProductType ?? productType;

      try {
        const aoiContract = selectedAoiToContract(targetAoi);
        const format = chosenProduct === "analysis_raster" ? "geotiff" : "png";

        const asset = await requestImagery(
          {
            scene_id: targetSceneId,
            aoi: aoiContract,
            product_type: chosenProduct,
            visualization_preset: chosenPreset,
            output_format: format,
            include_metadata: true,
          },
          controller.signal,
        );

        if (seq === singleSeqRef.current && !controller.signal.aborted) {
          setActiveAsset(asset);
          setSingleStatus("ready");
          return asset;
        }
        return null;
      } catch (err: unknown) {
        if (controller.signal.aborted || seq !== singleSeqRef.current) {
          return null;
        }
        const message = err instanceof Error ? err.message : "Failed to retrieve scene imagery.";
        setSingleError(message);
        setSingleStatus("error");
        return null;
      }
    },
    [productType, selectedPreset],
  );

  const clearImagery = useCallback(() => {
    if (singleAbortRef.current) {
      singleAbortRef.current.abort();
      singleAbortRef.current = null;
    }
    setActiveAsset(null);
    setSingleStatus("idle");
    setSingleError(null);
  }, []);

  // Fetch Multitemporal Pair Imagery
  const fetchTemporalImagery = useCallback(
    async (
      beforeId: string,
      afterId: string,
      targetAoi: SelectedAoi,
      targetBeforePreset?: VisualizationPreset,
      targetAfterPreset?: VisualizationPreset,
      targetProductType?: ImageryProductType,
    ): Promise<TemporalImageryResponse | null> => {
      if (temporalAbortRef.current) {
        temporalAbortRef.current.abort();
      }
      const controller = new AbortController();
      temporalAbortRef.current = controller;
      const seq = ++temporalSeqRef.current;

      setTemporalStatus("loading");
      setTemporalError(null);

      const bPreset = targetBeforePreset ?? beforePreset;
      const aPreset = targetAfterPreset ?? afterPreset;
      const chosenProduct = targetProductType ?? productType;

      try {
        const aoiContract = selectedAoiToContract(targetAoi);
        const format = chosenProduct === "analysis_raster" ? "geotiff" : "png";

        const response = await requestTemporalImagery(
          {
            before_scene_id: beforeId,
            after_scene_id: afterId,
            aoi: aoiContract,
            product_type: chosenProduct,
            before_preset: bPreset,
            after_preset: aPreset,
            output_format: format,
            align_outputs: true,
            include_metadata: true,
          },
          controller.signal,
        );

        if (seq === temporalSeqRef.current && !controller.signal.aborted) {
          setTemporalResponse(response);
          setTemporalStatus("ready");
          return response;
        }
        return null;
      } catch (err: unknown) {
        if (controller.signal.aborted || seq !== temporalSeqRef.current) {
          return null;
        }
        const message =
          err instanceof Error ? err.message : "Failed to retrieve multitemporal imagery pair.";
        setTemporalError(message);
        setTemporalStatus("error");
        return null;
      }
    },
    [afterPreset, beforePreset, productType],
  );

  const clearTemporalImagery = useCallback(() => {
    if (temporalAbortRef.current) {
      temporalAbortRef.current.abort();
      temporalAbortRef.current = null;
    }
    setTemporalResponse(null);
    setTemporalStatus("idle");
    setTemporalError(null);
  }, []);

  return {
    // Single Scene
    activeAsset,
    singleStatus,
    singleError,
    selectedPreset,
    productType,
    opacity,
    visible,
    fetchImagery,
    clearImagery,
    setSelectedPreset,
    setProductType,
    setOpacity,
    setVisible,

    // Multitemporal Comparison
    temporalResponse,
    temporalStatus,
    temporalError,
    beforePreset,
    afterPreset,
    comparisonMode,
    swipePosition,
    blendOpacity,
    fetchTemporalImagery,
    clearTemporalImagery,
    setBeforePreset,
    setAfterPreset,
    setComparisonMode,
    setSwipePosition,
    setBlendOpacity,
    alignmentStatus: (temporalResponse?.alignment_status ?? null) as AlignmentStatus | null,
  };
}
