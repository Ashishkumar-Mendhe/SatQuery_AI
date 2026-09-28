"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BrandMark } from "@/components/brand-mark";
import { Icon } from "@/components/icon";

interface ReportItem {
  id: string;
  title: string;
  created_at: string;
  pdf_url?: string;
  json_url?: string;
}

export default function ReportsPage() {
  const [reports, setReports] = useState<ReportItem[]>([]);

  useEffect(() => {
    // In local development, check if there are cached snapshots in memory or localStorage
    const saved = localStorage.getItem("satquery.recent_report");
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as ReportItem;
        setReports([parsed]);
      } catch {
        // ignore
      }
    }
  }, []);

  return (
    <div className="min-h-screen bg-[#080d14] text-[#edf3fa] flex flex-col">
      <header className="flex items-center justify-between px-6 py-4 border-b border-[#273649] bg-[#0b121b]">
        <div className="flex items-center gap-4">
          <BrandMark href="/" />
          <span className="text-xs text-[#74859a] uppercase font-bold tracking-wider">
            Reports &amp; Dossiers
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
            <h1 className="text-xl font-bold text-[#edf3fa]">
              Evidence-Based Reports &amp; Dossiers
            </h1>
            <p className="text-xs text-[#a4b2c3] mt-1">
              Deterministic, audit-ready ReportLab PDF documents and immutable JSON snapshots with
              SHA-256 integrity verification.
            </p>
          </div>
        </div>

        {reports.length === 0 ? (
          <div className="p-16 border border-[#273649] border-dashed rounded-xl text-center">
            <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-[#101925] flex items-center justify-center text-[#62d8e8]">
              <Icon name="report" />
            </div>
            <h3 className="text-sm font-semibold text-[#edf3fa]">
              No report dossiers generated yet
            </h3>
            <p className="text-xs text-[#74859a] max-w-sm mx-auto mt-1 mb-4">
              When you perform change detection, multimodal SAR fusion, or visual question
              answering, click <strong>Export Report Dossier</strong> in the workspace to produce
              print-ready PDF and portable JSON reports.
            </p>
            <Link
              href="/workspace"
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-[#041318] bg-[#62d8e8] rounded-md hover:bg-[#8ae6f2] transition"
            >
              <Icon name="spark" />
              <span>Go to Workspace &amp; Export</span>
            </Link>
          </div>
        ) : (
          <div className="grid gap-3">
            {reports.map((rep) => (
              <div
                key={rep.id}
                className="p-4 border border-[#273649] bg-[#101925] rounded-lg flex items-center justify-between hover:border-[#385068] transition"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-[#73ddb1]/10 text-[#73ddb1] border border-[#73ddb1]/30">
                      Generated
                    </span>
                    <span className="text-xs text-[#74859a]">
                      {new Date(rep.created_at).toLocaleString()}
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold text-[#edf3fa] mt-1">{rep.title}</h3>
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={`/api/v1/reports/${rep.id}/download/pdf`}
                    target="_blank"
                    rel="noreferrer"
                    className="px-3 py-1.5 text-xs font-semibold text-[#8ae6f2] bg-[#62d8e8]/10 border border-[#62d8e8]/30 rounded hover:bg-[#62d8e8]/20 transition"
                  >
                    Download PDF
                  </a>
                  <a
                    href={`/api/v1/reports/${rep.id}/download/json`}
                    target="_blank"
                    rel="noreferrer"
                    className="px-3 py-1.5 text-xs font-semibold text-[#a4b2c3] border border-[#273649] rounded hover:border-[#62d8e8] hover:text-[#edf3fa] transition"
                  >
                    JSON Snapshot
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
