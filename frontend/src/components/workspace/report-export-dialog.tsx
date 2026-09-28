"use client";

import { useState } from "react";
import { Icon } from "@/components/icon";
import { AccessibleDialog } from "@/components/workspace/accessible-dialog";
import type { ReportFormat } from "@/lib/analysis-contracts";
import type { ReportSection } from "@/lib/report-contracts";
import type { ExportReportContext, useReportExport } from "@/lib/use-report-export";

export interface ReportExportDialogProps {
  exportState: ReturnType<typeof useReportExport>;
  context: ExportReportContext;
}

const SECTION_LABELS: Record<ReportSection, { label: string; description: string }> = {
  summary: {
    label: "Executive Summary",
    description: "AOI geometry, query context, answer summary, and data origin.",
  },
  scenes: {
    label: "Satellite Scenes & Sensors",
    description: "Acquisition timestamps, platform info, cloud cover, and scene IDs.",
  },
  quantitative_findings: {
    label: "Quantitative Findings",
    description: "Measured change areas, explicit denominators, and index statistics.",
  },
  visual_evidence: {
    label: "Visual Evidence & Figures",
    description: "True-color imagery, spectral maps, and change difference overlays.",
  },
  ai_interpretation: {
    label: "AI Findings & Observations",
    description: "Verified claims and visual model predictions clearly disclaimed.",
  },
  confidence_limitations: {
    label: "Confidence & Caveats",
    description: "Quality breakdown, resolution limits, and analytical caveats.",
  },
  provenance_methods: {
    label: "Provenance & Methods",
    description: "Processing timestamps, pipeline versions, parameters, and algorithms.",
  },
};

