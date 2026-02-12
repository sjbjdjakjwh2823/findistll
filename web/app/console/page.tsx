"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { BackgroundBeams } from "@/components/ui/background-beams";
import { ArrowLeft, ServerCog, Database, MessagesSquare, RefreshCcw } from "lucide-react";
import type { JsonRecord } from "@/lib/types";

const API_BASE = "/api/proxy";

type ConsoleModel = {
  id: string;
  name: string;
  model: string;
};

export default function ConsolePage() {
  const [models, setModels] = useState<ConsoleModel[]>([]);
  const [modelForm, setModelForm] = useState({
    name: "Local Qwen",
    provider: "openai",
    base_url: "http://localhost:11434/v1",
    model: "qwen2.5:7b-instruct-q4_K_M",
    purpose: "llm",
    is_default: true,
  });
  const [modelStatus, setModelStatus] = useState<string | null>(null);

  const [llmPrompt, setLlmPrompt] = useState("Summarize the key risk drivers for a tech-heavy portfolio.");
  const [llmResult, setLlmResult] = useState<JsonRecord | null>(null);
  const [llmRunId, setLlmRunId] = useState<string | null>(null);
  const [llmError, setLlmError] = useState<string | null>(null);

  const [ragQuery, setRagQuery] = useState("FEDFUNDS rate change impact on growth stocks");
  const [ragResult, setRagResult] = useState<JsonRecord | null>(null);
  const [ragError, setRagError] = useState<string | null>(null);

  const loadModels = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/console/models`);
      const data = await res.json();
      const items = (data.models || []) as Array<Partial<ConsoleModel>>;
      setModels(
        items.map((m, idx) => ({
          id: String(m.id ?? idx),
          name: String(m.name ?? ""),
          model: String(m.model ?? ""),
        }))
      );
    } catch (e: unknown) {
      setModelStatus(e instanceof Error ? e.message : "Failed to load models");
    }
  };

  useEffect(() => {
    loadModels();
  }, []);

  const saveModel = async () => {
    setModelStatus(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/console/models`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(modelForm),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Failed to save model");
      }
      setModelStatus(`Saved: ${data.model_id}`);
      loadModels();
    } catch (e: unknown) {
      setModelStatus(e instanceof Error ? e.message : "Failed to save model");
    }
  };

  const runLlm = async () => {
    setLlmError(null);
    setLlmResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/console/llm/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: llmPrompt, model: modelForm.model }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "LLM run failed");
      }
      setLlmRunId(data.run_id || null);
      setLlmResult(data.result);
    } catch (e: unknown) {
      setLlmError(e instanceof Error ? e.message : "LLM run failed");
    }
  };

  const runRag = async () => {
    setRagError(null);
    setRagResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/console/rag/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: ragQuery, top_k: 5 }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "RAG query failed");
      }
      setRagResult(data);
    } catch (e: unknown) {
      setRagError(e instanceof Error ? e.message : "RAG query failed");
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden">
      <BackgroundBeams className="z-0" />
      <div className="relative z-10 mx-auto w-full max-w-6xl px-6 pb-20 pt-10 md:pt-16 text-white">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ServerCog className="h-6 w-6 text-cyan-300" />
            <h1 className="text-3xl font-semibold">RAG / LLM Console</h1>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/mlops"
              className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200 hover:bg-white/10"
            >
              MLOps
            </Link>
            <Link
              href="/lakehouse"
              className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200 hover:bg-white/10"
            >
              Lakehouse
            </Link>
            <Link
              href="/"
              className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200 hover:bg-white/10"
            >
              <ArrowLeft className="h-3 w-3" /> Back
            </Link>
          </div>
        </div>

        <section className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-black/40 p-6">
            <div className="mb-3 flex items-center gap-2 text-sm text-slate-200">
              <Database className="h-4 w-4" /> Model Registry
            </div>
            <div className="space-y-3 text-xs text-slate-300">
              <input
                className="w-full rounded-md border border-white/10 bg-black/50 px-3 py-2"
                value={modelForm.name}
                onChange={(e) => setModelForm({ ...modelForm, name: e.target.value })}
                placeholder="Model name"
              />
              <input
                className="w-full rounded-md border border-white/10 bg-black/50 px-3 py-2"
                value={modelForm.model}
                onChange={(e) => setModelForm({ ...modelForm, model: e.target.value })}
                placeholder="Model ID"
              />
              <input
                className="w-full rounded-md border border-white/10 bg-black/50 px-3 py-2"
                value={modelForm.base_url}
                onChange={(e) => setModelForm({ ...modelForm, base_url: e.target.value })}
                placeholder="Base URL"
              />
              <button
                onClick={saveModel}
                className="inline-flex items-center gap-2 rounded-full bg-cyan-400/20 px-3 py-1.5 text-[11px] font-semibold text-cyan-100 ring-1 ring-cyan-400/40"
              >
                Save Model
              </button>
              {modelStatus && <div className="text-[11px] text-emerald-300">{modelStatus}</div>}
            </div>
            <div className="mt-4">
              <div className="mb-2 flex items-center justify-between text-[11px] text-slate-400">
                <span>Registered</span>
                <button onClick={loadModels} className="inline-flex items-center gap-1 text-slate-300">
                  <RefreshCcw className="h-3 w-3" /> Refresh
                </button>
              </div>
                <div className="space-y-2 text-[11px] text-slate-300">
                {models.map((m) => (
                  <div key={String(m.id)} className="rounded-md border border-white/10 bg-black/40 px-3 py-2">
                    <div className="font-semibold">{String(m.name)}</div>
                    <div className="text-slate-400">{String(m.model)}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-black/40 p-6">
            <div className="mb-3 flex items-center gap-2 text-sm text-slate-200">
              <MessagesSquare className="h-4 w-4" /> LLM Run
            </div>
            <textarea
              className="h-32 w-full rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
              value={llmPrompt}
              onChange={(e) => setLlmPrompt(e.target.value)}
            />
            <button
              onClick={runLlm}
              className="mt-3 inline-flex items-center gap-2 rounded-full bg-emerald-400/20 px-3 py-1.5 text-[11px] font-semibold text-emerald-100 ring-1 ring-emerald-400/40"
            >
              Run LLM
            </button>
            {llmError && <div className="mt-2 text-[11px] text-rose-300">{llmError}</div>}
            {llmRunId && (
              <div className="mt-2 text-[11px] text-emerald-300">
                Run ID: {llmRunId} (Open <a href="/mlops" className="underline">MLOps</a>)
              </div>
            )}
            {llmResult && (
              <pre className="mt-3 max-h-64 overflow-auto rounded-md border border-white/10 bg-black/50 p-3 text-[11px] text-slate-200">
{JSON.stringify(llmResult, null, 2)}
              </pre>
            )}
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 flex items-center gap-2 text-sm text-slate-200">
            <MessagesSquare className="h-4 w-4" /> RAG Query
          </div>
          <div className="flex flex-col gap-3 md:flex-row">
            <input
              className="w-full rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
              value={ragQuery}
              onChange={(e) => setRagQuery(e.target.value)}
            />
            <button
              onClick={runRag}
              className="inline-flex items-center gap-2 rounded-full bg-sky-400/20 px-3 py-1.5 text-[11px] font-semibold text-sky-100 ring-1 ring-sky-400/40"
            >
              Run RAG
            </button>
          </div>
          {ragError && <div className="mt-2 text-[11px] text-rose-300">{ragError}</div>}
          {Boolean(ragResult?.delta_source_version) && (
            <div className="mt-2 text-[11px] text-cyan-300">
              Delta Source Version: {String(ragResult?.delta_source_version)}
            </div>
          )}
          {ragResult && (
            <pre className="mt-3 max-h-64 overflow-auto rounded-md border border-white/10 bg-black/50 p-3 text-[11px] text-slate-200">
{JSON.stringify(ragResult, null, 2)}
            </pre>
          )}
        </section>
      </div>
    </main>
  );
}
