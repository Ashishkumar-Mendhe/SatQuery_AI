# Phase 7 report — bounded imagery question answering

Last updated: **2026-09-24**  
Current status: **PHASE 7 PARTIALLY VERIFIED; 7A COMPLETE; 7B–7F EXECUTED WITH OPEN LIVE GATES**

This report records the 7A decision/contracts, 7B bounded answer/caption implementation, 7C referring-grounding implementation, 7D protected inference API/job implementation, 7E workspace connection, and 7F closeout verification. Phase 7 is not marked complete because live VQA/caption and the durable production workflow did not pass.

## 7F verification and closeout — 2026-09-24

One real Earth Search Sentinel-2 L2A input successfully traversed trusted RGB/SCL resolution, calibrated windowed extraction, the fixed model-chip renderer, Phase 6 quality checks, and the pinned local grounding runtime. Item `S2B_T43PGQ_20251223T051848_L2A`, acquired `2025-12-23T05:25:18.674Z`, produced a 110×113 PNG in EPSG:32643 with affine `(10, 0, 780970, 0, -10, 1436370)`, checksum `4fbf8bda…`, 100% all-RGB validity, 99.634% QA-usable AOI coverage, and catalogue cloud metadata 4.321234%. Its fixed 0.0–0.3 reflectance rendering retained transparent exclusions and performed no per-image normalization. A new regression confirms non-finite invalid samples become deterministic transparent pixels without an unsafe cast warning.

Grounding DINO revision `a2bb814…` returned one `vegetation` box in chip pixels `(0.6303, 1.3331, 109.7972, 112.5866)` with raw uncalibrated relevance `0.6482`. The exact affine produced projected corners spanning approximately `(780976.30, 1436356.67)` to `(782067.97, 1435244.13)` metres; independent EPSG:32643→WGS84 conversion placed the corners around `(77.589934–77.600094, 12.969899–12.980050)`, consistent with the chip/AOI bounds and the frontend conversion tests. Model inference was 5.915 s on local CPU; cold model load plus inference was 30.159 s; complete catalogue/extraction/QA/grounding elapsed time was 77.200 s. The source and overlay were visually inspected. The box covers nearly the whole chip and is therefore valid placement evidence but weak, over-broad localization—not model validation or a vegetation measurement.

Sample size was **one real unannotated scientific chip**. It is licence-compatible Sentinel input under the provider-linked Copernicus terms, but it has no independent VQA, caption, or box ground truth. The repository contains no suitable licence-reviewed annotated Phase 7 evaluation sample. The earlier labelled 16×16 synthetic fixture remains plumbing-only. Consequently no benchmark accuracy, precision/recall, caption score, or generalized model-quality claim is reported.

Live VQA and caption success were **not run** because `RUNTIME_AI_PROVIDER`, `RUNTIME_AI_MODEL`, and `RUNTIME_AI_API_KEY` remain unconfigured. The real-chip verifier returned `inference_not_run` with that reason; it did not fabricate responses. PostgreSQL/PostGIS and a verified production principal also remain unavailable, so durable production persistence/access checks remain covered only by synthetic API tests. Real API attempts additionally exposed intermittent bounded range-read failures before stage one; these became terminal safe `inference_failed` jobs with no result/artifact. Phase 7 therefore cannot be complete.

Negative/failure coverage passed for unsupported quantitative questions, failed and unknown quality, unavailable answer model, no grounding detection, invalid grounding, stale provider references, stale UI selection, and cross-owner artifact denial. A real headless-browser flow restored the AOI, searched Earth Search, selected one of six scenes, submitted a question, displayed the safe retryable inference failure, and refreshed. Refresh restored the AOI but did not resurrect the prior answer/overlay. The canonical `localhost:3000` run had only a missing favicon and upstream basemap-style warnings; a deliberate `127.0.0.1:3000` origin exposed exact-origin CORS failures, confirming setup must use the documented canonical origin.

