"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { BrandMark } from "@/components/brand-mark";
import { Icon } from "@/components/icon";
import { deleteSavedAoi, fetchSavedAois, type PersistedAoi } from "@/lib/persistence-client";

export default function SavedAoisPage() {
  const [aois, setAois] = useState<PersistedAoi[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAois = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSavedAois();
      setAois(data);
    } catch {
      setError("Could not load saved Areas of Interest. Check backend connection.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAois();
  }, [loadAois]);

  const handleDelete = async (id: string) => {
    const ok = await deleteSavedAoi(id);
    if (ok) {
      setAois((prev) => prev.filter((a) => a.id !== id));
    }
  };

  return (
    <div className="min-h-screen bg-[#080d14] text-[#edf3fa] flex flex-col">
      <header className="flex items-center justify-between px-6 py-4 border-b border-[#273649] bg-[#0b121b]">
        <div className="flex items-center gap-4">
          <BrandMark href="/" />
          <span className="text-xs text-[#74859a] uppercase font-bold tracking-wider">
            Saved Areas of Interest
          </span>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/workspace"
            className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-semibold text-[#8ae6f2] bg-[#62d8e8]/10 border border-[#62d8e8]/30 rounded-md hover:bg-[#62d8e8]/20 transition"
          >
            <Icon name="map" />
            <span>Open Workspace</span>
          </Link>
        </div>
      </header>

      <main className="flex-1 max-w-5xl w-full mx-auto p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-[#edf3fa]">Saved Areas of Interest</h1>
            <p className="text-xs text-[#a4b2c3] mt-1">
              Geodesically validated polygons with geodesic area calculation, bounds, and GeoJSON
              geometry.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadAois()}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-medium text-[#a4b2c3] border border-[#273649] rounded-md hover:border-[#62d8e8] hover:text-[#edf3fa] transition disabled:opacity-50"
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>

        {loading ? (
          <div className="p-12 text-center text-[#74859a] text-sm">
            Loading saved AOIs from database…
          </div>
        ) : error ? (
          <div className="p-6 border border-[#ff9e9e]/30 bg-[#ff9e9e]/10 rounded-lg text-[#ff9e9e] text-xs">
            <p>{error}</p>
            <button
              type="button"
              onClick={() => void loadAois()}
              className="mt-3 px-3 py-1 bg-[#ff9e9e]/20 rounded font-semibold text-[#edf3fa]"
            >
              Retry
            </button>
          </div>
        ) : aois.length === 0 ? (
          <div className="p-16 border border-[#273649] border-dashed rounded-xl text-center">
            <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-[#101925] flex items-center justify-center text-[#62d8e8]">
              <Icon name="target" />
            </div>
            <h3 className="text-sm font-semibold text-[#edf3fa]">No saved AOIs in database</h3>
            <p className="text-xs text-[#74859a] max-w-sm mx-auto mt-1 mb-4">
              Draw or import an Area of Interest on the workspace map to define your study boundary
              and discover satellite scenes.
            </p>
            <Link
              href="/workspace"
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-[#041318] bg-[#62d8e8] rounded-md hover:bg-[#8ae6f2] transition"
            >
              <Icon name="map" />
              <span>Draw AOI in Workspace</span>
            </Link>
          </div>
        ) : (
          <div className="grid gap-3">
            {aois.map((aoi) => (
              <div
                key={aoi.id}
                className="p-4 border border-[#273649] bg-[#101925] rounded-lg flex items-center justify-between hover:border-[#385068] transition"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-[#73ddb1]/10 text-[#73ddb1] border border-[#73ddb1]/30">
                      Authoritative Valid
                    </span>
                    <span className="text-xs text-[#74859a]">
                      Created {new Date(aoi.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold text-[#edf3fa] mt-1">{aoi.name}</h3>
                  <div className="flex items-center gap-4 text-xs text-[#a4b2c3] mt-1">
                    <span>
                      Area:{" "}
                      <strong className="text-[#edf3fa]">
                        {aoi.area_sqkm ? aoi.area_sqkm.toFixed(3) : "—"} km²
                      </strong>
                    </span>
                    <span>Source: {aoi.source}</span>
                    <span>Vertices: {aoi.geometry?.coordinates?.[0]?.length ?? 0}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Link
                    href="/workspace"
                    className="px-3 py-1.5 text-xs font-semibold text-[#62d8e8] border border-[#62d8e8]/30 rounded hover:bg-[#62d8e8]/10 transition"
                  >
                    Open in Map
                  </Link>
                  <button
                    type="button"
                    onClick={() => void handleDelete(aoi.id)}
                    className="p-1.5 text-[#ff9e9e] hover:bg-[#ff9e9e]/10 rounded transition"
                    title="Delete AOI"
                  >
                    <Icon name="close" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
