import { z } from "zod";

export const VIEWER_SCHEMA_VERSION = "1.0" as const;
export const VIEWER_STATE_VERSION = 1 as const;

const utcTimestampSchema = z
  .string()
  .refine(
    (value) => value.endsWith("Z") && Number.isFinite(Date.parse(value)),
    "Expected an ISO 8601 UTC timestamp with a Z suffix.",
  );
const providerIdentifierSchema = z
  .string()
  .min(1)
  .max(64)
  .regex(/^[a-z0-9][a-z0-9._-]*$/);
const boundedIdentifierSchema = z.string().min(1).max(512);
const viewerIdentifierSchema = z
  .string()
  .min(1)
  .max(160)
  .regex(/^[a-z0-9][a-z0-9._-]*$/);
const acquisitionSchema = z
  .object({ start: utcTimestampSchema, end: utcTimestampSchema })
  .strict()
  .refine((value) => Date.parse(value.end) >= Date.parse(value.start), {
    message: "Acquisition end must not precede start.",
    path: ["end"],
  });
const boundsSchema = z
  .tuple([z.number().finite(), z.number().finite(), z.number().finite(), z.number().finite()])
  .superRefine(([west, south, east, north], context) => {
    if (
      !(-180 <= west && west < east && east <= 180 && -90 <= south && south < north && north <= 90)
    ) {
      context.addIssue({
        code: "custom",
        message: "Bounds must be ordered west, south, east, north within WGS84.",
      });
    } else if (east - west > 180) {
      context.addIssue({
        code: "custom",
        message: "Antimeridian-crossing bounds are unsupported.",
      });
    }
  });
const attributionSchema = z
  .array(z.string().min(1).max(1000))
  .min(1)
  .max(20)
  .superRefine((values, context) => {
    if (new Set(values).size !== values.length) {
      context.addIssue({ code: "custom", message: "Attributions must be unique." });
    }
  });

export const viewerSceneIdentitySchema = z
  .object({
    provider: providerIdentifierSchema,
    collection: z.string().min(1).max(160),
    item: boundedIdentifierSchema,
  })
  .strict();

export const resolvedImageryAssetIdentitySchema = z
  .object({
    scene: viewerSceneIdentitySchema,
    asset: boundedIdentifierSchema,
    asset_version: z.string().min(1).max(256).nullable(),
  })
  .strict();

export const catalogueAvailabilitySchema = z
  .object({
    state: z.enum(["available", "stale", "unavailable", "unknown"]),
    reason: z.string().min(1).max(1000).nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    if ((value.state === "stale" || value.state === "unavailable") && value.reason === null) {
      context.addIssue({
        code: "custom",
        message: `${value.state} catalogue state requires a reason.`,
      });
    }
  });

export const assetAccessibilitySchema = z
  .object({
    state: z.enum([
      "accessible",
      "requires_authorization",
      "requires_purchase",
      "expired",
      "unavailable",
      "unknown",
    ]),
    method: z.enum(["none", "provider_reference", "backend_mediated"]),
    reason: z.string().min(1).max(1000).nullable(),
    expires_at: utcTimestampSchema.nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.state === "accessible" && value.method === "none") {
      context.addIssue({
        code: "custom",
        message: "Accessible imagery requires an access method.",
      });
    }
    if (value.state !== "accessible" && value.method !== "none") {
      context.addIssue({
        code: "custom",
        message: "Inaccessible imagery must not expose an access method.",
      });
    }
    if (
      ["requires_authorization", "requires_purchase", "expired", "unavailable"].includes(
        value.state,
      ) &&
      value.reason === null
    ) {
      context.addIssue({
        code: "custom",
        message: `${value.state} asset state requires a reason.`,
      });
    }
    if (value.state === "expired" && value.expires_at === null) {
      context.addIssue({ code: "custom", message: "Expired asset access requires expires_at." });
    }
  });

export const analysisReadinessSchema = z
  .object({
    state: z.enum(["not_assessed", "not_ready", "ready", "unsupported"]),
    reason: z.string().min(1).max(1000),
  })
  .strict();

export const supportedRenderPresetSchema = z
  .object({
    id: viewerIdentifierSchema,
    title: z.string().min(1).max(160),
    description: z.string().min(1).max(500),
    mode: z.enum(["rgb", "single_band"]),
    bands: z.array(boundedIdentifierSchema).min(1).max(3),
    purpose: z.literal("visualization"),
  })
  .strict()
  .superRefine((value, context) => {
    const required = value.mode === "rgb" ? 3 : 1;
    if (value.bands.length !== required) {
      context.addIssue({
        code: "custom",
        message: `${value.mode} render presets require exactly ${required} band(s).`,
      });
    }
    if (new Set(value.bands).size !== value.bands.length) {
      context.addIssue({ code: "custom", message: "Render preset bands must be unique." });
    }
  });