Required gates passed: `scripts/verify.ps1`; backend 187 passed / 1 PostgreSQL integration skip; frontend 114/114; focused Phase 7 frontend 15/15; focused VQA/grounding backend 14/14; Ruff format/check, strict mypy, Biome format/lint, TypeScript, and optimized Next build. Documentation reconciliation retains the phase as **PARTIALLY VERIFIED**. Exact completion action: configure the pinned server-side answer model, PostgreSQL/PostGIS and verified principal; run real VQA and caption through the protected job API/workspace; use a licence-reviewed annotated evaluation sample; and repeat the real grounding overlay in the workspace. Stop before Phase 8.

## 7E workspace AI results — 2026-09-24

The workspace assistant now offers three explicit operations for the selected supported Earth Search Sentinel-2 L2A scene and current AOI: ask one image question, generate a caption, or locate a referred feature. It submits the stable scene/AOI contract to the protected inference job API, polls actual states, and shows actual stage units without deriving a percentage. Recoverable failures retain the draft and expose retry. A per-request sequence and cancellation guard prevents late responses from replacing a newer selection.

The result panels contain only typed backend evidence. Answer distinguishes model interpretation from unavailable/blocked/unknown states and shows source scene, acquisition, model/version, execution/quality status, and warnings/actions. Evidence loads the exact owner-authorized PNG used by inference, overlays validated chip-pixel boxes, links every region to the source chip, and offers a separate map visibility toggle. Supported UTM projected footprints are converted to WGS84 for MapLibre; unsupported CRS or invalid coordinates fail closed. Changing scene hides the overlay and marks the retained answer stale rather than relocating it. The AOI geometry is never modified.

Supporting backend work atomically commits both the exact `inference_chip` PNG and `inference_evidence` JSON and requires both for cache reuse. Inference and preparation artifact routes remain kind-scoped, and authorization is unchanged. No thumbnail, basemap, screenshot, illustrative response, model score, or absent measurement becomes scientific evidence or confidence.

Verification passed: six focused assistant/map tests cover question, caption, exact-chip grounding, overlay show/hide, retry with draft retention, stale-scene behavior, coordinate conversion, and unsupported CRS. The complete frontend passed 114 tests across 26 files; Biome, TypeScript, and production build passed. The backend passed 186 tests with one PostgreSQL integration skip; Ruff, format, and strict mypy passed over 84 files. Desktop and compact-width headless-Chrome renders were visually inspected.

Live verification is incomplete. The configured browser connector failed before tab creation because sandbox policy metadata was unavailable, so the automated tests are not represented as a real browser click-through. A real API job for Earth Search item `S2B_T43PGQ_20251223T051848_L2A` over a bounded AOI completed trusted RGB reads but failed safely while opening the provider SCL stream (`not recognized as being in a supported file format`). It returned terminal `inference_failed`, one of four stages complete, no result, and no artifacts. No model call or real overlay is claimed. Task 7E is implemented but partially verified; stop before 7F.

## 7D inference API and evidence records — 2026-09-24

SatQuery now exposes protected typed start/status/result/cancel/artifact routes under `/api/v1/inference`. Public input contains only a stable supported scene identity, validated AOI, closed operation, bounded text, request UUID, and optional normalized user-selected grounding crop. It cannot contain asset URLs, paths, bytes, credentials, client readiness, model output, or confidence. The worker re-fetches the catalogue item and resolves calibrated RGB plus actual SCL through the existing trusted provider services, then builds the exact fixed-render/checksum-bound chip used by 7B/7C.

Slow extraction and inference reuse the Phase 6 durable PostgreSQL job/event/artifact infrastructure. Repository operations are now explicitly scoped as `prepare_optical` or `infer_single_image`, including idempotency, cache lookup, queued recovery, and worker claiming. The inference cache binds owner/access scope, canonical request/AOI, stable provider item version/acquisition evidence, and code/operation version. Task 7E extended the private atomic result to the exact `inference_chip` PNG plus its `inference_evidence` JSON, both readable only through the existing owner/scope lookup and both required for cache reuse. No incomplete artifact is exposed.

