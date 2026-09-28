"use client";

import { useCallback, useEffect, useState } from "react";
import { AccessibleDialog } from "@/components/workspace/accessible-dialog";
import {
  AssistantPanel,
  type AssistantSelectionAction,
} from "@/components/workspace/assistant-panel";
import type { ResultTab } from "@/components/workspace/results-tabs";
import { SceneContainer } from "@/components/workspace/scene-container";
import { WorkspaceSidebar } from "@/components/workspace/workspace-sidebar";
import { WorkspaceTopbar } from "@/components/workspace/workspace-topbar";
import type { InferenceGroundingOverlay } from "@/lib/inference-grounding-map-layer";
import type { ChangeResult } from "@/lib/change-client";
import type { OpticalSarResult, SarScene } from "@/lib/optical-sar-client";
import {
  type CatalogueSceneContext,
  catalogueSceneKey,
  createCatalogueSceneSelection,
  type SelectedCatalogueScene,
} from "@/lib/scene-selection";
import { useAoiDraft } from "@/lib/use-aoi-draft";
import { useSceneSelectionDraft } from "@/lib/use-scene-selection-draft";

export function WorkspaceShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const [assistantVisible, setAssistantVisible] = useState(true);
  const [guideOpen, setGuideOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [activeTab, setActiveTab] = useState<ResultTab>("answer");
  const [sceneContext, setSceneContext] = useState<CatalogueSceneContext | null>(null);
  const [hoveredSceneKey, setHoveredSceneKey] = useState<string | null>(null);
  const [inferenceGroundingOverlay, setInferenceGroundingOverlay] =
    useState<InferenceGroundingOverlay | null>(null);
  const [comparison, setComparison] = useState<{
    sceneA: SelectedCatalogueScene;
    sceneB: SelectedCatalogueScene;
  } | null>(null);
  const [sarSelection, setSarSelection] = useState<{
    scene: SarScene;
    polarization: string;
  } | null>(null);
  const [assistantAction, setAssistantAction] = useState<{
    id: number;
    kind: AssistantSelectionAction;
  } | null>(null);
  const [assistantChangeResult, setAssistantChangeResult] = useState<{
    id: number;
    result: ChangeResult;
  } | null>(null);
  const [assistantSarResult, setAssistantSarResult] = useState<{
    id: number;
    result: OpticalSarResult;
  } | null>(null);
  const {
    aoi,
    setAoi,
    clearAoi,
    persistenceState: aoiPersistenceState,
    persistenceMessage,
  } = useAoiDraft();
  const {
    selectedScene,
    selectScene,
    clearScene,
    refreshScene,
    persistenceState: scenePersistenceState,
    persistenceMessage: sceneSelectionMessage,
  } = useSceneSelectionDraft();
  const closeGuide = useCallback(() => setGuideOpen(false), []);
  const handleSarSelectionChange = useCallback(
    (scene: SarScene | null, polarization: string | null) => {
      setSarSelection(scene && polarization ? { scene, polarization } : null);
    },
    [],
  );

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
    <div
      className={`workspace-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""} ${assistantVisible ? "assistant-visible" : "assistant-hidden"}`}
    >
      <WorkspaceTopbar
        assistantVisible={assistantVisible}
        onOpenNavigation={() => setMobileNavigationOpen(true)}
        onToggleAssistant={() => setAssistantVisible((current) => !current)}
        onOpenHelp={() => setGuideOpen(true)}
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
        persistenceMessage={persistenceMessage}
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
        inferenceGroundingOverlay={
          inferenceGroundingOverlay?.sceneKey === selectedScene?.key
            ? inferenceGroundingOverlay
            : null
        }
        onComparisonChange={setComparison}
        onSarSelectionChange={handleSarSelectionChange}
        assistantAction={assistantAction}
        assistantChangeResult={assistantChangeResult}
        assistantSarResult={assistantSarResult}
      />
      {assistantVisible ? (
        <button
          className="workspace-backdrop assistant-backdrop"
          type="button"
          aria-label="Hide assistant panel"
          onClick={() => setAssistantVisible(false)}
        />
      ) : null}
      <div id="assistant-region" className="assistant-region">
        <AssistantPanel
          visible={assistantVisible}
          draft={draft}
          activeTab={activeTab}
          selectedAoi={aoi}
          selectedScene={selectedScene}
          comparison={comparison}
          sarSelection={sarSelection}
          onDraftChange={setDraft}
          onTabChange={setActiveTab}
          onClose={() => setAssistantVisible(false)}
          onGroundingOverlayChange={setInferenceGroundingOverlay}
          onSelectionAction={(kind) => setAssistantAction({ id: Date.now(), kind })}
          onOpenChangeResult={(result) => setAssistantChangeResult({ id: Date.now(), result })}
          onOpenOpticalSarResult={(result) => {
            setAssistantSarResult({ id: Date.now(), result });
            setAssistantAction({ id: Date.now(), kind: "sar" });
          }}
        />
      </div>
      <AccessibleDialog
        open={guideOpen}
        onClose={closeGuide}
        title="What is available here?"
        description="Explore imagery and ask the bounded GeoAgent to route supported imagery analyses while keeping interpretation separate from measured evidence."
      >
        <ul className="dialog-list">
          <li>
            <strong>Available:</strong> map navigation, coordinate and place search, AOI drawing,
            editing, browser draft persistence, GeoJSON import/export, live catalogue imagery
            discovery, scene footprints and metadata selection, georeferenced natural-colour imagery
            display, visual comparison, actual-acquisition timeline, browser-local viewer
            restoration, bounded single-image questions, captions, validated box grounding, two-date
            change, separate optical/SAR observations, conversation routing, question drafts, and
            service checks when the corresponding backend services are available.
          </li>
          <li>
            <strong>Not available:</strong> quantitative model measurements, unvalidated cause or
            land-cover claims, server-saved AOIs/viewer state, missions, or reports.
          </li>
          <li>
            <strong>Service status:</strong> backend readiness is separate from analysis
            availability and never creates a result.
          </li>
        </ul>
      </AccessibleDialog>
    </div>
  );
}
