# Product requirements document

## Status and authority

This document is the authority for **what** SatQuery AI must provide. All functionality is planned unless explicitly marked implemented; as of Phase 0, none of the product functionality is implemented. Technical realization belongs in `TRD.md`, interfaces in `API_CONTRACT.md`, and delivery status in `FEATURES.md` and `CURRENT_PHASE.md`.

## Problem and intended users

Remote-sensing users often move among catalogues, GIS tools, image-processing code, and narrative reporting to answer a spatial question. SatQuery AI should provide one inspectable workspace where a user can identify analytical imagery, ask a natural-language question, and receive a bounded answer connected to spatial evidence and provenance.

Primary users are geospatial analysts and remote-sensing researchers. Secondary users include planners, disaster-response staff, environmental teams, and other evidence-conscious decision makers. The product may help non-specialists interpret outputs, but it must not hide unsupported claims or imply expert-grade certainty.

## Goals and success evaluation

- Reduce the effort between locating imagery and obtaining a reviewable, reproducible answer.
- Keep imagery identity, processing method, spatial evidence, uncertainty, and limitations visible.
- Support single-image questions, before/after comparison, and compatible optical/SAR workflows through one product and one workspace.
- Fail honestly when data, credentials, tool capability, georeferencing, or evidence are insufficient.

Initial quantitative success measures are **targets pending measurement**, not achieved claims:

- At least 95% of completed supported analyses expose input asset identity, method, limitations, and evidence or an explicit reason evidence is unavailable.
- Zero known cases in acceptance testing where an unavailable provider or analysis tool produces fabricated output.
- At least 90% of representative supported tasks can be completed without leaving the workspace, measured after the corresponding features exist.
- Interactive UI actions should normally acknowledge input within 200 ms and API reads within 1 second excluding network and long-running processing; these are design targets to be revised from measured baselines.

Scientific/model accuracy thresholds are unresolved and must be set per validated task, dataset, sensor, and model before a capability can be described as validated.

## Core user journeys

1. **Inspect and ask:** the user selects a catalogued asset or uploads imagery, sees validated metadata, asks a question, watches an honest job state, and reviews the answer, supporting regions, method, provenance, confidence meaning, warnings, and trace summary.
2. **AOI discovery:** the user draws or supplies an area of interest (AOI), validates its geometry, searches configured catalogues by space/time and relevant quality fields, and selects an analytical asset rather than relying on the basemap.
3. **Before/after comparison:** the user selects two assets, confirms temporal order and compatibility, requests comparison, and receives findings constrained to valid aligned overlap with quality differences disclosed.
4. **Optical/SAR workflow:** the user supplies compatible optical and SAR assets for an explicitly supported method; the system checks sensor/acquisition metadata and preprocessing requirements before execution.
5. **Uncertainty and failure inspection:** the user can see missing evidence, unavailable values, unsupported questions, compatibility failures, partial failures, and actionable remediation without fabricated answers or progress.
6. **Revisit and export:** once history and reporting exist, the user reopens an owned analysis and exports a report that preserves provenance, evidence references, methods, units, assumptions, warnings, and generation time.

## Functional requirements and acceptance criteria