Evidence retains the source scene/acquisition, chip source assets/checksum/dimensions/rendering/footprint/affine, complete Phase 6 VQA quality context, explicit quality decision, execution outcome, actual answer model/version/parameters or actual grounding result, and a warning that provenance is not proof of interpretation. Required failed quality is `blocked`; required unresolved quality is `unknown`; an absent configured answer model is `unavailable`. These outcomes complete the policy evaluation without inventing model work. Jobs expose actual stage units and queued/running/cancelling/succeeded/failed/cancelled states, never percentages or numerical answer confidence. Invalid grounding fails without an artifact.

Verification passed: focused API/service cases cover a successful VQA request through the FastAPI ASGI route, exact-chip evidence, cache reuse, unavailable model, blocked and unknown quality, stale provider scene, invalid grounding, and cross-owner artifact denial. Ruff and strict mypy passed, and the full backend suite passed 186 tests with one PostgreSQL integration test skipped because its URL is unconfigured. A request using the real scene `S2C_T43PGQ_20251228T052411_L2A` was sent through the actual SatQuery API; it truthfully returned `503 CAPABILITY_UNAVAILABLE` before acceptance because no verified principal resolver is configured, while startup also recorded unavailable durable processing. Therefore no real extraction, live model call, persisted database row, or authorized production artifact is claimed. Task 7D is implemented but partially verified; stop before 7E.

## 7C grounding implementation

