"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { SatelliteScene } from "./analysis-contracts";
import type { SelectedAoi } from "./aoi";
import { selectedAoiToContract } from "./aoi";
import { searchTemporalCandidates, validateTemporalPair } from "./temporal-client";
import type {
  PairingPreferences,
  TemporalPairValidationResult,
  TemporalSceneCandidates,
} from "./temporal-contracts";
import type { SceneFiltersDraft } from "./workspace-draft-storage";

export interface UseTemporalPairingOptions {
  readonly selectedAoi: SelectedAoi | null;
  readonly beforeWindow: { start_date: string; end_date: string } | null;
  readonly afterWindow: { start_date: string; end_date: string } | null;
  readonly sceneFilters: SceneFiltersDraft;
  readonly preferences?: PairingPreferences | null;
}

export function useTemporalPairing(options: UseTemporalPairingOptions) {
  const { selectedAoi, beforeWindow, afterWindow, sceneFilters, preferences } = options;

  const [candidates, setCandidates] = useState<TemporalSceneCandidates | null>(null);
  const [searchState, setSearchState] = useState<"idle" | "searching" | "error">("idle");
  const [searchError, setSearchError] = useState<string | null>(null);

  const [selectedBeforeScene, setSelectedBeforeScene] = useState<SatelliteScene | null>(null);
  const [selectedAfterScene, setSelectedAfterScene] = useState<SatelliteScene | null>(null);

  const [validationResult, setValidationResult] = useState<TemporalPairValidationResult | null>(
    null,
  );
  const [validationState, setValidationState] = useState<"idle" | "validating" | "error">("idle");
  const [validationError, setValidationError] = useState<string | null>(null);

  const searchAbortControllerRef = useRef<AbortController | null>(null);
  const validationAbortControllerRef = useRef<AbortController | null>(null);
  const aoiKey = selectedAoi ? JSON.stringify(selectedAoi.feature.geometry) : null;
  const beforeKey = beforeWindow ? `${beforeWindow.start_date}:${beforeWindow.end_date}` : null;
  const afterKey = afterWindow ? `${afterWindow.start_date}:${afterWindow.end_date}` : null;

  const prevAoiKeyRef = useRef<string | null>(aoiKey);
  const prevBeforeKeyRef = useRef<string | null>(beforeKey);
  const prevAfterKeyRef = useRef<string | null>(afterKey);

  // Invalidate candidates & selections when AOI actually changes
  useEffect(() => {
    if (prevAoiKeyRef.current !== aoiKey) {
      prevAoiKeyRef.current = aoiKey;
      setCandidates(null);
      setSelectedBeforeScene(null);
      setSelectedAfterScene(null);
      setValidationResult(null);
      setSearchError(null);
      setValidationError(null);
    }
  }, [aoiKey]);

  // Invalidate when dates actually change
  useEffect(() => {
    if (prevBeforeKeyRef.current !== beforeKey) {
      prevBeforeKeyRef.current = beforeKey;
      setSelectedBeforeScene(null);
      setValidationResult(null);
    }
  }, [beforeKey]);

  useEffect(() => {
    if (prevAfterKeyRef.current !== afterKey) {
      prevAfterKeyRef.current = afterKey;
      setSelectedAfterScene(null);
      setValidationResult(null);
    }
  }, [afterKey]);

  // Candidate Search
  const searchCandidates = useCallback(async () => {
    if (!selectedAoi || !beforeWindow || !afterWindow) {
      return;
    }

    if (searchAbortControllerRef.current) {
      searchAbortControllerRef.current.abort();
    }
    const abortController = new AbortController();
    searchAbortControllerRef.current = abortController;

    setSearchState("searching");
    setSearchError(null);

    try {
      const aoiContract = selectedAoiToContract(selectedAoi);
      const res = await searchTemporalCandidates(
        {
          aoi: aoiContract,
          before_window: {
            start_date: beforeWindow.start_date,
            end_date: beforeWindow.end_date,
            label: "before",
          },
          after_window: {
            start_date: afterWindow.start_date,
            end_date: afterWindow.end_date,
            label: "after",
          },
          max_cloud_cover: sceneFilters.maxCloudCover,
          sensor_types: [sceneFilters.sensorType],
          limit_per_window: sceneFilters.limit,
          pairing_preferences: preferences ?? null,
        },
        abortController.signal,
      );

      if (!abortController.signal.aborted) {
        setCandidates(res);
        setSearchState("idle");

        // If a recommended pair was returned and no manual selection is active, auto-stage recommendation
        if (res.recommended_pair && !selectedBeforeScene && !selectedAfterScene) {
          const recB = res.before_scenes.find(
            (s) => s.id === res.recommended_pair?.before_scene_id,
          );
          const recA = res.after_scenes.find((s) => s.id === res.recommended_pair?.after_scene_id);
          if (recB && recA) {
            setSelectedBeforeScene(recB);
            setSelectedAfterScene(recA);
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      if (!abortController.signal.aborted) {
        setSearchState("error");
        setSearchError(err instanceof Error ? err.message : "Temporal scene discovery failed.");
      }
    }
  }, [
    selectedAoi,
    beforeWindow,
    afterWindow,
    sceneFilters,
    preferences,
    selectedBeforeScene,
    selectedAfterScene,
  ]);

  // Pair Validation Trigger
  const triggerValidation = useCallback(
    async (before: SatelliteScene, after: SatelliteScene) => {
      if (!selectedAoi) return;

      if (validationAbortControllerRef.current) {
        validationAbortControllerRef.current.abort();
      }
      const abortController = new AbortController();
      validationAbortControllerRef.current = abortController;

      setValidationState("validating");
      setValidationError(null);

      try {
        const aoiContract = selectedAoiToContract(selectedAoi);
        const res = await validateTemporalPair(
          {
            aoi: aoiContract,
            before_scene: before,
            after_scene: after,
            analysis_mode: "change_detection",
            pairing_preferences: preferences ?? null,
          },
          abortController.signal,
        );

        if (!abortController.signal.aborted) {
          setValidationResult(res);
          setValidationState("idle");
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        if (!abortController.signal.aborted) {
          setValidationState("error");
          setValidationError(err instanceof Error ? err.message : "Pair validation failed.");
        }
      }
    },
    [selectedAoi, preferences],
  );

  // Auto-validate whenever both scenes are selected
  useEffect(() => {
    if (selectedBeforeScene && selectedAfterScene) {
      triggerValidation(selectedBeforeScene, selectedAfterScene);
    } else {
      setValidationResult(null);
      setValidationState("idle");
    }
  }, [selectedBeforeScene, selectedAfterScene, triggerValidation]);

  const selectBeforeScene = useCallback((scene: SatelliteScene | null) => {
    setSelectedBeforeScene(scene);
  }, []);

  const selectAfterScene = useCallback((scene: SatelliteScene | null) => {
    setSelectedAfterScene(scene);
  }, []);

  const applyRecommendedPair = useCallback(() => {
    if (!candidates?.recommended_pair) return;
    const recB = candidates.before_scenes.find(
      (s) => s.id === candidates.recommended_pair?.before_scene_id,
    );
    const recA = candidates.after_scenes.find(
      (s) => s.id === candidates.recommended_pair?.after_scene_id,
    );
    if (recB && recA) {
      setSelectedBeforeScene(recB);
      setSelectedAfterScene(recA);
    }
  }, [candidates]);

  const clearSelection = useCallback(() => {
    setSelectedBeforeScene(null);
    setSelectedAfterScene(null);
    setValidationResult(null);
  }, []);

  return {
    candidates,
    searchState,
    searchError,
    selectedBeforeScene,
    selectedAfterScene,
    validationResult,
    validationState,
    validationError,
    searchCandidates,
    selectBeforeScene,
    selectAfterScene,
    applyRecommendedPair,
    clearSelection,
  };
}
