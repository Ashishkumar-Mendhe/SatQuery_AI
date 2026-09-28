"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { BrandMark } from "@/components/brand-mark";
import { Icon } from "@/components/icon";
import {
  deleteAnalysisHistory,
  fetchAnalysisHistory,
  type PersistedHistory,
} from "@/lib/persistence-client";

export default function HistoryPage() {
  const [history, setHistory] = useState<PersistedHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAnalysisHistory();
      setHistory(data);
    } catch {
      setError("Could not load analysis history. Check service status.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const handleDelete = async (id: string) => {
    const ok = await deleteAnalysisHistory(id);
    if (ok) {
      setHistory((prev) => prev.filter((item) => item.id !== id));
    }
  };

  return (
    <div className="min-h-screen bg-[#080d14] text-[#edf3fa] flex flex-col">
      <header className="flex items-center justify-between px-6 py-4 border-b border-[#273649] bg-[#0b121b]">
        <div className="flex items-center gap-4">
          <BrandMark href="/" />
          <span className="text-xs text-[#74859a] uppercase font-bold tracking-wider">
            Analysis History
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
            <h1 className="text-xl font-bold text-[#edf3fa]">Analysis & Query History</h1>
            <p className="text-xs text-[#a4b2c3] mt-1">
              Immutable historical runs, bi-temporal change measurements, and visual question
              answers.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadHistory()}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-medium text-[#a4b2c3] border border-[#273649] rounded-md hover:border-[#62d8e8] hover:text-[#edf3fa] transition disabled:opacity-50"
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>

        {loading ? (
          <div className="p-12 text-center text-[#74859a] text-sm">
            Loading analysis history records from database…
          </div>
        ) : error ? (
          <div className="p-6 border border-[#ff9e9e]/30 bg-[#ff9e9e]/10 rounded-lg text-[#ff9e9e] text-xs">
            <p>{error}</p>
            <button
              type="button"
              onClick={() => void loadHistory()}
              className="mt-3 px-3 py-1 bg-[#ff9e9e]/20 rounded font-semibold text-[#edf3fa]"
            >
              Retry
            </button>
          </div>
        ) : history.length === 0 ? (
          <div className="p-16 border border-[#273649] border-dashed rounded-xl text-center">
            <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-[#101925] flex items-center justify-center text-[#62d8e8]">
              <Icon name="history" />
            </div>
            <h3 className="text-sm font-semibold text-[#edf3fa]">No analyses recorded yet</h3>
            <p className="text-xs text-[#74859a] max-w-sm mx-auto mt-1 mb-4">
              When you run change detection, spectral index differences, or visual QA in the
              workspace, completed findings are automatically saved to your persistent history.
            </p>
            <Link
              href="/workspace"
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-[#041318] bg-[#62d8e8] rounded-md hover:bg-[#8ae6f2] transition"
            >
              <Icon name="spark" />
              <span>Launch an Analysis</span>
            </Link>
          </div>
        ) : (
          <div className="grid gap-3">
            {history.map((item) => (
              <div
                key={item.id}
                className="p-4 border border-[#273649] bg-[#101925] rounded-lg flex items-center justify-between hover:border-[#385068] transition"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-[#62d8e8]/10 text-[#62d8e8] border border-[#62d8e8]/30">
                      {item.analysis_type.replace("_", " ")}
                    </span>
                    <span className="text-xs text-[#74859a]">
                      {new Date(item.created_at).toLocaleString()}
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold text-[#edf3fa] mt-1">{item.title}</h3>
                  {item.query_text && (
                    <p className="text-xs text-[#a4b2c3] mt-0.5 italic">“{item.query_text}”</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Link
                    href="/workspace"
                    className="px-3 py-1.5 text-xs font-semibold text-[#62d8e8] border border-[#62d8e8]/30 rounded hover:bg-[#62d8e8]/10 transition"
                  >
                    Open
                  </Link>
                  <button
                    type="button"
                    onClick={() => void handleDelete(item.id)}
                    className="p-1.5 text-[#ff9e9e] hover:bg-[#ff9e9e]/10 rounded transition"
                    title="Delete record"
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