The authorized 7C scope supersedes the tracker’s earlier provisional 7C/7D ordering. SatQuery now has a separate local grounding pipeline using `IDEA-Research/grounding-dino-tiny` at immutable revision `a2bb814dd30d776dcf7e30523b00659f4f141c71`. The checkpoint model card declares Apache-2.0 and zero-shot object detection; `model.safetensors` is 689,359,096 bytes. It is a general open-set detector, not a remote-sensing-localization model, so its output is candidate evidence requiring inspection rather than ground truth. Sources: [Grounding DINO repository](https://github.com/IDEA-Research/GroundingDINO), [Transformers model documentation](https://huggingface.co/docs/transformers/model_doc/grounding-dino), and [pinned checkpoint](https://huggingface.co/IDEA-Research/grounding-dino-tiny/tree/a2bb814dd30d776dcf7e30523b00659f4f141c71).

The processor uses its recorded 800-pixel shortest edge, 1333-pixel longest edge, bilinear resize, ImageNet normalization, and right/bottom padding. Postprocessing explicitly targets the original whole-chip or selected-crop dimensions. A selected region is an integer pixel-edge crop bound to the source chip and remains a separate request field. Detector boxes first remain in visual-prompt pixels, are clipped there, receive the crop offset into chip pixels, and are transformed at their four pixel-edge corners through the recorded chip affine into its projected CRS. Degenerate/outside geometry is discarded. Synthetic round-trip tests invert the supported affine and recover the original chip coordinates.

Contracts distinguish `detected`, `no_detection`, `ambiguous_detection`, `unsupported_geometry`, `unavailable`, and `failed_inference`. Multiple candidates are retained only because Grounding DINO natively returns multiple detections. `model_score` is explicitly `uncalibrated_model_relevance`, never probability or answer confidence. The selected model produces rectangular boxes only. Requests for a polygon or mask return `unsupported_geometry`; the derived map rectangle is labelled a box footprint and is not a segmentation polygon.

Dependencies are isolated in the `grounding` optional extra and pinned as Pillow 12.3.0, PyTorch 2.14.0 CPU, and Transformers 5.17.0. Model loading is lazy; inference is thread-offloaded, limited to two concurrent calls (default one), capped at 300 seconds, and accepts at most ten candidates. Exact chip contract, byte count, checksum, and Phase 6 readiness are checked before the runtime is called. No HTTP route, durable job, public artifact, workspace behavior, or automatic coupling to VQA was added.

## 7C verification outcome — 2026-09-24

- Focused synthetic grounding tests: **PASSED**, 6/6. They cover selected-region separation, crop offset, clipping, pixel↔map round trip, multiple/ambiguous candidates, no detection, invalid outside boxes, unsupported masks, quality refusal, model failure, and chip tampering.
- Full non-database backend: **PASSED**, 181/181 with one PostgreSQL integration test deselected. Ruff format/check and strict mypy passed over 80 source/test/script files. Documentation audit passed over 34 Markdown files with 43 relative links, zero broken targets, 16 roadmap rows, and one active row.
- Actual model runtime: **PASSED on a labelled synthetic fixture only**. The pinned 689 MB checkpoint loaded locally on CPU and returned one `vegetation` box for the uniform 16×16 calibrated fixture: visual-prompt/chip box approximately `(0.0032, 0.0, 16.0, 15.9984)`, raw uncalibrated model score `0.5292`, model inference `5.30 s`, processed at 800×800 with no padding. The saved `tmp/phase-7c-grounding/scientific-chip.png` and `grounding-overlay.png` were visually inspected and the near-full-chip placement agrees with the returned coordinates. This fixture contains no meaningful object and proves execution/placement only, not localization quality.
- Real-scene verification: **FAILED/BLOCKED**. `backend/scripts/verify_grounding.py` searched three real Earth Search Sentinel-2 scenes over the airport AOI. Each trusted bounded RGB extraction failed at the inherited COG range-read deadline before SCL/chip/model inference. No real model-produced region, real overlay, or visual accuracy assessment exists. No thumbnail, basemap, or prior screenshot was substituted.

Task 7C therefore remains partially verified. Completion requires a QA-ready real scientific chip through the trusted extraction path, an actual checkpoint result (including a truthful no-detection result), and side-by-side source/overlay inspection with uncertainty recorded.

## 7A environment finding

- Host: Windows 10.0.26200 x64, Intel Core i5-1235U, 12 logical processors, approximately 15.7 GiB RAM.
- No usable NVIDIA runtime was demonstrated: `nvidia-smi` is not installed. Windows device enumeration was denied, so this is not a claim that the machine has no GPU; it is a finding that a supported local CUDA inference runtime is unavailable here.
- The backend has raster dependencies but no installed `torch`, `transformers`, `accelerate`, OpenAI SDK, Anthropic SDK, or Hugging Face inference SDK. The frontend has no model-provider SDK.
- The checked environment contains no configured AI provider, model, or API credential. Values were checked only for presence and were not printed.
- Phase 6 remains partially verified. Its real persisted identity/database workflow was not demonstrated, and the workspace still declares analysis unavailable. A model flow must consume an authorized prepared artifact and carry the actual Phase 6 readiness/checks; it cannot infer that preparation passed.

## Model evaluation and decision

### GeoChat-7B — evaluated, not selected for the first executable path

GeoChat is directly relevant: its authors describe image/region captioning, VQA, scene classification, grounded conversation, and referring-object detection. The public checkpoint is a 7B LLaVA/Vicuna-derived model with custom GeoChat architecture, float16 weights, a 504×504 training image setting, and two PyTorch weight shards totalling approximately 14.1 GB. The repository documents Python 3.10/custom installation and reports training on three A100 40 GB GPUs; it does not publish a supported inference-memory requirement for this host. Sources: [GeoChat repository](https://github.com/mbzuai-oryx/GeoChat), [paper](https://arxiv.org/abs/2311.15826), [checkpoint files](https://huggingface.co/MBZUAI/geochat-7B/tree/main), and [checkpoint configuration](https://huggingface.co/MBZUAI/geochat-7B/blob/main/config.json).

The Hugging Face model card labels the checkpoint `apache-2.0`, but the repository page does not expose a repository licence file and the model derives from LLaVA/Vicuna and multiple training datasets. Dependency, base-model, and dataset terms therefore still require deployment review; the checkpoint tag alone is not treated as complete commercial clearance. The card also reports no deployed inference provider. GeoChat is not feasible on the currently demonstrated runtime without a separately provisioned GPU service and that review. No weights were downloaded and no model was trained.

### Selected answer/caption path

The initial adapter target is the OpenAI Responses API with the pinned `gpt-4.1-mini-2025-04-14` snapshot. The official model page documents image input, Responses API support, structured output, and the pinned snapshot. It is hosted, so there are no downloadable weights or open-source weight licence; use is governed by the provider's service terms and must pass the project's privacy/data-transfer review before deployment. Source: [GPT-4.1 mini model page](https://developers.openai.com/api/docs/models/gpt-4.1-mini).

This is feasible because it needs no local GPU and can be called from a bounded backend adapter. It is not active today because no provider credential is configured. 7B must use deterministic fake transport first and report the live smoke separately as unavailable until configuration exists.

The model is a general vision-language model, not a remote-sensing measurement system. Official vision guidance warns that vision models can make mistakes, produce incorrect descriptions, struggle with precise spatial localization, and only approximate counts. GeoChat's paper independently reports that general-domain VLMs can be inaccurate or fabricate remote-sensing-specific information. Accordingly, this path is limited to cautious single-chip captioning and visual questions; it cannot establish land-use facts, quantitative counts, change, damage, sub-resolution objects, or calibrated confidence. Sources: [OpenAI vision limitations](https://developers.openai.com/api/docs/guides/images-vision#limitations) and [GeoChat paper](https://arxiv.org/abs/2311.15826).

## Image and answer contract

The closed Pydantic contracts are in `backend/src/satquery/api/schemas/vqa.py`.

- `ModelImageChip` accepts only an authorized prepared-raster artifact identity and checksum—never a client URL, path, or arbitrary bytes. It records acquisition time and is bounded to 2048×2048 / 4,194,304 pixels and 20 MiB.
- The chip is a derived visual representation, not calibrated scientific data. It records RGB band order, source units, a fixed linear input/output range, explicit visual-only out-of-range clipping, transparent invalid pixels, and `per_image_normalization=false`. The calibrated Phase 6 raster remains unchanged as the source of record.
- `PixelToMapTransform` explicitly defines upper-left pixel-edge coordinates, right/down axes, UTM CRS, and a north-up affine transform.
- `Phase6QualityContext` retains preparation job, manifest, task readiness, and the exact checks supporting that readiness. Failed/unresolved evidence is representable; contradictory ready/failed evidence is rejected.
- `VqaCaptionRequest` distinguishes captioning from VQA and allows no untyped extras.
- `ModelAnswer` has explicit `available`, `unavailable`, and `unknown` states, a versioned model identity, image-specific evidence references, warnings, optional separate grounding, and the Phase 6 context. `calibrated_confidence` is constrained to null and arbitrary `confidence` fields are rejected.
- Grounding geometry is separately typed as chip pixel-edge boxes or projected-map polygons. Every geometry identifies the exact chip and coordinate space.

## Grounding decision

The selected answer model's text or coordinates are not accepted as spatial grounding because its documented precise-localization limitation is incompatible with an evidence overlay. Grounding initially returns `unavailable` or `unknown`.

The separate research candidate is GeoChat-7B grounding because it explicitly supports grounded descriptions and rotated/referring boxes for remote-sensing imagery. It remains disabled until a version-pinned GPU runtime, dependency/licence review, bounded output parser, and synthetic pixel-coordinate evaluation exist. A future evaluation does not imply that its locations are accurate; accepted geometry must use the separate grounding contract and source-chip transform.

## Executable 7B acceptance boundary

`backend/tests/test_vqa_schemas.py::test_7b_acceptance_contract_fixture_is_executable_and_retains_failed_quality` is the executable boundary fixture. In 7B, the deterministic fake adapter must consume that request and return the represented answer without dropping the failed Phase 6 finding, adding confidence, changing the chip, or claiming grounding. A live provider smoke remains a separate conditional test.

## 7B implementation

- `satquery.inference.chip` creates a PNG only from trusted calibrated RGB extraction and decoded SCL masks. The fixed 0.0–0.3 surface-reflectance rendering is recorded, clipping applies only to the derived visual chip, invalid/excluded pixels are transparent, and calibrated arrays remain unchanged. The contract preserves stable source item/assets, acquisition time, RGB order, dimensions, AOI footprint, projected CRS/affine transform, checksum, byte size, and measured quality checks. No basemap, preview, or catalogue thumbnail is accepted.
- Runtime-measured chips and committed prepared artifacts are distinguished explicitly. The provisional `vqa-provisional-engineering-v1` gate requires at least 0.8 all-RGB-valid AOI fraction and 0.5 decoded-QA-usable AOI fraction. These are conservative engineering controls, not scientifically universal thresholds. Missing QA is unresolved and blocks inference rather than assuming clear conditions.
- `SingleImageInferenceService` provides separate question-answer and caption operations. It rejects quantitative/count/area/percentage/distance/coordinate/confidence, single-image temporal-change, construction/demolition, and damage questions before inference. Failed or unresolved quality also stops before the provider call.
- `OpenAIResponsesTransport` calls only the fixed `https://api.openai.com/v1/responses` endpoint using the pinned `gpt-4.1-mini-2025-04-14` snapshot, a base64 PNG data URL, `detail=high`, strict structured output, `store=false`, temperature 0, and bounded output/time. The service records prompt/adapter/model versions, parameters, provider response ID, and measured latency. Credentials remain `SecretStr` server configuration and never enter the chip or result.
- Input is limited to 2048×2048 / 4,194,304 pixels, 20 MiB, and 500 question characters. Output is limited to configured tokens and request characters, timeout is at most 120 seconds, and concurrent inference is limited to two (default one). The lifespan exposes the service internally only when all provider settings are present. No public route was added because authorized prepared-input orchestration belongs to 7C.

Transformers was not used: 7A selected a hosted OpenAI model rather than a local Hugging Face checkpoint. The implemented processor follows the official [OpenAI image-input guidance](https://developers.openai.com/api/docs/guides/images-vision) and [Responses API contract](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).

## 7B actual verification outcome — 2026-09-24

- Deterministic focused boundary: **PASSED**, 23/23 across VQA schemas, inference, and configuration. It exercised real PNG encoding from labelled calibrated arrays, exact-chip checksum binding, both operations, strict OpenAI request/response shape, quality/missing-QA refusal, unsupported quantitative questions, timeout, and one-slot concurrency. These remain clearly synthetic fixtures and are never production fallback answers.
- Full non-database backend: **PASSED**, 175/175. Ruff format/check passed for 81 files and strict mypy passed for 77 source/test/script files.
- Documentation/roadmap audit: **PASSED**, 34 Markdown files, 43 relative links, zero broken targets, exactly 16 phase rows, and one active row.
- Real provider chip attempt: **FAILED/BLOCKED**. Both the normal and explicitly unrestricted-network runs reached real Earth Search metadata, then trusted remote COG range reads timed out inside the existing Rasterio range opener before an accepted chip could be produced. No thumbnail/basemap fallback was used.
- Live VQA inference: **NOT RUN**. `RUNTIME_AI_PROVIDER`, `RUNTIME_AI_MODEL`, and `RUNTIME_AI_API_KEY` are all unconfigured, and no accepted real chip was available. Output and model latency are unavailable.
- Live caption inference: **NOT RUN** for the same reasons. Output and model latency are unavailable.
- Hardware actually observed for orchestration remains the Windows x64 Intel Core i5-1235U host with approximately 15.7 GiB RAM and no demonstrated NVIDIA runtime. Hosted model execution hardware is provider-managed and undisclosed; no contrary hardware claim is made.

The mandatory live VQA and caption acceptance criteria therefore did not pass, so 7B is not marked complete.

## 7A verification

- Focused schema tests: **PASSED**, 6/6.
- Full non-database backend tests: **PASSED**, 166/166. The database integration test was intentionally not run because 7A has no database behavior and the carried PostgreSQL gate remains unavailable.
- Ruff check/format: **PASSED**, 76 Python files.
- Strict mypy: **PASSED**, 42 source files.
- Documentation audit: **PASSED**, 35 Markdown files, zero broken relative links, exactly 16 roadmap phase rows.
- Live OpenAI/GeoChat inference: **not run**; no configured provider/local runtime, and live inference is outside 7A.
- Browser UI: **not run**; no UI behavior changed in 7A.

## Exact next action

Do not start Phase 8. To finish the open Phase 7 gates, configure the pinned server-side answer model, durable PostgreSQL/verified identity, and a licence-reviewed annotated sample. Then run successful real question and caption jobs through the workspace and repeat the real grounding source/map overlay inspection; retain measured outputs and limitations.