| Requirement | Planned behavior | Observable acceptance criteria |
|---|---|---|
| **PRD-AST-001 Asset intake and metadata** | Select a discovered asset or upload an allowed raster; expose source/provider, stable identity, acquisition time, sensor, bands, dimensions, resolution, CRS, bounds, georeferencing, nodata, and applicable cloud/quality metadata. | **AC-AST-01:** required metadata is shown or explicitly unavailable, never guessed. **AC-AST-02:** invalid type, size, structure, or geospatial metadata produces a structured rejection without creating a usable asset. **AC-AST-03:** an ungeoreferenced image remains usable only for supported pixel-space work and receives no invented geographic coordinates. |
| **PRD-QRY-001 Natural-language analysis** | Accept a question tied to owned inputs and route only to supported, bounded analysis capabilities. | **AC-QRY-01:** a supported request creates a traceable query/job with stable IDs. **AC-QRY-02:** unsupported or ambiguous requests return a specific limitation or clarification need. **AC-QRY-03:** language-model narration never substitutes for required measurement. |
| **PRD-EVD-001 Evidence-backed results** | Return answer, supported findings, measurements, evidence, provenance, confidence/quality meaning, warnings, limitations, and processing summary. | **AC-EVD-01:** every quantity identifies asset, method, units, assumptions, and denominator/exclusions where applicable. **AC-EVD-02:** every overlay identifies source image and coordinate space. **AC-EVD-03:** unknown fields are null/unavailable. **AC-EVD-04:** scores distinguish raw model score, heuristic quality, and calibrated probability. |
| **PRD-AOI-001 AOI workflow** | Create, edit, validate, and reuse an AOI in the map/workspace. | **AC-AOI-01:** invalid geometry and out-of-policy complexity are rejected. **AC-AOI-02:** persisted geometry uses the documented CRS/order and records ownership. **AC-AOI-03:** user can inspect the AOI used by an analysis. |
| **PRD-DSC-001 EO discovery** | Search configured Earth-observation catalogues by AOI, time, and supported metadata filters. | **AC-DSC-01:** results identify provider and provider asset ID with acquisition/quality metadata. **AC-DSC-02:** unavailable provider/credentials produce an explicit unavailable capability. **AC-DSC-03:** discovery results do not imply pixels were accessed or analyzed. |
| **PRD-CMP-001 Before/after comparison** | Compare two compatible assets with defensible spatial/temporal preparation. | **AC-CMP-01:** temporal ordering, CRS, resolution, alignment, valid overlap, nodata, and relevant quality differences are checked. **AC-CMP-02:** output states reprojection, resampling, co-registration, denominator, and exclusions. **AC-CMP-03:** appearance differences are not automatically labeled construction, demolition, vegetation loss, or flood damage. |
| **PRD-MOD-001 Optical and SAR analysis** | Support explicitly validated single- or multimodal methods when inputs and preprocessing are compatible. | **AC-MOD-01:** sensor, bands/polarizations, acquisition geometry/time, resolution, and preprocessing needs are validated. **AC-MOD-02:** mud, bare soil, sediment, water, shadow, and built surfaces are not treated as interchangeable classes. **AC-MOD-03:** object claims remain within image resolution and validated model capability. |
| **PRD-JOB-001 Inspectable execution** | Run long analyses asynchronously with explicit lifecycle, errors, retries, outputs, and a user-visible trace summary. | **AC-JOB-01:** status is one of the contract states and only legal transitions occur. **AC-JOB-02:** progress is absent unless based on real work. **AC-JOB-03:** retries do not silently duplicate a completed operation. **AC-JOB-04:** tool/version/parameter records support reproducibility where required. |
| **PRD-RSL-001 Honest limitations and failures** | Give limited, warned, unsupported, or failed outcomes when evidence or capability is insufficient. | **AC-RSL-01:** missing credentials never yield a fabricated result. **AC-RSL-02:** machine-readable errors distinguish validation, authorization, capability, dependency, and processing failures. **AC-RSL-03:** partial outputs are labeled incomplete and cannot appear complete. |
| **PRD-HIS-001 Analysis history** | List and reopen analyses owned by the current user with their immutable result provenance. | **AC-HIS-01:** cross-owner access is denied. **AC-HIS-02:** list pagination is stable. **AC-HIS-03:** reopened results identify unavailable/expired artifacts rather than silently replacing them. |
| **PRD-RPT-001 Reporting/export** | Export a human-readable analysis report where policy permits. | **AC-RPT-01:** report includes IDs, timestamps, asset provenance, findings, units/denominators, evidence references, confidence meaning, limitations, and method summary. **AC-RPT-02:** generation status and failure are inspectable. **AC-RPT-03:** report access follows result ownership and expiry policy. |
| **PRD-UI-001 Unified professional workspace** | Provide one responsive workspace containing viewer/map, query, layers/evidence, and results; no Simple/Expert split. | **AC-UI-01:** a user can complete the supported inspect-and-ask journey in one workspace. **AC-UI-02:** selected source, active layer/evidence, job state, and limitations remain identifiable. **AC-UI-03:** keyboard and assistive-technology checks cover core workflows. |

## Nonfunctional requirements