export function ReportExportDialog({ exportState, context }: ReportExportDialogProps) {
  const {
    isOpen,
    closeDialog,
    title,
    setTitle,
    selectedFormats,
    toggleFormat,
    includedSections,
    toggleSection,
    isGenerating,
    generationStage,
    reportResponse,
    error,
    generateReport,
    downloadFile,
    reset,
  } = exportState;

  const [downloadingFormat, setDownloadingFormat] = useState<string | null>(null);

  const handleStartGeneration = async () => {
    await generateReport(context);
  };

  const handleDownload = async (fmt: ReportFormat) => {
    setDownloadingFormat(fmt);
    await downloadFile(fmt);
    setDownloadingFormat(null);
  };

  const isCompleted = reportResponse !== null && reportResponse.status === "completed";
  const isMock =
    context.snapshot?.is_mock_data ||
    context.answer?.data_origin === "mock" ||
    context.changeResult?.data_origin === "mock";

  const totalAoiKm2 = context.aoi?.area_km2 ?? null;
  const validCompKm2 =
    context.changeResult?.metrics.shared_valid_area_km2 ??
    (context.snapshot?.quantitative_summary?.valid_comparison_area_km2 as number | undefined) ??
    null;

  return (
    <AccessibleDialog
      open={isOpen}
      onClose={closeDialog}
      title="Export Evidence Dossier"
      description="Generate an immutable, verifiable PDF and JSON report from the current analysis snapshot."
    >
      <div className="report-export-container">
        {/* Origin Notice */}
        {isMock && (
          <div className="report-origin-banner mock-banner" role="alert">
            <Icon name="warning" width={16} height={16} />
            <span>
              <strong>Synthetic Demo Data:</strong> This export will be prominently labelled as
              synthetic/mock data and not a live satellite measurement.
            </span>
          </div>
        )}

        {/* Snapshot Context Card */}
        <div className="report-context-card">
          <div className="report-context-header">
            <span className="report-context-title">Target Analysis Context</span>
            {context.resultId && <span className="report-result-badge">{context.resultId}</span>}
          </div>
          <div className="report-context-grid">
            <div className="report-context-item">
              <span className="context-label">AOI Total Area</span>
              <span className="context-value">
                {totalAoiKm2 !== null ? `${totalAoiKm2.toFixed(2)} km²` : "Not defined"}
              </span>
            </div>
            <div className="report-context-item">
              <span className="context-label">Valid Comparison Area</span>
              <span className="context-value">
                {validCompKm2 !== null ? `${validCompKm2.toFixed(2)} km²` : "N/A"}
              </span>
            </div>
            <div className="report-context-item">
              <span className="context-label">Satellite Scenes</span>
              <span className="context-value">
                {context.scenes && context.scenes.length > 0
                  ? `${context.scenes.length} scene(s) paired`
                  : "Single Scene / AOI"}
              </span>
            </div>
            <div className="report-context-item">
              <span className="context-label">Analysis State</span>
              <span className="context-value">
                {context.changeResult
                  ? "Bi-temporal Change"
                  : context.answer
                    ? "Grounded QA"
                    : "Prepared Raster"}
              </span>
            </div>
          </div>
        </div>

        {/* Success View */}
        {isCompleted ? (
          <div className="report-success-panel" data-testid="report-success-panel">
            <div className="report-success-header">
              <Icon name="check" width={24} height={24} className="success-icon" />
              <div>
                <h4 className="success-title">Dossier Generated Successfully</h4>
                <p className="success-subtitle">
                  Snapshot committed with SHA-256 integrity hash. Ready for download.
                </p>
              </div>
            </div>

            {reportResponse.snapshot?.checksum_sha256 && (
              <div className="report-checksum-box">
                <span className="checksum-label">SHA-256 Digest:</span>
                <code className="checksum-hash">{reportResponse.snapshot.checksum_sha256}</code>
              </div>
            )}

            {(() => {
              const hasFormat = (fmt: ReportFormat): boolean => {
                if (!reportResponse) return false;
                if (Array.isArray(reportResponse.formats)) {
                  return reportResponse.formats.includes(fmt);
                }
                if (reportResponse.formats && typeof reportResponse.formats === "object") {
                  return fmt in reportResponse.formats;
                }
                if (reportResponse.format_statuses && fmt in reportResponse.format_statuses) {
                  return true;
                }
                return false;
              };

              return (
                <div className="report-download-actions">
                  {hasFormat("pdf") && (
                    <button
                      type="button"
                      className="btn btn-primary download-btn"
                      onClick={() => handleDownload("pdf" as ReportFormat)}
                      disabled={downloadingFormat !== null}
                      data-testid="download-pdf-button"
                    >
                      <Icon name="report" width={16} height={16} />
                      <span>
                        {downloadingFormat === "pdf" ? "Downloading..." : "Download PDF Report"}
                      </span>
                    </button>
                  )}

                  {hasFormat("json") && (
                    <button
                      type="button"
                      className="btn btn-secondary download-btn"
                      onClick={() => handleDownload("json" as ReportFormat)}
                      disabled={downloadingFormat !== null}
                      data-testid="download-json-button"
                    >
                      <Icon name="report" width={16} height={16} />
                      <span>
                        {downloadingFormat === "json" ? "Downloading..." : "Download JSON Snapshot"}
                      </span>
                    </button>
                  )}
                </div>
              );
            })()}

            <div className="report-success-footer">
              <button type="button" className="btn btn-tertiary" onClick={reset}>
                Generate Another Format / Change Settings
              </button>
            </div>
          </div>
        ) : (
          /* Configuration & Generation View */
          <div className="report-config-panel">
            {/* Title Input */}
            <div className="form-group">
              <label htmlFor="report-title-input" className="form-label">
                Report Title
              </label>
              <input
                id="report-title-input"
                type="text"
                className="form-input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Enter report title..."
                maxLength={150}
                disabled={isGenerating}
              />
            </div>

            {/* Export Formats */}
            <div className="form-group">
              <span className="form-label">Export Formats</span>
              <fieldset className="format-toggle-group" aria-label="Export formats">
                <button
                  type="button"
                  className={`format-toggle-chip ${selectedFormats.includes("pdf" as ReportFormat) ? "selected" : ""}`}
                  onClick={() => toggleFormat("pdf" as ReportFormat)}
                  disabled={isGenerating}
                  aria-pressed={selectedFormats.includes("pdf" as ReportFormat)}
                  data-testid="format-pdf-toggle"
                >
                  <Icon name="evidence" width={14} height={14} />
                  <span>PDF Document (A4 Print-Ready)</span>
                </button>
                <button
                  type="button"
                  className={`format-toggle-chip ${selectedFormats.includes("json" as ReportFormat) ? "selected" : ""}`}
                  onClick={() => toggleFormat("json" as ReportFormat)}
                  disabled={isGenerating}
                  aria-pressed={selectedFormats.includes("json" as ReportFormat)}
                  data-testid="format-json-toggle"
                >
                  <Icon name="activity" width={14} height={14} />
                  <span>JSON Snapshot (Portable Data)</span>
                </button>
              </fieldset>
            </div>

            {/* Included Sections */}
            <div className="form-group">
              <span className="form-label">Include Dossier Sections</span>
              <div className="sections-checklist">
                {(Object.keys(SECTION_LABELS) as ReportSection[]).map((sectionKey) => {
                  const info = SECTION_LABELS[sectionKey];
                  const isChecked = includedSections.includes(sectionKey);
                  return (
                    <label key={sectionKey} className="section-checkbox-label">
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleSection(sectionKey)}
                        disabled={isGenerating}
                      />
                      <div className="section-checkbox-text">
                        <span className="section-name">{info.label}</span>
                        <span className="section-desc">{info.description}</span>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="report-error-banner" role="alert">
                <Icon name="warning" width={16} height={16} />
                <div className="error-text">
                  <strong>Export Failed:</strong> {error}
                </div>
              </div>
            )}

            {/* Progress Stage */}
            {isGenerating && (
              <div className="report-progress-panel" role="status">
                <div className="progress-spinner" />
                <span className="progress-stage-text">
                  {generationStage || "Generating report..."}
                </span>
              </div>
            )}

            {/* Actions */}
            <div className="report-dialog-actions">
              <button
                type="button"
                className="btn btn-tertiary"
                onClick={closeDialog}
                disabled={isGenerating}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleStartGeneration}
                disabled={isGenerating || selectedFormats.length === 0}
                data-testid="generate-report-submit"
              >
                {isGenerating ? (
                  <span>Generating Dossier...</span>
                ) : (
                  <>
                    <Icon name="report" width={16} height={16} />
                    <span>Generate Dossier</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </AccessibleDialog>
  );
}