export const resolvedImageryAssetSchema = z
  .object({
    schema_version: z.literal(VIEWER_SCHEMA_VERSION),
    identity: resolvedImageryAssetIdentitySchema,
    acquisition: acquisitionSchema,
    media_type: z
      .string()
      .min(1)
      .max(160)
      .regex(/^image\/[a-z0-9.+-]+$/),
    bounds: boundsSchema,
    render_presets: z.array(supportedRenderPresetSchema).min(1).max(20),
    default_render_preset: viewerIdentifierSchema,
    catalogue_availability: catalogueAvailabilitySchema,
    asset_accessibility: assetAccessibilitySchema,
    analysis_readiness: analysisReadinessSchema,
    attributions: attributionSchema,
    resolved_at: utcTimestampSchema,
  })
  .strict()
  .superRefine((value, context) => {
    const identifiers = value.render_presets.map((preset) => preset.id);
    if (new Set(identifiers).size !== identifiers.length) {
      context.addIssue({ code: "custom", message: "Render preset identifiers must be unique." });
    }
    if (!identifiers.includes(value.default_render_preset)) {
      context.addIssue({
        code: "custom",
        message: "The default render preset must identify a supported preset.",
      });
    }
  });

export const tileAccessSchema = z
  .object({
    state: z.enum(["available", "expired", "denied", "unavailable"]),
    reason: z.string().min(1).max(1000).nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.state !== "available" && value.reason === null) {
      context.addIssue({
        code: "custom",
        message: `${value.state} tile access requires a reason.`,
      });
    }
  });

const tileUrlTemplateSchema = z
  .string()
  .min(1)
  .max(2048)
  .superRefine((value, context) => {
    if (
      !value.startsWith("/api/v1/") ||
      value.includes("?") ||
      value.includes("#") ||
      !["{z}", "{x}", "{y}"].every((marker) => value.includes(marker))
    ) {
      context.addIssue({
        code: "custom",
        message: "Tile URL templates must be relative mediated API paths with z, x, and y markers.",
      });
    }
  });

export const tileMetadataSchema = z
  .object({
    schema_version: z.literal(VIEWER_SCHEMA_VERSION),
    tile_set_id: z.string().uuid(),
    asset: resolvedImageryAssetIdentitySchema,
    render_preset: viewerIdentifierSchema,
    bounds: boundsSchema,
    min_zoom: z.number().int().min(0).max(24),
    max_zoom: z.number().int().min(0).max(24),
    tile_size: z.union([z.literal(256), z.literal(512)]),
    media_type: z.enum(["image/png", "image/jpeg", "image/webp"]),
    url_template: tileUrlTemplateSchema.nullable(),
    expires_at: utcTimestampSchema.nullable(),
    attributions: attributionSchema,
    access: tileAccessSchema,
  })
  .strict()
  .superRefine((value, context) => {
    if (value.max_zoom < value.min_zoom) {
      context.addIssue({ code: "custom", message: "max_zoom must not be less than min_zoom." });
    }
    if (value.access.state === "available") {
      if (value.url_template === null || value.expires_at === null) {
        context.addIssue({
          code: "custom",
          message: "Available tile access requires a URL template and expires_at.",
        });
      }
    } else if (value.url_template !== null) {
      context.addIssue({
        code: "custom",
        message: "Unavailable tile access must not expose a URL template.",
      });
    }
    if (value.access.state === "expired" && value.expires_at === null) {
      context.addIssue({ code: "custom", message: "Expired tile access requires expires_at." });
    }
  });

export const imageryDisplaySettingsSchema = z
  .object({
    visible: z.boolean(),
    opacity: z.number().min(0).max(1),
    brightness_min: z.number().min(0).max(1),
    brightness_max: z.number().min(0).max(1),
    contrast: z.number().min(-1).max(1),
    saturation: z.number().min(-1).max(1),
  })
  .strict()
  .refine((value) => value.brightness_max >= value.brightness_min, {
    message: "brightness_max must not be less than brightness_min.",
    path: ["brightness_max"],
  });

export const renderStatusSchema = z
  .object({
    state: z.enum(["not_requested", "loading", "rendered", "failed", "expired"]),
    reason: z.string().min(1).max(1000).nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    if ((value.state === "failed" || value.state === "expired") && value.reason === null) {
      context.addIssue({
        code: "custom",
        message: `${value.state} render state requires a reason.`,
      });
    }
  });

export const activeImageryLayerSchema = z
  .object({
    layer_id: viewerIdentifierSchema,
    asset: resolvedImageryAssetIdentitySchema,
    acquisition: acquisitionSchema,
    render_preset: viewerIdentifierSchema,
    tile_set_id: z.string().uuid().nullable(),
    display: imageryDisplaySettingsSchema,
    catalogue_availability: catalogueAvailabilitySchema,
    asset_accessibility: assetAccessibilitySchema,
    render_status: renderStatusSchema,
    analysis_readiness: analysisReadinessSchema,
  })
  .strict()
  .superRefine((value, context) => {
    if (value.render_status.state === "rendered") {
      if (value.tile_set_id === null) {
        context.addIssue({ code: "custom", message: "A rendered layer requires tile_set_id." });
      }
      if (value.asset_accessibility.state !== "accessible") {
        context.addIssue({
          code: "custom",
          message: "A rendered layer requires accessible asset state.",
        });
      }
    }
  });