| Requirement | Acceptance direction |
|---|---|
| **PRD-NFR-SEC-001 Security and privacy** | **AC-NFR-SEC-01:** authorization tests deny cross-owner access to every protected resource. **AC-NFR-SEC-02:** secret, upload, remote-fetch, storage, logging, and deletion controls in `SECURITY.md` pass before affected features ship. |
| **PRD-NFR-REL-001 Reliability** | **AC-NFR-REL-01:** duplicate delivery, retry, cancellation, and worker-loss tests preserve legal durable states and never duplicate a completed operation. Results retain input/method lineage. |
| **PRD-NFR-REP-001 Reproducibility** | **AC-NFR-REP-01:** a completed measured result exposes immutable asset identity, timestamps, coordinate assumptions, relevant tool/model versions, parameters, and artifact checksums needed to repeat it. |
| **PRD-NFR-PERF-001 Performance** | **AC-NFR-PERF-01:** measured baselines and separate budgets exist for interaction, metadata APIs, upload, discovery, queues, and analysis before performance claims are made; targets above remain provisional. |
| **PRD-NFR-ACC-001 Accessibility** | **AC-NFR-ACC-01:** core UI journeys pass the selected WCAG 2.2 AA automated/manual checks, and map-only evidence has a textual/structured counterpart. Compliance remains unmeasured until UI exists. |
| **PRD-NFR-PORT-001 Portability** | **AC-NFR-PORT-01:** documented setup and verification run on supported Windows PowerShell and the selected portable/container path without undocumented shell assumptions. |
| **PRD-NFR-OBS-001 Observability** | **AC-NFR-OBS-01:** request/query/job correlation and failure-state tests pass while secret, token, signed-URL, and sensitive imagery leakage checks remain clean. |

## Scope boundaries

In product scope over the roadmap: imagery intake/selection, AOI and catalogue discovery, supported visual questions, grounded evidence, compatible comparisons and multimodal analysis, history, and reporting.

Out of Phase 0: all executable code, manifests, dependency installation, endpoints, migrations, database connections, authentication, UI, map components, processing, providers, deployment, and model/data downloads.

Not implied without later validation: universal sensor support; cadastral/legal surveying; autonomous high-stakes decisions; guaranteed object detection or disaster attribution; analysis of a basemap; or scientific accuracy outside documented validation bounds.

## Traceability

| Product requirements | Technical requirements | Features |
|---|---|---|
| PRD-AST-001 | TRD-AST-001, TRD-GEO-001, TRD-SEC-002 | F-AST-01 |
| PRD-QRY-001, PRD-RSL-001 | TRD-ORC-001, TRD-RSL-001, TRD-INT-001 | F-QRY-01, F-REL-01 |
| PRD-EVD-001 | TRD-RSL-002, TRD-GEO-002 | F-EVD-01 |
| PRD-AOI-001, PRD-DSC-001 | TRD-GEO-001, TRD-INT-001 | F-AOI-01, F-DSC-01 |
| PRD-CMP-001, PRD-MOD-001 | TRD-CMP-001, TRD-MOD-001 | F-CMP-01, F-MOD-01 |
| PRD-JOB-001 | TRD-JOB-001, TRD-OBS-001 | F-JOB-01 |
| PRD-HIS-001, PRD-RPT-001 | TRD-PER-001, TRD-RPT-001 | F-HIS-01, F-RPT-01 |
| PRD-UI-001 | TRD-BND-001, TRD-UI-001 | F-UI-01 |
| PRD-NFR-SEC-001 | TRD-SEC-001, TRD-SEC-002 | Cross-cutting security |
| PRD-NFR-REL-001 | TRD-JOB-001, TRD-RSL-001 | Cross-cutting reliability |
| PRD-NFR-REP-001 | TRD-RSL-002, TRD-PER-001 | F-EVD-01, F-JOB-01 |
| PRD-NFR-PERF-001 | TRD-PERF-001, TRD-OBS-001 | Cross-cutting performance |
| PRD-NFR-ACC-001 | TRD-UI-001 | F-UI-01 |
| PRD-NFR-PORT-001 | TRD-DEP-001 | F-CORE-01 |
| PRD-NFR-OBS-001 | TRD-OBS-001 | F-JOB-01, F-REL-01 |

The acceptance IDs above are the product-level checks. `TESTING.md` defines how later phases turn them into automated or manual evidence.

## Unresolved product decisions

- Which first analysis tasks, sensors, and datasets will receive validation and measurable accuracy thresholds.
- Supported file formats/sizes and retention/quotas for initial release.
- Identity/tenant model, sharing policy, and intended deployment jurisdictions.
- First EO catalogue/provider and licensing constraints.
- Report formats and whether export is included in the first usable release.
- The original agreed Phase 4–15 roadmap titles and scope, unavailable in the inspected workspace.
