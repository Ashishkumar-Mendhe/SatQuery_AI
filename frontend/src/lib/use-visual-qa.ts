import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { AOIGeometry } from "./analysis-contracts";
import type { WorkspaceContextSnapshot } from "./query-contracts";
import { askVisualQuery, getVisualCapabilities, VisualClientError } from "./visual-client";
import type {
  GroundedVisualRegion,
  VisualCapabilitiesResponse,
  VisualOperation,
  VisualQueryResponse,
} from "./visual-contracts";

export interface UseVisualQAProps {
  aoi?: AOIGeometry | null;
  selectedAssetIds?: string[];
  selectedSceneIds?: string[];
  locationLabel?: string | null;
}

export interface UseVisualQAReturn {
  question: string;
  setQuestion: (q: string) => void;
  operation: VisualOperation;
  setOperation: (op: VisualOperation) => void;
  isSubmitting: boolean;
  currentResponse: VisualQueryResponse | null;
  error: string | null;
  capabilities: VisualCapabilitiesResponse | null;
  highlightedObservationId: string | null;
  highlightedRegion: GroundedVisualRegion | null;
  selectObservation: (observationId: string | null) => void;
  askQuestion: (questionOverride?: string) => Promise<VisualQueryResponse | null>;
  cancelQuery: () => void;
  retryQuery: () => void;
  clearResponse: () => void;
  isContextStale: boolean;
  contextSnapshot: WorkspaceContextSnapshot;
}

function computeVisualFingerprint(aoi: AOIGeometry | null | undefined, assetIds: string[]): string {
  const parts = [aoi ? JSON.stringify(aoi.coordinates) : "no-aoi", [...assetIds].sort().join(",")];
  let hash = 0;
  const str = parts.join("|");
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash |= 0;
  }
  return `vfp-${Math.abs(hash).toString(16)}`;
}

export function useVisualQA({
  aoi = null,
  selectedAssetIds = [],
  selectedSceneIds = [],
  locationLabel = null,
}: UseVisualQAProps = {}): UseVisualQAReturn {
  const [question, setQuestion] = useState<string>("");
  const [operation, setOperation] = useState<VisualOperation>("describe");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [currentResponse, setCurrentResponse] = useState<VisualQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [capabilities, setCapabilities] = useState<VisualCapabilitiesResponse | null>(null);
  const [highlightedObservationId, setHighlightedObservationId] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const lastSubmittedQuestionRef = useRef<string>("");

  const contextFingerprint = useMemo(
    () => computeVisualFingerprint(aoi, selectedAssetIds),
    [aoi, selectedAssetIds],
  );

  const contextSnapshot = useMemo<WorkspaceContextSnapshot>(
    () => ({
      snapshot_id: `vsnap_${Math.random().toString(36).slice(2, 9)}`,
      fingerprint: contextFingerprint,
      aoi_geometry: aoi,
      location_label: locationLabel,
      scene_ids: selectedSceneIds,
    }),
    [contextFingerprint, aoi, locationLabel, selectedSceneIds],
  );

  const isContextStale = useMemo(() => {
    if (!currentResponse) return false;
    return currentResponse.context_fingerprint !== contextFingerprint;
  }, [currentResponse, contextFingerprint]);

  // Clear error on asset change
  useEffect(() => {
    if (selectedAssetIds.length > 0) {
      setError(null);
    }
  }, [selectedAssetIds]);

  // Load capabilities once on mount
  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    async function loadCaps() {
      try {
        const caps = await getVisualCapabilities(controller.signal);
        if (isMounted) {
          setCapabilities(caps);
        }
      } catch {
        // Non-blocking fallback
      }
    }

    void loadCaps();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, []);

  const selectObservation = useCallback((observationId: string | null) => {
    setHighlightedObservationId(observationId);
  }, []);

  const highlightedRegion = useMemo(() => {
    if (!currentResponse || !highlightedObservationId) return null;
    return (
      currentResponse.grounded_regions.find((r) => r.observation_id === highlightedObservationId) ||
      null
    );
  }, [currentResponse, highlightedObservationId]);

  const clearResponse = useCallback(() => {
    setCurrentResponse(null);
    setError(null);
    setHighlightedObservationId(null);
  }, []);

  const cancelQuery = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsSubmitting(false);
  }, []);

  const askQuestion = useCallback(
    async (questionOverride?: string): Promise<VisualQueryResponse | null> => {
      const q = (questionOverride ?? question).trim();
      if (!q) {
        setError("Please enter a question to analyze the image.");
        return null;
      }

      if (selectedAssetIds.length === 0) {
        setError("Please select at least 1 image asset before asking a visual question.");
        return null;
      }

      cancelQuery();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setIsSubmitting(true);
      setError(null);
      lastSubmittedQuestionRef.current = q;

      try {
        const resp = await askVisualQuery(
          {
            question: q,
            context_snapshot: contextSnapshot,
            selected_image_asset_ids: selectedAssetIds.slice(0, 2),
            operation,
          },
          controller.signal,
        );

        setCurrentResponse(resp);
        // Highlight first observation with bounding box if available
        const firstWithBox = resp.observations.find((o) => Boolean(o.canonical_box));
        if (firstWithBox) {
          setHighlightedObservationId(firstWithBox.observation_id);
        } else if (resp.observations.length > 0) {
          setHighlightedObservationId(resp.observations[0].observation_id);
        }

        return resp;
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return null;
        }
        const msg =
          err instanceof VisualClientError
            ? err.message
            : "Failed to obtain an answer for this image. Please try again.";
        setError(msg);
        return null;
      } finally {
        setIsSubmitting(false);
        abortControllerRef.current = null;
      }
    },
    [question, selectedAssetIds, operation, contextSnapshot, cancelQuery],
  );

  const retryQuery = useCallback(() => {
    if (lastSubmittedQuestionRef.current) {
      void askQuestion(lastSubmittedQuestionRef.current);
    }
  }, [askQuestion]);

  return {
    question,
    setQuestion,
    operation,
    setOperation,
    isSubmitting,
    currentResponse,
    error,
    capabilities,
    highlightedObservationId,
    highlightedRegion,
    selectObservation,
    askQuestion,
    cancelQuery,
    retryQuery,
    clearResponse,
    isContextStale,
    contextSnapshot,
  };
}
