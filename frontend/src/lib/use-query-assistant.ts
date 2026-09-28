import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { AnalysisMode, AOIGeometry } from "./analysis-contracts";
import { QueryClientError, askQuery, getQueryCapabilities } from "./query-client";
import type {
  QueryAnswer,
  QueryCapabilitiesResponse,
  WorkspaceContextSnapshot,
} from "./query-contracts";

export interface UseQueryAssistantProps {
  aoi?: AOIGeometry | null;
  activeMode?: AnalysisMode | null;
  activeSpectralResultId?: string | null;
  activeChangeResultId?: string | null;
  activeFusionResultId?: string | null;
  selectedSceneIds?: string[];
  locationLabel?: string | null;
}

export interface UseQueryAssistantReturn {
  question: string;
  setQuestion: (q: string) => void;
  isSubmitting: boolean;
  loadingStage: string | null;
  currentAnswer: QueryAnswer | null;
  error: string | null;
  capabilities: QueryCapabilitiesResponse | null;
  highlightedRegionId: string | null;
  highlightedEvidenceId: string | null;
  selectHighlight: (regionId: string | null, evidenceId?: string | null) => void;
  askQuestion: (questionOverride?: string) => Promise<QueryAnswer | null>;
  cancelQuery: () => void;
  retryQuery: () => void;
  clearAnswer: () => void;
  isContextStale: boolean;
  contextSnapshot: WorkspaceContextSnapshot;
}

function computeContextFingerprint(
  aoi: AOIGeometry | null | undefined,
  sceneIds: string[],
  activeMode: AnalysisMode | null | undefined,
  spectralId: string | null | undefined,
  changeId: string | null | undefined,
  fusionId: string | null | undefined,
): string {
  const parts = [
    aoi ? JSON.stringify(aoi.coordinates) : "no-aoi",
    [...sceneIds].sort().join(","),
    activeMode || "none",
    spectralId || "none",
    changeId || "none",
    fusionId || "none",
  ];
  // Simple deterministic string hash for client-side comparison
  let hash = 0;
  const str = parts.join("|");
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash |= 0;
  }
  return `fp-${Math.abs(hash).toString(16)}`;
}

export function useQueryAssistant({
  aoi = null,
  activeMode = null,
  activeSpectralResultId = null,
  activeChangeResultId = null,
  activeFusionResultId = null,
  selectedSceneIds = [],
  locationLabel = null,
}: UseQueryAssistantProps = {}): UseQueryAssistantReturn {
  const [question, setQuestion] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [loadingStage, setLoadingStage] = useState<string | null>(null);
  const [currentAnswer, setCurrentAnswer] = useState<QueryAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [capabilities, setCapabilities] = useState<QueryCapabilitiesResponse | null>(null);
  const [highlightedRegionId, setHighlightedRegionId] = useState<string | null>(null);
  const [highlightedEvidenceId, setHighlightedEvidenceId] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const lastSubmittedQuestionRef = useRef<string>("");

  // Build reactive context snapshot
  const contextFingerprint = useMemo(
    () =>
      computeContextFingerprint(
        aoi,
        selectedSceneIds,
        activeMode,
        activeSpectralResultId,
        activeChangeResultId,
        activeFusionResultId,
      ),
    [
      aoi,
      selectedSceneIds,
      activeMode,
      activeSpectralResultId,
      activeChangeResultId,
      activeFusionResultId,
    ],
  );

  const contextSnapshot: WorkspaceContextSnapshot = useMemo(
    () => ({
      snapshot_id: `snap-${Date.now()}`,
      fingerprint: contextFingerprint,
      aoi_geometry: aoi,
      location_label: locationLabel,
      scene_ids: selectedSceneIds,
      active_mode: activeMode,
      active_spectral_result_id: activeSpectralResultId,
      active_change_result_id: activeChangeResultId,
      active_fusion_result_id: activeFusionResultId,
      created_at: new Date().toISOString(),
    }),
    [
      contextFingerprint,
      aoi,
      locationLabel,
      selectedSceneIds,
      activeMode,
      activeSpectralResultId,
      activeChangeResultId,
      activeFusionResultId,
    ],
  );

  // Detect if previous answer belonged to an older context
  const isContextStale = useMemo(() => {
    if (!currentAnswer) return false;
    return currentAnswer.context_fingerprint !== contextFingerprint;
  }, [currentAnswer, contextFingerprint]);

  // Load capabilities once on mount
  useEffect(() => {
    const controller = new AbortController();
    getQueryCapabilities(controller.signal)
      .then((caps) => setCapabilities(caps))
      .catch((err) => {
        if (!(err instanceof DOMException && err.name === "AbortError")) {
          // Non-fatal, engine will still work
          console.warn("Could not fetch query capabilities:", err);
        }
      });

    return () => {
      controller.abort();
    };
  }, []);

  const selectHighlight = useCallback((regionId: string | null, evidenceId?: string | null) => {
    setHighlightedRegionId(regionId);
    setHighlightedEvidenceId(evidenceId ?? null);
  }, []);

  const cancelQuery = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsSubmitting(false);
    setLoadingStage(null);
  }, []);

  const askQuestion = useCallback(
    async (questionOverride?: string): Promise<QueryAnswer | null> => {
      const q = (questionOverride ?? question).trim();
      if (q.length < 3) {
        setError("Please enter a question of at least 3 characters.");
        return null;
      }

      cancelQuery();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setIsSubmitting(true);
      setError(null);
      setLoadingStage("Evaluating context and routing intent...");
      lastSubmittedQuestionRef.current = q;

      try {
        setLoadingStage("Retrieving evidence and checking sufficiency...");
        const answer = await askQuery(
          {
            question: q,
            context_snapshot: contextSnapshot,
          },
          controller.signal,
        );

        setCurrentAnswer(answer);
        setIsSubmitting(false);
        setLoadingStage(null);
        abortControllerRef.current = null;
        return answer;
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return null;
        }
        setIsSubmitting(false);
        setLoadingStage(null);
        abortControllerRef.current = null;
        const msg =
          err instanceof QueryClientError
            ? err.message
            : "An unexpected error occurred while answering your question.";
        setError(msg);
        return null;
      }
    },
    [question, contextSnapshot, cancelQuery],
  );

  const retryQuery = useCallback(() => {
    if (lastSubmittedQuestionRef.current) {
      askQuestion(lastSubmittedQuestionRef.current);
    }
  }, [askQuestion]);

  const clearAnswer = useCallback(() => {
    setCurrentAnswer(null);
    setError(null);
    setHighlightedRegionId(null);
    setHighlightedEvidenceId(null);
  }, []);

  return {
    question,
    setQuestion,
    isSubmitting,
    loadingStage,
    currentAnswer,
    error,
    capabilities,
    highlightedRegionId,
    highlightedEvidenceId,
    selectHighlight,
    askQuestion,
    cancelQuery,
    retryQuery,
    clearAnswer,
    isContextStale,
    contextSnapshot,
  };
}
