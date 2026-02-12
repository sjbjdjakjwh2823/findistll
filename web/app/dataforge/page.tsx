"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { BackgroundBeams } from "@/components/ui/background-beams";
import { QueueList } from "@/components/dataforge/QueueList";
import { ReviewInterface } from "@/components/dataforge/ReviewInterface";
import { StatsPanel } from "@/components/dataforge/StatsPanel";
import type { JsonRecord } from "@/lib/types";
import type { Sample } from "@/lib/dataforge_types";
import { 
  Factory, 
  FileUp, 
  Sparkles, 
  CheckCircle2,
  ArrowLeft,
  BarChart3,
  ListTodo
} from "lucide-react";

// API base URL - uses Next.js rewrites or direct backend
const API_BASE = "/api/proxy";

interface QueueStats {
  total_pending: number;
  total_in_review: number;
  total_approved: number;
  total_corrected: number;
  total_rejected: number;
  by_template_type: Record<string, Record<string, number>>;
  avg_confidence_pending: number | null;
}

interface IngestStats {
  total_documents?: number;
  by_status?: Record<string, number>;
}

export default function DataForgePage() {
  const [activeTab, setActiveTab] = useState<"queue" | "review" | "stats" | "ingest">("queue");
  const [queueStats, setQueueStats] = useState<QueueStats | null>(null);
  const [currentSample, setCurrentSample] = useState<Sample | null>(null);
  const [annotatorId, setAnnotatorId] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [ingestStats, setIngestStats] = useState<IngestStats | null>(null);
  const [ingestDocs, setIngestDocs] = useState<JsonRecord[] | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  // Load annotator ID from localStorage
  useEffect(() => {
    const stored = localStorage.getItem("dataforge_annotator_id");
    if (stored) {
      setAnnotatorId(stored);
    } else {
      // Generate a simple ID for demo
      const newId = `annotator_${Date.now().toString(36)}`;
      localStorage.setItem("dataforge_annotator_id", newId);
      setAnnotatorId(newId);
    }
  }, []);

  // Fetch queue stats
  useEffect(() => {
    fetchQueueStats();
    const interval = setInterval(() => {
      fetchQueueStats();
    }, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    fetchIngestStats();
    fetchIngestDocs();
    const interval = setInterval(() => {
      fetchIngestStats();
      fetchIngestDocs();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchQueueStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/annotate/stats/queue`);
      if (res.ok) {
        const data = await res.json();
        setQueueStats(data);
      }
    } catch (e) {
      console.error("Failed to fetch queue stats:", e);
    }
  };

  const fetchIngestStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/ingest/stats`);
      if (res.ok) {
        const data = (await res.json()) as IngestStats;
        setIngestStats(data || null);
      }
    } catch (e) {
      console.error("Failed to fetch ingest stats:", e);
    }
  };

  const fetchIngestDocs = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/ingest/documents?limit=30`);
      if (res.ok) {
        const data = await res.json();
        setIngestDocs(data.documents || []);
      }
    } catch (e) {
      console.error("Failed to fetch ingest documents:", e);
    }
  };

  const uploadAsync = async () => {
    if (!uploadFile) return;
    setUploadStatus("Uploading...");
    try {
      const form = new FormData();
      form.append("file", uploadFile);
      const res = await fetch(`${API_BASE}/api/v1/ingest/upload-async`, {
        method: "POST",
        body: form,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || "upload failed");
      setUploadStatus(`Queued: ${data.document_id}`);
      setUploadFile(null);
      fetchIngestStats();
      fetchIngestDocs();
    } catch (e: unknown) {
      setUploadStatus(`Failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const fetchNextSample = async () => {
    if (!annotatorId) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/annotate/next?annotator_id=${annotatorId}`);
      if (res.ok) {
        const data = await res.json();
        if (data.has_sample) {
          setCurrentSample({
            id: data.sample_id,
            template_type: data.template_type,
            generated_content: data.generated_content,
            confidence_score: data.confidence_score,
            raw_documents: {
              source: data.source,
              ticker: data.ticker,
              raw_content: data.raw_content
            }
          });
          setActiveTab("review");
        } else {
          alert("No samples in queue!");
        }
      }
    } catch (e) {
      console.error("Failed to fetch next sample:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleAnnotation = async (action: string, corrections?: JsonRecord, reasoning?: string) => {
    if (!currentSample || !annotatorId) return;
    
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/annotate/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sample_id: currentSample.id,
          annotator_id: annotatorId,
          action,
          corrections,
          reasoning,
        }),
      });
      
      if (res.ok) {
        setCurrentSample(null);
        fetchQueueStats();
        // Auto-fetch next
        fetchNextSample();
      } else {
        alert("Failed to submit annotation");
      }
    } catch (e) {
      console.error("Failed to submit annotation:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleSkip = async () => {
    if (!currentSample || !annotatorId) return;
    
    try {
      await fetch(`${API_BASE}/api/v1/annotate/skip/${currentSample.id}?annotator_id=${annotatorId}`, {
        method: "POST",
      });
      setCurrentSample(null);
      fetchNextSample();
    } catch (e) {
      console.error("Failed to skip sample:", e);
    }
  };

  return (
    <main className="min-h-screen bg-black text-white relative overflow-hidden">
      <BackgroundBeams className="z-0 opacity-30" />
      
      <div className="relative z-10 p-6 max-w-7xl mx-auto">
        {/* Header */}
        <header className="mb-8 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="p-2 hover:bg-white/5 rounded-lg transition"
              title="Back to Dashboard"
            >
              <ArrowLeft className="h-5 w-5 text-neutral-400" />
            </Link>
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-3">
                <Factory className="h-8 w-8 text-amber-500" />
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-amber-400 to-orange-600">
                  DataForge
                </span>
              </h1>
              <p className="text-neutral-500 text-sm mt-1">
                Phase 1: Data Production Factory — HITL Review Interface
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="text-right text-xs">
              <div className="text-neutral-500">Annotator ID</div>
              <div className="font-mono text-amber-400">{annotatorId.slice(0, 16)}...</div>
            </div>
          </div>
        </header>

        {/* Quick Stats Bar */}
        {queueStats && (
          <div className="grid grid-cols-5 gap-4 mb-6">
            <StatCard 
              label="Pending" 
              value={queueStats.total_pending} 
              color="text-amber-400"
              icon={<ListTodo className="h-4 w-4" />}
            />
            <StatCard 
              label="In Review" 
              value={queueStats.total_in_review} 
              color="text-blue-400"
              icon={<Sparkles className="h-4 w-4" />}
            />
            <StatCard 
              label="Approved" 
              value={queueStats.total_approved} 
              color="text-emerald-400"
              icon={<CheckCircle2 className="h-4 w-4" />}
            />
            <StatCard 
              label="Corrected" 
              value={queueStats.total_corrected} 
              color="text-cyan-400"
              icon={<FileUp className="h-4 w-4" />}
            />
            <StatCard 
              label="Avg Confidence" 
              value={queueStats.avg_confidence_pending 
                ? `${(queueStats.avg_confidence_pending * 100).toFixed(0)}%` 
                : "—"
              } 
              color="text-purple-400"
              icon={<BarChart3 className="h-4 w-4" />}
            />
          </div>
        )}

        {/* Tab Navigation */}
        <div className="flex gap-2 mb-6">
          <TabButton 
            active={activeTab === "queue"} 
            onClick={() => setActiveTab("queue")}
          >
            <ListTodo className="h-4 w-4" /> Queue
          </TabButton>
          <TabButton 
            active={activeTab === "review"} 
            onClick={() => setActiveTab("review")}
          >
            <Sparkles className="h-4 w-4" /> Review
          </TabButton>
          <TabButton 
            active={activeTab === "stats"} 
            onClick={() => setActiveTab("stats")}
          >
            <BarChart3 className="h-4 w-4" /> Stats
          </TabButton>
          <TabButton
            active={activeTab === "ingest"}
            onClick={() => setActiveTab("ingest")}
          >
            <FileUp className="h-4 w-4" /> Ingest
          </TabButton>
          
          <div className="flex-1" />
          
          <button
            onClick={fetchNextSample}
            disabled={loading}
            className="px-4 py-2 bg-amber-500/20 border border-amber-500/30 rounded-lg text-amber-400 font-bold text-sm hover:bg-amber-500/30 transition disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? (
              <>Loading...</>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Start Reviewing
              </>
            )}
          </button>
        </div>

        {/* Content */}
        <div className="bg-neutral-900/50 border border-neutral-800 rounded-xl p-6 min-h-[600px]">
          {activeTab === "queue" && (
            <QueueList 
              apiBase={API_BASE} 
              onSelectSample={(sample) => {
                setCurrentSample(sample);
                setActiveTab("review");
              }}
            />
          )}
          
          {activeTab === "review" && (
            <ReviewInterface
              sample={currentSample}
              loading={loading}
              onApprove={() => handleAnnotation("approved")}
              onCorrect={(corrections, reasoning) => handleAnnotation("corrected", corrections, reasoning)}
              onReject={(reasoning) => handleAnnotation("rejected", undefined, reasoning)}
              onSkip={handleSkip}
              onFetchNext={fetchNextSample}
            />
          )}
          
          {activeTab === "stats" && (
            <StatsPanel apiBase={API_BASE} annotatorId={annotatorId} />
          )}

          {activeTab === "ingest" && (
            <div className="space-y-4">
              <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
                <div className="text-sm font-semibold text-white mb-2">Async Upload</div>
                <div className="text-xs text-neutral-400 mb-3">
                  대용량 데이터는 UI에서 업로드 후 큐로 넘기고, 실제 처리는 터미널(worker)에서 실행됩니다.
                </div>
                <input
                  type="file"
                  className="text-xs text-neutral-300"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                />
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={uploadAsync}
                    className="px-4 py-2 rounded-lg bg-amber-500/20 border border-amber-500/30 text-amber-300 text-sm hover:bg-amber-500/30 transition"
                  >
                    Queue Upload
                  </button>
                  <button
                    onClick={() => {
                      fetchIngestStats();
                      fetchIngestDocs();
                    }}
                    className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-neutral-200 text-sm hover:bg-white/10 transition"
                  >
                    Refresh
                  </button>
                </div>
                {uploadStatus && <div className="mt-2 text-xs text-neutral-300">{uploadStatus}</div>}
              </div>

              <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
                <div className="text-sm font-semibold text-white mb-2">Ingest Status</div>
                <div className="grid grid-cols-3 gap-3 text-xs text-neutral-400">
                  <div>Total: {ingestStats?.total_documents ?? "-"}</div>
                  <div>Queued: {ingestStats?.by_status?.queued ?? 0}</div>
                  <div>Processing: {ingestStats?.by_status?.processing ?? 0}</div>
                  <div>Completed: {ingestStats?.by_status?.completed ?? 0}</div>
                  <div>Failed: {ingestStats?.by_status?.failed ?? 0}</div>
                  <div>Pending: {ingestStats?.by_status?.pending ?? 0}</div>
                </div>
              </div>

              <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
                <div className="text-sm font-semibold text-white mb-2">Recent Documents</div>
                {ingestDocs && ingestDocs.length === 0 && (
                  <div className="text-xs text-neutral-400">No documents yet.</div>
                )}
                {ingestDocs && ingestDocs.length > 0 && (
                  <div className="mt-2 max-h-[320px] overflow-auto text-xs text-neutral-300">
                    <div className="grid grid-cols-4 gap-2 font-semibold text-neutral-400 mb-2">
                      <div>Doc ID</div>
                      <div>Source</div>
                      <div>Status</div>
                      <div>Ingested</div>
                    </div>
                    {ingestDocs.map((doc) => (
                      <div key={String(doc.id ?? "")} className="grid grid-cols-4 gap-2 border-b border-white/5 py-2">
                        <div className="truncate">{String(doc.id ?? "")}</div>
                        <div className="truncate">{String(doc.source ?? "")}</div>
                        <div className="truncate">{String(doc.processing_status ?? "")}</div>
                        <div className="truncate">{String(doc.ingested_at ?? "")}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

// Helper Components

function StatCard({ label, value, color, icon }: { 
  label: string; 
  value: number | string; 
  color: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="bg-neutral-900/50 border border-neutral-800 rounded-lg p-4">
      <div className="flex items-center gap-2 text-neutral-500 text-xs mb-1">
        {icon}
        {label}
      </div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
    </div>
  );
}

function TabButton({ active, onClick, children }: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition ${
        active 
          ? "bg-white/10 text-white" 
          : "text-neutral-500 hover:text-white hover:bg-white/5"
      }`}
    >
      {children}
    </button>
  );
}
