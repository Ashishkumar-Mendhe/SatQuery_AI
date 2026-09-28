import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createAoiFromBounds } from "./aoi";
import { AOI_STORAGE_KEY, serializeStoredAoi } from "./aoi-storage";
import { useAoiDraft } from "./use-aoi-draft";

// Synthetic bounded geometry for storage behavior, not an analytical measurement.
const syntheticAoi = createAoiFromBounds([1, 1, 2, 2]);
beforeEach(() => localStorage.clear());
afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("AOI browser persistence", () => {
  it("restores validated geometry after mounting and clears the saved draft", () => {
    localStorage.setItem(AOI_STORAGE_KEY, serializeStoredAoi(syntheticAoi));
    const { result } = renderHook(useAoiDraft);
    expect(result.current.aoi?.bounds).toEqual([1, 1, 2, 2]);
    expect(result.current.persistenceState).toBe("restored");
    act(() => result.current.clearAoi());
    expect(result.current.aoi).toBeNull();
    expect(localStorage.getItem(AOI_STORAGE_KEY)).toBeNull();
  });

  it("discards corrupt data without creating a selection", () => {
    localStorage.setItem(AOI_STORAGE_KEY, "invalid JSON");
    const { result } = renderHook(useAoiDraft);
    expect(result.current.aoi).toBeNull();
    expect(result.current.persistenceMessage).toMatch(/corrupt/);
    expect(localStorage.getItem(AOI_STORAGE_KEY)).toBeNull();
  });

  it("keeps the AOI usable when a quota failure prevents saving", () => {
    const { result } = renderHook(useAoiDraft);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("Synthetic quota failure", "QuotaExceededError");
    });
    act(() => result.current.setAoi(syntheticAoi));
    expect(result.current.aoi).toEqual(syntheticAoi);
    expect(result.current.persistenceState).toBe("unavailable");
    expect(result.current.persistenceMessage).toMatch(/older draft/);
  });

  it("reports denied storage access without breaking the local selection", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("Synthetic denied access");
    });
    const { result } = renderHook(useAoiDraft);
    expect(result.current.persistenceState).toBe("unavailable");
    act(() => result.current.setAoi(syntheticAoi));
    expect(result.current.aoi?.bounds).toEqual(syntheticAoi.bounds);
  });
});
