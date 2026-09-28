"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { AnalysisMode } from "./analysis-contracts";
import type { SelectedAoi } from "./aoi";
import type { PairingPreferences } from "./temporal-contracts";
import {
  clearWorkspaceDraftFromStorage,
  parseWorkspaceDraft,
  type ResultTab,
  type SceneFiltersDraft,
  saveWorkspaceDraftToStorage,
  serializeWorkspaceDraft,
  WORKSPACE_DRAFT_STORAGE_KEY,
} from "./workspace-draft-storage";

export type WorkspacePersistenceState = "loading" | "empty" | "saved" | "restored" | "unavailable";

export interface WorkspaceDraftState {
  readonly analysisMode: AnalysisMode;
  readonly questionDraft: string;
  readonly dateRange: { start_date: string; end_date: string } | null;
  readonly beforeWindow: { start_date: string; end_date: string; label?: string } | null;
  readonly afterWindow: { start_date: string; end_date: string; label?: string } | null;
  readonly selectedBeforeSceneId: string | null;
  readonly selectedAfterSceneId: string | null;
  readonly pairingPreferences: PairingPreferences | null;
  readonly sceneFilters: SceneFiltersDraft;
  readonly activeTab: ResultTab;
  readonly persistenceState: WorkspacePersistenceState;
  readonly persistenceMessage: string;
  readonly isRestored: boolean;
  readonly savedAt: string | null;
}

export interface UseWorkspaceDraftOptions {
  readonly selectedAoi: SelectedAoi | null;
  readonly onRestoreAoi?: (aoi: SelectedAoi) => void;
}

