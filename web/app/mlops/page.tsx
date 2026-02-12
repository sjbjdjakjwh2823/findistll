"use client";

import React, { useState } from "react";
import Link from "next/link";
import { BackgroundBeams } from "@/components/ui/background-beams";
import type { JsonRecord } from "@/lib/types";

const API_BASE = "/api/proxy";

export default function MlopsPage() {
  const [experiments, setExperiments] = useState<JsonRecord[]>([]);
  const [models, setModels] = useState<JsonRecord[]>([]);
  const [modelName, setModelName] = useState("preciso-default");
  const [version, setVersion] = useState("1");
  const [stage, setStage] = useState("Staging");
  const [lastAction, setLastAction] = useState<JsonRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [datasetVersionId, setDatasetVersionId] = useState("");
  const [localModelPath, setLocalModelPath] = useState("");
  const [trainingNotes, setTrainingNotes] = useState("");
  const [trainingArgsText, setTrainingArgsText] = useState(
    '{"epochs":1,"batch_size":1,"grad_accum":8,"learning_rate":0.0002,"max_length":1024,"lora_r":8,"lora_alpha":16,"lora_dropout":0.05}'
  );
  const [trainingResult, setTrainingResult] = useState<JsonRecord | null>(null);
  const [trainingErr, setTrainingErr] = useState<string | null>(null);
  const [autoTrainEnabled, setAutoTrainEnabled] = useState<boolean | null>(null);
  const [autoTrainErr, setAutoTrainErr] = useState<string | null>(null);
  const [datasetVersions, setDatasetVersions] = useState<JsonRecord[]>([]);
  const [datasetName, setDatasetName] = useState("");
  const [datasetErr, setDatasetErr] = useState<string | null>(null);
  const [servingErr, setServingErr] = useState<string | null>(null);

  const loadExperiments = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/mlflow/experiments`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "experiments failed");
      setExperiments(data.experiments || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "experiments failed");
    }
  };

  const loadModels = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/console/models`);
      const data = await res.json();
      if (res.ok) {
        setModels(data.models || []);
        if (!modelName && data.models?.[0]?.model) {
          setModelName(String(data.models[0].model));
        }
      }
    } catch {
      // best-effort
    }
  };

  const loadAutoTrain = async () => {
    setAutoTrainErr(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/training/auto`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "auto status failed");
      setAutoTrainEnabled(Boolean(data.enabled));
    } catch (e: unknown) {
      setAutoTrainErr(e instanceof Error ? e.message : "auto status failed");
    }
  };

  const toggleAutoTrain = async () => {
    if (autoTrainEnabled === null) return;
    setAutoTrainErr(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/training/auto`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !autoTrainEnabled }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "auto update failed");
      setAutoTrainEnabled(Boolean(data.enabled));
    } catch (e: unknown) {
      setAutoTrainErr(e instanceof Error ? e.message : "auto update failed");
    }
  };

  const loadDatasetVersions = async () => {
    setDatasetErr(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/datasets/versions?limit=200`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "datasets failed");
      setDatasetVersions(data.versions || []);
    } catch (e: unknown) {
      setDatasetErr(e instanceof Error ? e.message : "datasets failed");
    }
  };

  const createDataset = async () => {
    setDatasetErr(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/datasets/versions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: datasetName || null }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "create failed");
      setDatasetName("");
      await loadDatasetVersions();
      if (data?.version?.id) {
        setDatasetVersionId(String(data.version.id));
      }
    } catch (e: unknown) {
      setDatasetErr(e instanceof Error ? e.message : "create failed");
    }
  };

  const setServingModel = async (modelId: string) => {
    setServingErr(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/console/models/default`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: modelId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "set default failed");
      await loadModels();
    } catch (e: unknown) {
      setServingErr(e instanceof Error ? e.message : "set default failed");
    }
  };
  const sealDataset = async (id: string) => {
    setDatasetErr(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/datasets/versions/${encodeURIComponent(id)}/seal`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "seal failed");
      await loadDatasetVersions();
    } catch (e: unknown) {
      setDatasetErr(e instanceof Error ? e.message : "seal failed");
    }
  };

  const promote = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/mlflow/models/${encodeURIComponent(modelName)}/promote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version, stage }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "promote failed");
      setLastAction(data.promotion);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "promote failed");
    }
  };

  const runTraining = async () => {
    setTrainingErr(null);
    setTrainingResult(null);
    if (!datasetVersionId.trim()) {
      setTrainingErr("dataset_version_id is required.");
      return;
    }
    try {
      const trainingArgs = trainingArgsText.trim()
        ? JSON.parse(trainingArgsText)
        : null;
      const res = await fetch(`${API_BASE}/api/v1/training/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dataset_version_id: datasetVersionId.trim(),
          model_name: modelName,
          local_model_path: localModelPath.trim() || null,
          training_args: trainingArgs,
          notes: trainingNotes.trim() || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "training run failed");
      setTrainingResult(data);
    } catch (e: unknown) {
      setTrainingErr(e instanceof Error ? e.message : "training run failed");
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden">
      <BackgroundBeams className="z-0" />
      <div className="relative z-10 mx-auto w-full max-w-6xl px-6 py-10 text-white">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-3xl font-semibold">MLOps (MLflow)</h1>
          <Link href="/" className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs">Back</Link>
        </div>
        <div className="rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 text-xs text-slate-300">Experiments + Model Registry Promotion</div>
          <div className="flex flex-wrap gap-2">
            <button onClick={loadExperiments} className="rounded-full bg-cyan-400/20 px-3 py-1 text-xs ring-1 ring-cyan-400/40">Load Experiments</button>
            <button onClick={loadModels} className="rounded-full bg-indigo-400/20 px-3 py-1 text-xs ring-1 ring-indigo-400/40">Load Models</button>
            <button onClick={loadDatasetVersions} className="rounded-full bg-slate-400/20 px-3 py-1 text-xs ring-1 ring-slate-400/40">Load Datasets</button>
            <button onClick={loadAutoTrain} className="rounded-full bg-emerald-400/20 px-3 py-1 text-xs ring-1 ring-emerald-400/40">Auto Train Status</button>
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-3">
            <input value={modelName} onChange={(e) => setModelName(e.target.value)} className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs" placeholder="model name" />
            <select
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
            >
              <option value={modelName}>Current: {modelName}</option>
              {models.map((m) => (
                <option key={String(m.id || m.model || "")} value={String(m.model || m.name || "")}>
                  {String(m.name || m.model || m.id || "model")}
                </option>
              ))}
            </select>
            <input value={version} onChange={(e) => setVersion(e.target.value)} className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs" />
            <input value={stage} onChange={(e) => setStage(e.target.value)} className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs" />
          </div>
          <button onClick={promote} className="mt-3 rounded-full bg-emerald-400/20 px-3 py-1 text-xs ring-1 ring-emerald-400/40">Promote</button>
          {servingErr && <div className="mt-3 text-xs text-rose-300">{servingErr}</div>}
          {error && <div className="mt-3 text-xs text-rose-300">{error}</div>}
          <pre className="mt-4 max-h-64 overflow-auto rounded-md border border-white/10 bg-black/50 p-3 text-[11px] text-slate-200">
{JSON.stringify({ experiments, lastAction }, null, 2)}
          </pre>
        </div>

        <div className="mt-6 rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 text-xs text-slate-300">Serving Model Selector</div>
          <div className="space-y-2 text-xs text-slate-300">
            {models.map((m) => (
              <div key={String(m.id || "")} className="flex items-center justify-between rounded-md border border-white/10 bg-black/50 px-3 py-2">
                <div>
                  <div className="text-slate-200">{String(m.name || m.model || m.id || "")}</div>
                  <div className="text-[11px] text-slate-500">
                    {m.is_default ? "Serving" : "Idle"} · {String(m.provider || "")}
                  </div>
                </div>
                <button
                  onClick={() => setServingModel(String(m.id || ""))}
                  className="rounded-full bg-indigo-400/20 px-2 py-1 text-[11px] ring-1 ring-indigo-400/40"
                >
                  Set Serving
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 text-xs text-slate-300">Auto Training on Approval</div>
          <div className="flex items-center gap-3 text-xs text-slate-300">
            <span>Status: {autoTrainEnabled === null ? "unknown" : autoTrainEnabled ? "enabled" : "disabled"}</span>
            <button
              onClick={toggleAutoTrain}
              className="rounded-full bg-amber-400/20 px-3 py-1 text-xs ring-1 ring-amber-400/40"
            >
              Toggle
            </button>
          </div>
          {autoTrainErr && <div className="mt-2 text-xs text-rose-300">{autoTrainErr}</div>}
        </div>

        <div className="mt-6 rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 text-xs text-slate-300">Dataset Versions (Batch Training)</div>
          <div className="flex gap-2">
            <input
              value={datasetName}
              onChange={(e) => setDatasetName(e.target.value)}
              className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
              placeholder="dataset name (optional)"
            />
            <button
              onClick={createDataset}
              className="rounded-full bg-sky-400/20 px-3 py-1 text-xs ring-1 ring-sky-400/40"
            >
              Create
            </button>
          </div>
          {datasetErr && <div className="mt-2 text-xs text-rose-300">{datasetErr}</div>}
          <div className="mt-3 space-y-2 text-xs text-slate-300">
            {datasetVersions.map((v) => (
              <div key={String(v.id || "")} className="flex items-center justify-between rounded-md border border-white/10 bg-black/50 px-3 py-2">
                <div>
                  <div className="text-slate-200">{String(v.name || v.id || "")}</div>
                  <div className="text-[11px] text-slate-500">{String(v.status || "")}</div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setDatasetVersionId(String(v.id || ""))}
                    className="rounded-full bg-white/10 px-2 py-1 text-[11px]"
                  >
                    Use
                  </button>
                  <button
                    onClick={() => sealDataset(String(v.id || ""))}
                    className="rounded-full bg-rose-400/20 px-2 py-1 text-[11px] ring-1 ring-rose-400/40"
                  >
                    Seal
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 text-xs text-slate-300">One-Click Local Fine-Tune</div>
          <div className="grid gap-2 md:grid-cols-2">
            <input
              value={datasetVersionId}
              onChange={(e) => setDatasetVersionId(e.target.value)}
              className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
              placeholder="dataset_version_id"
            />
            <input
              value={localModelPath}
              onChange={(e) => setLocalModelPath(e.target.value)}
              className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
              placeholder="local model path (optional)"
            />
          </div>
          <textarea
            value={trainingNotes}
            onChange={(e) => setTrainingNotes(e.target.value)}
            className="mt-2 w-full rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
            placeholder="notes (optional)"
          />
          <textarea
            value={trainingArgsText}
            onChange={(e) => setTrainingArgsText(e.target.value)}
            className="mt-2 w-full rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs font-mono"
            placeholder='training_args JSON (e.g. {"epochs":1,"learning_rate":0.0002})'
          />
          <button
            onClick={runTraining}
            className="mt-3 rounded-full bg-emerald-400/20 px-3 py-1 text-xs ring-1 ring-emerald-400/40"
          >
            Start Fine-Tune
          </button>
          {trainingErr && <div className="mt-3 text-xs text-rose-300">{trainingErr}</div>}
          {trainingResult && (
            <pre className="mt-3 max-h-64 overflow-auto rounded-md border border-white/10 bg-black/50 p-3 text-[11px] text-slate-200">
{JSON.stringify(trainingResult, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </main>
  );
}
