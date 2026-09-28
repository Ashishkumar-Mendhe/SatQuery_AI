"use client";

import { useCallback, useEffect, useState } from "react";
import { AccessibleDialog } from "@/components/workspace/accessible-dialog";
import { AssistantPanel } from "@/components/workspace/assistant-panel";
import { ReportExportDialog } from "@/components/workspace/report-export-dialog";
import { ResetWorkspaceDialog } from "@/components/workspace/reset-workspace-dialog";
import { SceneContainer } from "@/components/workspace/scene-container";
import { WorkflowReadinessBanner } from "@/components/workspace/workflow-readiness-banner";
import { WorkspaceErrorBoundary } from "@/components/workspace/workspace-error-boundary";
import { WorkspaceSidebar } from "@/components/workspace/workspace-sidebar";
import { WorkspaceTopbar } from "@/components/workspace/workspace-topbar";
import { selectedAoiToContract } from "@/lib/aoi";
import type { ChangeDetectionResult } from "@/lib/change-contracts";
import type { FusionResult } from "@/lib/fusion-contracts";
import {
  type CatalogueSceneContext,
  catalogueSceneKey,
  createCatalogueSceneSelection,
  type SelectedCatalogueScene,
} from "@/lib/scene-selection";
import { useQueryAssistant } from "@/lib/use-query-assistant";
import { useReportExport } from "@/lib/use-report-export";
import { useVisualQA } from "@/lib/use-visual-qa";
import type { VisualOperation } from "@/lib/visual-contracts";
import { useAoiDraft } from "@/lib/use-aoi-draft";
import { useSceneSelectionDraft } from "@/lib/use-scene-selection-draft";
import { useWorkspaceDraft } from "@/lib/use-workspace-draft";
import { deriveWorkflowState } from "@/lib/workspace-workflow";