export function useWorkspaceDraft(options: UseWorkspaceDraftOptions) {
  const { selectedAoi, onRestoreAoi } = options;
  const [analysisMode, setAnalysisModeState] = useState<AnalysisMode>("visual_question_answering");
  const [questionDraft, setQuestionDraftState] = useState<string>("");
  const [dateRange, setDateRangeState] = useState<{ start_date: string; end_date: string } | null>(
    null,
  );
  const [beforeWindow, setBeforeWindowState] = useState<{
    start_date: string;
    end_date: string;
    label?: string;
  } | null>(null);
  const [afterWindow, setAfterWindowState] = useState<{
    start_date: string;
    end_date: string;
    label?: string;
  } | null>(null);
  const [selectedBeforeSceneId, setSelectedBeforeSceneIdState] = useState<string | null>(null);
  const [selectedAfterSceneId, setSelectedAfterSceneIdState] = useState<string | null>(null);
  const [pairingPreferences, setPairingPreferencesState] = useState<PairingPreferences | null>(
    null,
  );

  const [sceneFilters, setSceneFiltersState] = useState<SceneFiltersDraft>({
    maxCloudCover: 20,
    sensorType: "optical",
    limit: 12,
  });
  const [activeTab, setActiveTabState] = useState<ResultTab>("answer");
  const [persistenceState, setPersistenceState] = useState<WorkspacePersistenceState>("loading");
  const [persistenceMessage, setPersistenceMessage] = useState(
    "Checking this browser for a saved workspace draft…",
  );
  const [isRestored, setIsRestored] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const initialHydrationComplete = useRef(false);
  const saveTimeoutRef = useRef<number | null>(null);

  // Initial restoration on mount
  useEffect(() => {
    try {
      if (typeof window === "undefined" || !window.localStorage) {
        setPersistenceState("unavailable");
        setPersistenceMessage("Browser storage is unavailable. Drafts will remain in this tab.");
        initialHydrationComplete.current = true;
        return;
      }

      const storedRaw = window.localStorage.getItem(WORKSPACE_DRAFT_STORAGE_KEY);
      if (!storedRaw) {
        setPersistenceState("empty");
        setPersistenceMessage("No workspace draft is saved in this browser.");
        initialHydrationComplete.current = true;
        return;
      }

      try {
        const restored = parseWorkspaceDraft(storedRaw);
        setAnalysisModeState(restored.analysisMode);
        setQuestionDraftState(restored.questionDraft);
        setDateRangeState(restored.dateRange);
        setBeforeWindowState(restored.beforeWindow);
        setAfterWindowState(restored.afterWindow);
        setSelectedBeforeSceneIdState(restored.selectedBeforeSceneId);
        setSelectedAfterSceneIdState(restored.selectedAfterSceneId);
        setPairingPreferencesState(restored.pairingPreferences);
        setSceneFiltersState(restored.sceneFilters);
        setActiveTabState(restored.activeTab);
        setSavedAt(restored.savedAt);
        setIsRestored(true);
        setPersistenceState("restored");
        setPersistenceMessage("Workspace draft restored from this browser.");

        if (restored.aoi && onRestoreAoi) {
          onRestoreAoi(restored.aoi);
        }
      } catch (parseError) {
        // Discard invalid / expired draft
        clearWorkspaceDraftFromStorage();
        setPersistenceState("empty");
        setPersistenceMessage(
          parseError instanceof Error
            ? `${parseError.message} Starting fresh workspace.`
            : "Saved draft was invalid. Starting fresh workspace.",
        );
      }
    } catch {
      setPersistenceState("unavailable");
      setPersistenceMessage("Browser storage is unavailable. Drafts will remain in this tab.");
    } finally {
      initialHydrationComplete.current = true;
    }
  }, [onRestoreAoi]);

  // Debounced auto-save effect
  useEffect(() => {
    if (!initialHydrationComplete.current) return;

    if (saveTimeoutRef.current) {
      window.clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = window.setTimeout(() => {
      const serialized = serializeWorkspaceDraft({
        analysisMode,
        questionDraft,
        aoi: selectedAoi,
        dateRange,
        beforeWindow,
        afterWindow,
        selectedBeforeSceneId,
        selectedAfterSceneId,
        pairingPreferences,
        sceneFilters,
        activeTab,
      });

      const res = saveWorkspaceDraftToStorage(serialized);
      if (res.success) {
        setPersistenceState("saved");
        setPersistenceMessage("All edits saved to browser draft.");
        setSavedAt(new Date().toISOString());
      } else {
        setPersistenceState("unavailable");
        setPersistenceMessage(res.error ?? "Failed to save draft.");
      }
    }, 250);

    return () => {
      if (saveTimeoutRef.current) {
        window.clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [
    analysisMode,
    questionDraft,
    selectedAoi,
    dateRange,
    beforeWindow,
    afterWindow,
    selectedBeforeSceneId,
    selectedAfterSceneId,
    pairingPreferences,
    sceneFilters,
    activeTab,
  ]);

  const setAnalysisMode = useCallback((mode: AnalysisMode) => {
    setAnalysisModeState(mode);
  }, []);

  const setQuestionDraft = useCallback((text: string) => {
    setQuestionDraftState(text);
  }, []);

  const setDateRange = useCallback((range: { start_date: string; end_date: string } | null) => {
    setDateRangeState(range);
  }, []);

  const setBeforeWindow = useCallback(
    (range: { start_date: string; end_date: string; label?: string } | null) => {
      setBeforeWindowState(range);
    },
    [],
  );

  const setAfterWindow = useCallback(
    (range: { start_date: string; end_date: string; label?: string } | null) => {
      setAfterWindowState(range);
    },
    [],
  );

  const setSelectedBeforeSceneId = useCallback((id: string | null) => {
    setSelectedBeforeSceneIdState(id);
  }, []);

  const setSelectedAfterSceneId = useCallback((id: string | null) => {
    setSelectedAfterSceneIdState(id);
  }, []);

  const setPairingPreferences = useCallback((prefs: PairingPreferences | null) => {
    setPairingPreferencesState(prefs);
  }, []);

  const setSceneFilters = useCallback((filters: SceneFiltersDraft) => {
    setSceneFiltersState(filters);
  }, []);

  const setActiveTab = useCallback((tab: ResultTab) => {
    setActiveTabState(tab);
  }, []);

  const dismissRestoredNotice = useCallback(() => {
    setIsRestored(false);
  }, []);

  const clearDraft = useCallback(() => {
    clearWorkspaceDraftFromStorage();
    setAnalysisModeState("visual_question_answering");
    setQuestionDraftState("");
    setDateRangeState(null);
    setBeforeWindowState(null);
    setAfterWindowState(null);
    setSelectedBeforeSceneIdState(null);
    setSelectedAfterSceneIdState(null);
    setPairingPreferencesState(null);
    setSceneFiltersState({
      maxCloudCover: 20,
      sensorType: "optical",
      limit: 12,
    });
    setActiveTabState("answer");
    setPersistenceState("empty");
    setPersistenceMessage("Workspace draft cleared.");
    setSavedAt(null);
    setIsRestored(false);
  }, []);

  const resetWorkspace = clearDraft;

  return {
    analysisMode,
    questionDraft,
    dateRange,
    beforeWindow,
    afterWindow,
    selectedBeforeSceneId,
    selectedAfterSceneId,
    pairingPreferences,
    sceneFilters,
    activeTab,
    persistenceState,
    persistenceMessage,
    isRestored,
    savedAt,
    setAnalysisMode,
    setQuestionDraft,
    setDateRange,
    setBeforeWindow,
    setAfterWindow,
    setSelectedBeforeSceneId,
    setSelectedAfterSceneId,
    setPairingPreferences,
    setSceneFilters,
    setActiveTab,
    dismissRestoredNotice,
    resetWorkspace,
    clearDraft,
  };
}
