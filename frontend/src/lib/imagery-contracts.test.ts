import { describe, expect, it } from "vitest";
import {
  alignmentStatusSchema,
  imageryAssetSchema,
  imageryFormatSchema,
  imageryJobStatusSchema,
  imageryProductTypeSchema,
  imageryRequestSchema,
  rasterMetadataSchema,
  temporalImageryRequestSchema,
  temporalImageryResponseSchema,
  visualizationPresetSchema,
} from "./imagery-contracts";

describe("Imagery Zod Contracts", () => {
  const samplePolygon = {
    type: "Polygon" as const,
    coordinates: [
      [
        [77.5, 12.9],
        [77.7, 12.9],
        [77.7, 13.1],
        [77.5, 13.1],
        [77.5, 12.9],
      ],
    ],
  };

  it("validates ImageryProductType enum", () => {
    expect(imageryProductTypeSchema.parse("map_preview")).toBe("map_preview");
    expect(imageryProductTypeSchema.parse("analysis_raster")).toBe("analysis_raster");
    expect(imageryProductTypeSchema.parse("catalogue_thumbnail")).toBe("catalogue_thumbnail");
    expect(() => imageryProductTypeSchema.parse("invalid_type")).toThrow();
  });

  it("validates ImageryJobStatus enum", () => {
    expect(imageryJobStatusSchema.parse("queued")).toBe("queued");
    expect(imageryJobStatusSchema.parse("ready")).toBe("ready");
    expect(imageryJobStatusSchema.parse("failed")).toBe("failed");
    expect(() => imageryJobStatusSchema.parse("in_progress")).toThrow();
  });

  it("validates VisualizationPreset enum", () => {
    expect(visualizationPresetSchema.parse("true_color")).toBe("true_color");
    expect(visualizationPresetSchema.parse("false_color")).toBe("false_color");
    expect(visualizationPresetSchema.parse("vegetation")).toBe("vegetation");
    expect(visualizationPresetSchema.parse("water")).toBe("water");
    expect(visualizationPresetSchema.parse("urban")).toBe("urban");
    expect(visualizationPresetSchema.parse("sar_grayscale")).toBe("sar_grayscale");
    expect(visualizationPresetSchema.parse("sar_vv")).toBe("sar_vv");
    expect(visualizationPresetSchema.parse("sar_vh")).toBe("sar_vh");
    expect(() => visualizationPresetSchema.parse("infrared_custom")).toThrow();
  });

  it("validates ImageryFormat enum", () => {
    expect(imageryFormatSchema.parse("png")).toBe("png");
    expect(imageryFormatSchema.parse("jpeg")).toBe("jpeg");
    expect(imageryFormatSchema.parse("geotiff")).toBe("geotiff");
    expect(imageryFormatSchema.parse("cog")).toBe("cog");
    expect(() => imageryFormatSchema.parse("gif")).toThrow();
  });

  it("validates AlignmentStatus enum", () => {
    expect(alignmentStatusSchema.parse("aligned")).toBe("aligned");
    expect(alignmentStatusSchema.parse("approximately_aligned")).toBe("approximately_aligned");
    expect(alignmentStatusSchema.parse("requires_alignment")).toBe("requires_alignment");
    expect(alignmentStatusSchema.parse("incompatible")).toBe("incompatible");
    expect(alignmentStatusSchema.parse("unknown")).toBe("unknown");
    expect(() => alignmentStatusSchema.parse("perfect")).toThrow();
  });

  it("validates valid preview ImageryRequest", () => {
    const valid = imageryRequestSchema.parse({
      scene_id: "S2A_MSIL2A_20250101",
      aoi: samplePolygon,
      product_type: "map_preview",
      visualization_preset: "true_color",
      output_format: "png",
    });
    expect(valid.scene_id).toBe("S2A_MSIL2A_20250101");
    expect(valid.resampling_method).toBe("bilinear");
    expect(valid.map_projection).toBe("EPSG:3857");
  });

  it("validates valid analysis_raster ImageryRequest with GeoTIFF format", () => {
    const valid = imageryRequestSchema.parse({
      scene_id: "S2A_MSIL2A_20250101",
      aoi: samplePolygon,
      product_type: "analysis_raster",
      visualization_preset: "true_color",
      output_format: "geotiff",
    });
    expect(valid.product_type).toBe("analysis_raster");
    expect(valid.output_format).toBe("geotiff");
  });

  it("rejects analysis_raster with PNG output format", () => {
    expect(() =>
      imageryRequestSchema.parse({
        scene_id: "S2A_MSIL2A_20250101",
        aoi: samplePolygon,
        product_type: "analysis_raster",
        visualization_preset: "true_color",
        output_format: "png",
      }),
    ).toThrow(/analysis_raster product type requires geotiff or cog format/);
  });

  it("validates TemporalImageryRequest and enforces distinct scenes", () => {
    const valid = temporalImageryRequestSchema.parse({
      before_scene_id: "S2A_20250101",
      after_scene_id: "S2B_20250120",
      aoi: samplePolygon,
      before_preset: "true_color",
      after_preset: "false_color",
    });
    expect(valid.before_scene_id).toBe("S2A_20250101");
    expect(valid.after_scene_id).toBe("S2B_20250120");

    expect(() =>
      temporalImageryRequestSchema.parse({
        before_scene_id: "S2A_20250101",
        after_scene_id: "S2A_20250101",
        aoi: samplePolygon,
      }),
    ).toThrow(/distinct/);
  });

  it("validates ImageryAsset schema", () => {
    const asset = imageryAssetSchema.parse({
      asset_id: "ast-12345",
      scene_id: "S2A_20250101",
      product_type: "map_preview",
      format: "png",
      content_type: "image/png",
      width: 512,
      height: 512,
      resolution_meters: 10,
      bbox: [77.5, 12.9, 77.7, 13.1],
      crs: "EPSG:3857",
      bands: ["B04", "B03", "B02"],
      size_bytes: 45000,
      checksum: "abc123sha256",
      created_at: "2026-09-20T00:00:00Z",
      display_url: "/api/v1/imagery/assets/ast-12345",
      provider_id: "earth-search",
      data_origin: "real",
    });
    expect(asset.asset_id).toBe("ast-12345");
    expect(asset.width).toBe(512);
    expect(asset.data_origin).toBe("real");
  });

  it("validates TemporalImageryResponse schema", () => {
    const sampleAsset = {
      asset_id: "ast-1",
      scene_id: "S2A_20250101",
      product_type: "map_preview" as const,
      format: "png" as const,
      content_type: "image/png",
      width: 512,
      height: 512,
      resolution_meters: 10,
      bbox: [77.5, 12.9, 77.7, 13.1] as [number, number, number, number],
      crs: "EPSG:3857",
      bands: ["B04", "B03", "B02"],
      size_bytes: 45000,
      checksum: "abc123sha256",
      created_at: "2026-09-20T00:00:00Z",
      display_url: "/api/v1/imagery/assets/ast-1",
      provider_id: "earth-search",
      data_origin: "real" as const,
    };

    const resp = temporalImageryResponseSchema.parse({
      request_id: "req-temporal-1",
      pair_id: "pair-1",
      before_asset: sampleAsset,
      after_asset: { ...sampleAsset, asset_id: "ast-2", scene_id: "S2B_20250120" },
      alignment_status: "aligned",
      data_origin: "real",
    });
    expect(resp.request_id).toBe("req-temporal-1");
    expect(resp.alignment_status).toBe("aligned");
  });

  it("validates RasterMetadata schema", () => {
    const meta = rasterMetadataSchema.parse({
      crs: "EPSG:3857",
      bbox: [77.5, 12.9, 77.7, 13.1],
      width: 512,
      height: 512,
      pixel_size_x: 10.0,
      pixel_size_y: 10.0,
      band_count: 3,
      band_names: ["Red", "Green", "Blue"],
      data_type: "uint8",
      scene_id: "S2A_20250101",
      provider: "earth-search",
      collection: "sentinel-2-c1-l2a",
    });
    expect(meta.width).toBe(512);
    expect(meta.band_count).toBe(3);
  });
});