export function WorkspaceShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const [assistantVisible, setAssistantVisible] = useState(true);
  const [guideOpen, setGuideOpen] = useState(false);
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [sceneContext, setSceneContext] = useState<CatalogueSceneContext | null>(null);
  const [hoveredSceneKey, setHoveredSceneKey] = useState<string | null>(null);
  const [queryType, setQueryType] = useState<"evidence" | "visual">("visual");
  const [visualOperation, setVisualOperation] = useState<VisualOperation>("describe");
  const [changeResult, setChangeResult] = useState<ChangeDetectionResult | null>(null);
  const [fusionResult, setFusionResult] = useState<FusionResult | null>(null);
  const [isRasterPrepared, setIsRasterPrepared] = useState(false);
  const [hasSelectedPair, setHasSelectedPair] = useState(false);

  const {
    aoi,
    setAoi,
    clearAoi,
    persistenceState: aoiPersistenceState,
    persistenceMessage: aoiPersistenceMessage,
  } = useAoiDraft();

  const handleRestoreAoi = useCallback(
    (restoredAoi: Parameters<typeof setAoi>[0]) => {
      setAoi(restoredAoi);
    },
    [setAoi],
  );

  const {
    analysisMode,
    questionDraft,
    dateRange,
    beforeWindow,
    afterWindow,
    pairingPreferences,
    sceneFilters,
    activeTab,
    isRestored,
    setAnalysisMode,
    setQuestionDraft,
    setDateRange,
    setBeforeWindow,
    setAfterWindow,
    setPairingPreferences,
    setSceneFilters,
    setActiveTab,
    dismissRestoredNotice,
    resetWorkspace,
  } = useWorkspaceDraft({
    selectedAoi: aoi,
    onRestoreAoi: handleRestoreAoi,
  });

  const {
    selectedScene,
    selectScene,
    clearScene,
    refreshScene,
    persistenceState: scenePersistenceState,
    persistenceMessage: sceneSelectionMessage,
  } = useSceneSelectionDraft();

  const queryAssistant = useQueryAssistant({
    aoi: aoi ? selectedAoiToContract(aoi) : null,
    activeMode: analysisMode,
    activeChangeResultId: changeResult?.result_id ?? null,
    activeFusionResultId: fusionResult?.result_id ?? null,
    selectedSceneIds: selectedScene ? [selectedScene.scene.provider_asset_id] : [],
    locationLabel: aoi?.name ?? null,
  });

  const visualQA = useVisualQA({
    aoi: aoi ? selectedAoiToContract(aoi) : null,
    selectedAssetIds: selectedScene?.scene?.provider_asset_id
      ? [selectedScene.scene.provider_asset_id]
      : [],
    selectedSceneIds: selectedScene ? [selectedScene.scene.provider_asset_id] : [],
    locationLabel: aoi?.name ?? null,
  });

  const reportExport = useReportExport();

  const exportContext = {
    resultId:
      changeResult?.result_id ||
      fusionResult?.result_id ||
      queryAssistant.currentAnswer?.answer_id ||
      visualQA.currentResponse?.answer_id ||
      "res-current",
    workspaceId: "ws-default",
    title: questionDraft.trim() || "SatQuery Analysis Dossier",
    query: questionDraft.trim() || null,
    aoi: aoi ? selectedAoiToContract(aoi) : null,
    dateRange,
    scenes: selectedScene ? [selectedScene.scene] : [],
    answer: queryAssistant.currentAnswer,
    visualResponse: visualQA.currentResponse,
    changeResult,
  };

  const workflowState = deriveWorkflowState({
    mode: analysisMode,
    selectedAoi: aoi,
    dateRange,
    beforeWindow,
    afterWindow,
    hasSelectedScene: Boolean(selectedScene),
    hasSelectedPair,
    isRasterPrepared,
    hasAnalysisResult: Boolean(changeResult || fusionResult),
    hasAnswer: Boolean(queryAssistant.currentAnswer || visualQA.currentResponse),
    questionDraft,
  });

  const handleWorkflowAction = useCallback(
    (actionType: string) => {
      if (actionType === "export_report") {
        reportExport.openDialog();
      } else if (actionType === "ask_question") {
        setAssistantVisible(true);
        setActiveTab("answer");
      }
    },
    [reportExport, setActiveTab],
  );

  const closeGuide = useCallback(() => setGuideOpen(false), []);

  const invalidateScenesForAoi = useCallback(() => {
    setSceneContext((current) => (current ? { ...current, isCurrent: false } : null));
    setHoveredSceneKey(null);
    clearScene("AOI changed. Previous footprints are stale; search this area to select a scene.");
  }, [clearScene]);

  const handleSceneContextChange = useCallback((context: CatalogueSceneContext | null) => {
    setSceneContext(context);
  }, []);

  const handleSelectScene = useCallback(
    (scene: SelectedCatalogueScene) => {
      selectScene(scene);
    },
    [selectScene],
  );

  const handleClearScene = useCallback(
    (message?: string) => {
      clearScene(message);
      setHoveredSceneKey(null);
    },
    [clearScene],
  );

  const handleResetConfirmed = useCallback(() => {
    invalidateScenesForAoi();
    clearAoi();
    resetWorkspace();
  }, [clearAoi, invalidateScenesForAoi, resetWorkspace]);

  useEffect(() => {
    if (
      hoveredSceneKey &&
      !sceneContext?.scenes.some((scene) => catalogueSceneKey(scene) === hoveredSceneKey)
    ) {
      setHoveredSceneKey(null);
    }
    if (!selectedScene || !sceneContext?.isCurrent) return;
    const retained = sceneContext.scenes.find(
      (scene) => catalogueSceneKey(scene) === selectedScene.key,
    );
    if (!retained || sceneContext.fingerprint !== selectedScene.queryFingerprint) {
      clearScene(
        "Scene selection cleared because it is not present in the current search results.",
      );
    } else if (retained !== selectedScene.scene) {
      selectScene(
        createCatalogueSceneSelection(
          retained,
          selectedScene.queryFingerprint,
          selectedScene.query,
        ),
      );
    }
  }, [clearScene, hoveredSceneKey, sceneContext, selectScene, selectedScene]);

  useEffect(() => {
    if (!selectedScene || aoiPersistenceState === "loading") return;
    if (!aoi || JSON.stringify(aoi.feature.geometry) !== JSON.stringify(selectedScene.query.aoi)) {
      handleClearScene(
        "Saved scene selection cleared because it belongs to a different or unavailable AOI.",
      );
    }
  }, [aoi, aoiPersistenceState, handleClearScene, selectedScene]);

  useEffect(() => {
    if (window.matchMedia?.("(max-width: 760px)").matches) setAssistantVisible(false);
  }, []);

  return (
    <WorkspaceErrorBoundary>
      <div
        className={`workspace-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""} ${assistantVisible ? "assistant-visible" : "assistant-hidden"}`}
      >
        <WorkspaceTopbar
          assistantVisible={assistantVisible}
          dataOrigin={selectedScene?.scene?.provider?.id === "mock" ? "mock" : "real"}
          onOpenNavigation={() => setMobileNavigationOpen(true)}
          onToggleAssistant={() => setAssistantVisible((current) => !current)}
          onOpenHelp={() => setGuideOpen(true)}
          onResetWorkspace={() => setResetDialogOpen(true)}
        />
        <WorkspaceSidebar
          collapsed={sidebarCollapsed}
          mobileOpen={mobileNavigationOpen}
          onToggleCollapse={() => setSidebarCollapsed((current) => !current)}
          onCloseMobile={() => setMobileNavigationOpen(false)}
        />
        {mobileNavigationOpen ? (
          <button
            className="workspace-backdrop navigation-backdrop"
            type="button"
            aria-label="Close workspace navigation"
            onClick={() => setMobileNavigationOpen(false)}
          />
        ) : null}

        <div className="workspace-main-column">
          {isRestored ? (
            <div className="restored-draft-banner" role="status" aria-live="polite">
              <div className="restored-draft-content">
                <span>Your previous workspace draft was restored from this browser.</span>
                <div className="restored-draft-actions">
                  <button
                    type="button"
                    className="restored-draft-btn reset"
                    onClick={handleResetConfirmed}
                  >
                    Start fresh
                  </button>
                  <button
                    type="button"
                    className="restored-draft-btn dismiss"
                    onClick={dismissRestoredNotice}
                  >
                    Keep draft
                  </button>
                </div>
              </div>
            </div>
          ) : null}

          <WorkflowReadinessBanner
            workflowState={workflowState}
            onTriggerAction={handleWorkflowAction}
          />

          <SceneContainer
            selectedAoi={aoi}
            onSelectAoi={(nextAoi) => {
              invalidateScenesForAoi();
              setAoi(nextAoi);
            }}
            onClearAoi={() => {
              invalidateScenesForAoi();
              clearAoi();
            }}
            persistenceMessage={aoiPersistenceMessage}
            mode={analysisMode}
            onSelectMode={setAnalysisMode}
            dateRange={dateRange}
            onDateRangeChange={setDateRange}
            beforeWindow={beforeWindow}
            onBeforeWindowChange={setBeforeWindow}
            afterWindow={afterWindow}
            onAfterWindowChange={setAfterWindow}
            pairingPreferences={pairingPreferences}
            onPairingPreferencesChange={setPairingPreferences}
            sceneFilters={sceneFilters}
            onSceneFiltersChange={setSceneFilters}
            sceneContext={sceneContext}
            selectedScene={selectedScene}
            hoveredSceneKey={hoveredSceneKey}
            sceneSelectionMessage={sceneSelectionMessage}
            scenePersistenceState={scenePersistenceState}
            onSceneContextChange={handleSceneContextChange}
            onHoverScene={setHoveredSceneKey}
            onSelectScene={handleSelectScene}
            onClearScene={handleClearScene}
            onRefreshScene={refreshScene}
            onChangeResult={setChangeResult}
            onFusionResult={setFusionResult}
            onRasterPrepared={setIsRasterPrepared}
            onPairSelected={setHasSelectedPair}
          />
        </div>

        {assistantVisible ? (
          <button
            className="workspace-backdrop assistant-backdrop"
            type="button"
            aria-label="Hide assistant panel"
            onClick={() => setAssistantVisible(false)}
          />
        ) : null}

        {assistantVisible ? (
          <div id="assistant-region" className="assistant-region">
            <AssistantPanel
              visible={assistantVisible}
              draft={questionDraft}
              mode={analysisMode}
              activeTab={activeTab}
              onDraftChange={setQuestionDraft}
              onTabChange={setActiveTab}
              onClose={() => setAssistantVisible(false)}
              queryType={queryType}
              onQueryTypeChange={setQueryType}
              visualOperation={visualOperation}
              onVisualOperationChange={setVisualOperation}
              selectedImageCount={selectedScene ? 1 : 0}
              isSubmitting={
                queryType === "visual" ? visualQA.isSubmitting : queryAssistant.isSubmitting
              }
              loadingStage={queryType === "visual" ? null : queryAssistant.loadingStage}
              answer={queryAssistant.currentAnswer}
              visualResponse={visualQA.currentResponse}
              error={queryType === "visual" ? visualQA.error : queryAssistant.error}
              isContextStale={
                queryType === "visual" ? visualQA.isContextStale : queryAssistant.isContextStale
              }
              selectedHighlightId={queryAssistant.highlightedRegionId}
              selectedObservationId={visualQA.highlightedObservationId}
              onSelectObservation={visualQA.selectObservation}
              onSubmit={() => {
                if (queryType === "visual") {
                  visualQA.askQuestion(questionDraft).then((resp) => {
                    if (resp) {
                      setActiveTab("answer");
                    }
                  });
                } else {
                  queryAssistant.askQuestion(questionDraft).then((ans) => {
                    if (ans) {
                      setActiveTab("answer");
                    }
                  });
                }
              }}
              onCancel={queryType === "visual" ? visualQA.cancelQuery : queryAssistant.cancelQuery}
              onRetry={queryType === "visual" ? visualQA.retryQuery : queryAssistant.retryQuery}
              onClearAnswer={() => {
                visualQA.clearResponse();
                queryAssistant.clearAnswer();
              }}
              onSelectHighlight={queryAssistant.selectHighlight}
              onExecuteAction={(act) => {
                if (act.workflow_target === "change") {
                  setAnalysisMode("change_detection");
                } else if (act.workflow_target === "spectral") {
                  setAnalysisMode("spectral_analysis");
                } else if (act.workflow_target === "fusion") {
                  setAnalysisMode("multimodal_analysis");
                }
              }}
              onExportReport={reportExport.openDialog}
            />
          </div>
        ) : null}

        <AccessibleDialog
          open={guideOpen}
          onClose={closeGuide}
          title="What is available here?"
          description="Explore a real basemap and create one local area of interest while analytical services remain deliberately unavailable."
        >
          <ul className="dialog-list">
            <li>
              <strong>Available:</strong> map navigation, coordinate and place search, AOI drawing,
              editing, browser draft persistence, GeoJSON import/export, live catalogue imagery
              discovery, scene footprints and metadata selection, georeferenced natural-colour
              imagery display, visual comparison, actual-acquisition timeline, browser-local viewer
              restoration, question drafts, and service checks.
            </li>
            <li>
              <strong>Not available:</strong> displayed imagery as an analytical asset, viewer
              display server-saved AOIs/viewer state, analysis, stored history, missions, or
              reports.
            </li>
            <li>
              <strong>Service status:</strong> backend readiness is separate from analysis
              availability and never creates a result.
            </li>
          </ul>
        </AccessibleDialog>

        <ResetWorkspaceDialog
          open={resetDialogOpen}
          onClose={() => setResetDialogOpen(false)}
          onConfirm={handleResetConfirmed}
        />

        <ReportExportDialog exportState={reportExport} context={exportContext} />
      </div>
    </WorkspaceErrorBoundary>
  );
}