const comparisonSceneSchema = z
  .object({ scene: viewerSceneIdentitySchema, acquisition: acquisitionSchema })
  .strict();

export const savedComparisonSlotsSchema = z
  .object({
    scene_a: comparisonSceneSchema.nullable(),
    scene_b: comparisonSceneSchema.nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.scene_a === null && value.scene_b === null) {
      context.addIssue({
        code: "custom",
        message: "At least one saved comparison slot is required.",
      });
    }
    if (
      value.scene_a &&
      value.scene_b &&
      JSON.stringify(value.scene_a.scene) === JSON.stringify(value.scene_b.scene)
    ) {
      context.addIssue({ code: "custom", message: "Saved comparison slots must be distinct." });
    }
  });

export const comparisonSelectionSchema = z
  .object({ scene_a: comparisonSceneSchema, scene_b: comparisonSceneSchema })
  .strict()
  .superRefine((value, context) => {
    if (JSON.stringify(value.scene_a.scene) === JSON.stringify(value.scene_b.scene)) {
      context.addIssue({ code: "custom", message: "Comparison scenes A and B must be distinct." });
    }
    if (
      Date.parse(value.scene_a.acquisition.start) >= Date.parse(value.scene_b.acquisition.start)
    ) {
      context.addIssue({ code: "custom", message: "Scene A must be acquired before scene B." });
    }
  });

const timelineSceneSchema = z
  .object({ scene: viewerSceneIdentitySchema, acquisition: acquisitionSchema })
  .strict();

export const timelineSelectionSchema = z
  .object({
    scenes: z.array(timelineSceneSchema).min(1).max(100),
    selected_scene: viewerSceneIdentitySchema,
  })
  .strict()
  .superRefine((value, context) => {
    const identities = value.scenes.map((entry) => JSON.stringify(entry.scene));
    if (new Set(identities).size !== identities.length) {
      context.addIssue({ code: "custom", message: "Timeline scene identities must be unique." });
    }
    if (
      value.scenes.some(
        (entry, index) =>
          index > 0 &&
          Date.parse(value.scenes[index - 1].acquisition.start) >
            Date.parse(entry.acquisition.start),
      )
    ) {
      context.addIssue({
        code: "custom",
        message: "Timeline scenes must be ordered by increasing acquisition time.",
      });
    }
    if (!identities.includes(JSON.stringify(value.selected_scene))) {
      context.addIssue({
        code: "custom",
        message: "The selected scene must be present in the timeline.",
      });
    }
  });

export const savedImageryLayerSchema = z
  .object({
    layer_id: viewerIdentifierSchema,
    asset: resolvedImageryAssetIdentitySchema,
    acquisition: acquisitionSchema,
    render_preset: viewerIdentifierSchema,
    display: imageryDisplaySettingsSchema,
  })
  .strict();

export const viewerAoiReferenceSchema = z
  .object({
    storage_key: z.literal("satquery.aoi-draft.v1"),
    geometry_fingerprint: z.string().min(1).max(100_000),
  })
  .strict();

export const viewerCameraSchema = z
  .object({
    center: z.tuple([z.number().min(-180).max(180), z.number().min(-85.051129).max(85.051129)]),
    zoom: z.number().min(0).max(24),
    bearing: z.number().min(-360).max(360),
    pitch: z.number().min(0).max(85),
  })
  .strict();

export const savedViewerStateSchema = z
  .object({
    version: z.literal(VIEWER_STATE_VERSION),
    saved_at: utcTimestampSchema,
    aoi_reference: viewerAoiReferenceSchema.nullable(),
    camera: viewerCameraSchema.nullable(),
    active_layer: savedImageryLayerSchema.nullable(),
    comparison_slots: savedComparisonSlotsSchema.nullable(),
    comparison: comparisonSelectionSchema.nullable(),
    timeline: timelineSelectionSchema.nullable(),
  })
  .strict();

export type ViewerSceneIdentity = z.infer<typeof viewerSceneIdentitySchema>;
export type ResolvedImageryAssetIdentity = z.infer<typeof resolvedImageryAssetIdentitySchema>;
export type SupportedRenderPreset = z.infer<typeof supportedRenderPresetSchema>;
export type ResolvedImageryAsset = z.infer<typeof resolvedImageryAssetSchema>;
export type TileMetadata = z.infer<typeof tileMetadataSchema>;
export type ImageryDisplaySettings = z.infer<typeof imageryDisplaySettingsSchema>;
export type ActiveImageryLayer = z.infer<typeof activeImageryLayerSchema>;
export type ComparisonSelection = z.infer<typeof comparisonSelectionSchema>;
export type TimelineSelection = z.infer<typeof timelineSelectionSchema>;
export type SavedViewerState = z.infer<typeof savedViewerStateSchema>;
export type ViewerCamera = z.infer<typeof viewerCameraSchema>;
