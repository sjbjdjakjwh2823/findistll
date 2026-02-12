"use client";

import React, { useState } from "react";
import type { ApiList, ApiResult, JsonRecord } from "@/lib/types";

const API_BASE = "/api/proxy";

type HttpMethod = "GET" | "POST" | "PATCH";

function parseMaybeJson(input: string): unknown {
  try {
    return JSON.parse(input);
  } catch {
    return null;
  }
}

export default function CollabPage() {
  const [tenantId, setTenantId] = useState("public");

  const [targetUser, setTargetUser] = useState("bob");
  const [teamName, setTeamName] = useState("Risk Team");
  const [selectedTeamId, setSelectedTeamId] = useState("");
  const [newMemberUserId, setNewMemberUserId] = useState("bob");
  const [newMemberRole, setNewMemberRole] = useState("member");

  const [spaceType, setSpaceType] = useState("personal");
  const [spaceName, setSpaceName] = useState("My Space");
  const [spaceTeamId, setSpaceTeamId] = useState("");
  const [selectedSpaceId, setSelectedSpaceId] = useState("");

  const [docId, setDocId] = useState("doc_1");
  const [fileVisibility, setFileVisibility] = useState("private");
  const [selectedFileId, setSelectedFileId] = useState("");
  const [sharePrincipalType, setSharePrincipalType] = useState("user");
  const [sharePrincipalId, setSharePrincipalId] = useState("bob");
  const [sharePermission, setSharePermission] = useState("read");

  const [transferReceiver, setTransferReceiver] = useState("bob");
  const [transferMessage, setTransferMessage] = useState("please review");

  const [jobType, setJobType] = useState("rag");
  const [flow, setFlow] = useState("interactive");
  const [jobInputText, setJobInputText] = useState('{"query":"market stress"}');
  const [jobIdForLookup, setJobIdForLookup] = useState("");

  const [ragQuery, setRagQuery] = useState("Fed rate hike impact");
  const [ragTopK, setRagTopK] = useState(5);
  const [ragThreshold, setRagThreshold] = useState(0.6);

  const [contacts, setContacts] = useState<JsonRecord[]>([]);
  const [invites, setInvites] = useState<JsonRecord[]>([]);
  const [inviteTarget, setInviteTarget] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [teams, setTeams] = useState<JsonRecord[]>([]);
  const [spaces, setSpaces] = useState<JsonRecord[]>([]);
  const [files, setFiles] = useState<JsonRecord[]>([]);
  const [inbox, setInbox] = useState<JsonRecord[]>([]);
  const [tenantStatus, setTenantStatus] = useState<JsonRecord | null>(null);
  const [jobDetail, setJobDetail] = useState<JsonRecord | null>(null);
  const [ragResult, setRagResult] = useState<JsonRecord | null>(null);
  const [tenantLogs, setTenantLogs] = useState<JsonRecord[]>([]);
  const [output, setOutput] = useState<string>("No actions yet");
  const [error, setError] = useState<string | null>(null);

  const setTenant = async () => {
    await fetch("/api/tenant", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: tenantId }),
    });
  };

  const api = async (
    path: string,
    method: HttpMethod = "GET",
    body?: JsonRecord,
    asAdmin = false
  ): Promise<ApiResult> => {
    void asAdmin; // Auth/admin headers are injected by `/api/proxy` from NextAuth session + server env.
    const headers = { "Content-Type": "application/json" } as Record<string, string>;
    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: method === "GET" ? undefined : JSON.stringify(body || {}),
    });
    const json = (await res.json().catch(() => ({}))) as ApiResult;
    if (!res.ok) {
      const detail = (json?.detail as string | undefined) || `HTTP ${res.status}`;
      throw new Error(String(detail));
    }
    return json;
  };

  const runAction = async (label: string, fn: () => Promise<ApiResult>) => {
    setError(null);
    try {
      const result = await fn();
      setOutput(JSON.stringify({ label, result }, null, 2));
      return result;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setOutput(JSON.stringify({ label, error: msg }, null, 2));
      throw e;
    }
  };

  const refreshContacts = async () =>
    runAction("contacts.list", async () => {
      const out = (await api("/api/v1/collab/contacts/list")) as ApiList;
      setContacts((out.items as JsonRecord[]) || []);
      return out;
    });

  const refreshInvites = async () =>
    runAction("invites.list", async () => {
      const out = (await api("/api/v1/collab/invites/list")) as ApiList;
      setInvites((out.items as JsonRecord[]) || []);
      return out;
    });

  const refreshTeams = async () =>
    runAction("teams.my", async () => {
      const out = (await api("/api/v1/collab/teams/my-teams")) as ApiList;
      setTeams((out.items as JsonRecord[]) || []);
      if (!selectedTeamId && (out.items || []).length > 0) {
        const first = (out.items as JsonRecord[])[0] || {};
        setSelectedTeamId(String(first.id || ""));
      }
      return out;
    });

  const refreshSpaces = async () =>
    runAction("spaces.list", async () => {
      const out = (await api("/api/v1/collab/spaces")) as ApiList;
      setSpaces((out.items as JsonRecord[]) || []);
      if (!selectedSpaceId && (out.items || []).length > 0) {
        const first = (out.items as JsonRecord[])[0] || {};
        setSelectedSpaceId(String(first.id || ""));
      }
      return out;
    });

  const refreshFiles = async () =>
    runAction("files.list", async () => {
      const out = (await api("/api/v1/collab/files?limit=200")) as ApiList;
      setFiles((out.items as JsonRecord[]) || []);
      if (!selectedFileId && (out.items || []).length > 0) {
        const first = (out.items as JsonRecord[])[0] || {};
        setSelectedFileId(String(first.id || ""));
      }
      return out;
    });

  const refreshInbox = async () =>
    runAction("transfers.inbox", async () => {
      const out = (await api("/api/v1/collab/transfers/inbox")) as ApiList;
      setInbox((out.items as JsonRecord[]) || []);
      return out;
    });

  const refreshTenantStatus = async () =>
    runAction("pipeline.status", async () => {
      const out = (await api("/api/v1/pipeline/tenant-status")) as ApiResult;
      setTenantStatus(out as JsonRecord);
      return out;
    });

  const refreshTenantLogs = async () =>
    runAction("admin.logs.tenant", async () => {
      const out = (await api(
        `/api/v1/admin/logs/tenant?tenant_id=${encodeURIComponent(tenantId)}&limit=200`,
        "GET",
        undefined,
        true
      )) as ApiList;
      setTenantLogs((out.items as JsonRecord[]) || []);
      return out;
    });

  const refreshAll = async () => {
    await Promise.allSettled([
      refreshContacts(),
      refreshInvites(),
      refreshTeams(),
      refreshSpaces(),
      refreshFiles(),
      refreshInbox(),
      refreshTenantStatus(),
    ]);
  };

  const requestFriend = async () =>
    runAction("contacts.request", async () => {
      const out = await api("/api/v1/collab/contacts/request", "POST", { target_user_id: targetUser });
      await refreshContacts();
      return out;
    });

  const acceptFriend = async (contactId: string) =>
    runAction("contacts.accept", async () => {
      const out = await api("/api/v1/collab/contacts/accept", "POST", { contact_id: contactId });
      await refreshContacts();
      return out;
    });

  const createInvite = async () =>
    runAction("invites.create", async () => {
      const out = await api("/api/v1/collab/invites/create", "POST", {
        target_user_id: inviteTarget || undefined,
      });
      await refreshInvites();
      return out;
    });

  const acceptInvite = async () =>
    runAction("invites.accept", async () => {
      const out = await api("/api/v1/collab/invites/accept", "POST", { code: inviteCode });
      await refreshContacts();
      return out;
    });

  const createTeam = async () =>
    runAction("teams.create", async () => {
      const out = await api("/api/v1/collab/teams", "POST", { name: teamName });
      await refreshTeams();
      return out;
    });

  const addMember = async () =>
    runAction("teams.add_member", async () => {
      if (!selectedTeamId) throw new Error("Select a team first");
      const out = await api(`/api/v1/collab/teams/${selectedTeamId}/members`, "POST", {
        user_id: newMemberUserId,
        role: newMemberRole,
      });
      await refreshTeams();
      return out;
    });

  const createSpace = async () =>
    runAction("spaces.create", async () => {
      const payload: JsonRecord = { type: spaceType, name: spaceName };
      if (spaceType === "team") payload.team_id = spaceTeamId || selectedTeamId;
      const out = await api("/api/v1/collab/spaces", "POST", payload);
      await refreshSpaces();
      return out;
    });

  const uploadFile = async () =>
    runAction("files.upload", async () => {
      if (!selectedSpaceId) throw new Error("Select a space first");
      const out = await api("/api/v1/collab/files/upload", "POST", {
        space_id: selectedSpaceId,
        doc_id: docId,
        version: 1,
        visibility: fileVisibility,
      });
      await refreshFiles();
      return out;
    });

  const getFile = async () =>
    runAction("files.get", async () => {
      if (!selectedFileId) throw new Error("Select a file first");
      return api(`/api/v1/collab/files/${selectedFileId}`);
    });

  const shareFile = async () =>
    runAction("files.share", async () => {
      if (!selectedFileId) throw new Error("Select a file first");
      const out = await api(`/api/v1/collab/files/${selectedFileId}/share`, "POST", {
        principal_type: sharePrincipalType,
        principal_id: sharePrincipalId,
        permission: sharePermission,
      });
      await refreshFiles();
      return out;
    });

  const sendTransfer = async () =>
    runAction("transfers.send", async () => {
      if (!selectedFileId) throw new Error("Select a file first");
      const out = await api("/api/v1/collab/transfers/send", "POST", {
        receiver_user_id: transferReceiver,
        file_id: selectedFileId,
        message: transferMessage,
      });
      await refreshInbox();
      return out;
    });

  const ackTransfer = async (transferId: string, status: string) =>
    runAction("transfers.ack", async () => {
      const out = await api(`/api/v1/collab/transfers/${transferId}/ack`, "POST", { status });
      await refreshInbox();
      return out;
    });

  const submitJob = async () =>
    runAction("pipeline.submit", async () => {
      const inputRef = parseMaybeJson(jobInputText);
      if (!inputRef) throw new Error("Job input JSON is invalid");
      const out = await api("/api/v1/pipeline/jobs/submit", "POST", {
        job_type: jobType,
        flow,
        input_ref: inputRef,
      });
      setJobIdForLookup(String(out.id || ""));
      await refreshTenantStatus();
      return out;
    });

  const fetchJob = async () =>
    runAction("pipeline.job", async () => {
      if (!jobIdForLookup) throw new Error("Enter a job id first");
      const out = await api(`/api/v1/pipeline/jobs/${jobIdForLookup}`);
      setJobDetail(out);
      return out;
    });

  const queryRag = async () =>
    runAction("rag.query", async () => {
      const out = await api("/api/v1/rag/query", "POST", {
        query: ragQuery,
        top_k: ragTopK,
        threshold: ragThreshold,
      });
      setRagResult(out);
      return out;
    });

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <div className="mx-auto max-w-7xl px-6 py-8 space-y-6">
        <header className="rounded-xl border border-white/10 bg-gradient-to-br from-cyan-400/10 to-fuchsia-400/10 p-5">
          <h1 className="text-2xl font-semibold tracking-tight">Enterprise Collaboration + Shared Pipeline</h1>
          <p className="text-sm text-neutral-300 mt-1">
            Personal isolation, team collaboration, direct transfer, tenant-shared RAG/LLM pipeline in one workspace.
          </p>
        </header>

        <section className="rounded-xl border border-white/10 bg-white/5 p-4 grid grid-cols-1 md:grid-cols-5 gap-3">
          <input
            className="bg-black/40 border border-white/10 rounded p-2 text-xs md:col-span-3"
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            placeholder="tenant id (e.g. acme)"
          />
          <button
            className="px-3 py-2 rounded bg-white/10 border border-white/20 text-xs hover:bg-white/20"
            onClick={setTenant}
          >
            Set Tenant
          </button>
          <button className="px-3 py-2 rounded bg-white/10 border border-white/20 text-xs hover:bg-white/20" onClick={refreshAll}>
            Refresh
          </button>
        </section>

        <section className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <article className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            <h2 className="font-semibold">Contacts (Friends)</h2>
            <div className="flex gap-2">
              <input className="flex-1 bg-black/40 border border-white/10 rounded p-2 text-xs" value={targetUser} onChange={(e) => setTargetUser(e.target.value)} placeholder="target user id" />
              <button className="px-3 py-2 rounded bg-cyan-500/20 border border-cyan-400/40 text-xs" onClick={requestFriend}>Request</button>
              <button className="px-3 py-2 rounded bg-white/10 border border-white/20 text-xs" onClick={refreshContacts}>List</button>
            </div>
            <div className="max-h-40 overflow-auto border border-white/10 rounded">
              {(contacts || []).map((c) => {
                const canAccept = c?.status === "pending";
                return (
                  <div key={String(c.id)} className="p-2 text-xs border-b border-white/5 flex items-center justify-between gap-2">
                    <span className="font-mono">
                      {String(c.requester_user_id ?? "")}
                      {" -> "}
                      {String(c.target_user_id ?? "")} [{String(c.status ?? "")}]
                    </span>
                    {canAccept && (
                      <button className="px-2 py-1 rounded bg-emerald-500/20 border border-emerald-400/40" onClick={() => acceptFriend(String(c.id))}>
                        Accept
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </article>

          <article className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            <h2 className="font-semibold">Teams</h2>
            <div className="flex gap-2">
              <input className="flex-1 bg-black/40 border border-white/10 rounded p-2 text-xs" value={teamName} onChange={(e) => setTeamName(e.target.value)} placeholder="team name" />
              <button className="px-3 py-2 rounded bg-emerald-500/20 border border-emerald-400/40 text-xs" onClick={createTeam}>Create</button>
              <button className="px-3 py-2 rounded bg-white/10 border border-white/20 text-xs" onClick={refreshTeams}>My Teams</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              <select className="md:col-span-2 bg-black/40 border border-white/10 rounded p-2 text-xs" value={selectedTeamId} onChange={(e) => setSelectedTeamId(e.target.value)}>
                <option value="">Select team</option>
                {(teams || []).map((t) => (
                  <option key={String(t.id)} value={String(t.id)}>
                    {String(t.name ?? "")} ({String(t.membership_role ?? "member")})
                  </option>
                ))}
              </select>
              <input className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={newMemberUserId} onChange={(e) => setNewMemberUserId(e.target.value)} placeholder="member user id" />
              <select className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={newMemberRole} onChange={(e) => setNewMemberRole(e.target.value)}>
                <option value="member">member</option>
                <option value="admin">admin</option>
                <option value="owner">owner</option>
              </select>
            </div>
            <button className="px-3 py-2 rounded bg-indigo-500/20 border border-indigo-400/40 text-xs" onClick={addMember}>Add Member</button>
          </article>

          <article className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            <h2 className="font-semibold">Spaces</h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              <select className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={spaceType} onChange={(e) => setSpaceType(e.target.value)}>
                <option value="personal">personal</option>
                <option value="team">team</option>
              </select>
              <input className="md:col-span-2 bg-black/40 border border-white/10 rounded p-2 text-xs" value={spaceName} onChange={(e) => setSpaceName(e.target.value)} placeholder="space name" />
              <input className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={spaceTeamId} onChange={(e) => setSpaceTeamId(e.target.value)} placeholder="team id (optional)" />
            </div>
            <div className="flex gap-2">
              <button className="px-3 py-2 rounded bg-amber-500/20 border border-amber-400/40 text-xs" onClick={createSpace}>Create Space</button>
              <button className="px-3 py-2 rounded bg-white/10 border border-white/20 text-xs" onClick={refreshSpaces}>List Spaces</button>
            </div>
            <select className="w-full bg-black/40 border border-white/10 rounded p-2 text-xs" value={selectedSpaceId} onChange={(e) => setSelectedSpaceId(e.target.value)}>
              <option value="">Select space</option>
              {(spaces || []).map((s) => (
                <option key={String(s.id)} value={String(s.id)}>
                  {String(s.name ?? "")} ({String(s.type ?? "")})
                </option>
              ))}
            </select>
          </article>

          <article className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            <h2 className="font-semibold">Files + ACL</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <input className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={docId} onChange={(e) => setDocId(e.target.value)} placeholder="doc_id" />
              <select className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={fileVisibility} onChange={(e) => setFileVisibility(e.target.value)}>
                <option value="private">private</option>
                <option value="team">team</option>
                <option value="direct">direct</option>
              </select>
              <button className="px-3 py-2 rounded bg-violet-500/20 border border-violet-400/40 text-xs" onClick={uploadFile}>Register File</button>
            </div>
            <div className="flex gap-2">
              <button className="px-3 py-2 rounded bg-white/10 border border-white/20 text-xs" onClick={refreshFiles}>List Visible Files</button>
              <button className="px-3 py-2 rounded bg-white/10 border border-white/20 text-xs" onClick={getFile}>Get Selected File</button>
            </div>
            <select className="w-full bg-black/40 border border-white/10 rounded p-2 text-xs" value={selectedFileId} onChange={(e) => setSelectedFileId(e.target.value)}>
              <option value="">Select file</option>
              {(files || []).map((f) => (
                <option key={String(f.id)} value={String(f.id)}>
                  {String(f.doc_id ?? "")} / {String(f.visibility ?? "")} / {String(f.owner_user_id ?? "")}
                </option>
              ))}
            </select>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <select className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={sharePrincipalType} onChange={(e) => setSharePrincipalType(e.target.value)}>
                <option value="user">user</option>
                <option value="team">team</option>
              </select>
              <input className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={sharePrincipalId} onChange={(e) => setSharePrincipalId(e.target.value)} placeholder="principal id" />
              <select className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={sharePermission} onChange={(e) => setSharePermission(e.target.value)}>
                <option value="read">read</option>
                <option value="comment">comment</option>
                <option value="share">share</option>
              </select>
            </div>
            <button className="px-3 py-2 rounded bg-fuchsia-500/20 border border-fuchsia-400/40 text-xs" onClick={shareFile}>Share File</button>
          </article>

          <article className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            <h2 className="font-semibold">Direct Transfer</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <input className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={transferReceiver} onChange={(e) => setTransferReceiver(e.target.value)} placeholder="receiver user id" />
              <input className="md:col-span-2 bg-black/40 border border-white/10 rounded p-2 text-xs" value={transferMessage} onChange={(e) => setTransferMessage(e.target.value)} placeholder="message" />
            </div>
            <div className="flex gap-2">
              <button className="px-3 py-2 rounded bg-lime-500/20 border border-lime-400/40 text-xs" onClick={sendTransfer}>Send</button>
              <button className="px-3 py-2 rounded bg-white/10 border border-white/20 text-xs" onClick={refreshInbox}>Inbox</button>
            </div>
            <div className="max-h-40 overflow-auto border border-white/10 rounded">
              {(inbox || []).map((t) => (
                <div key={String(t.id)} className="p-2 text-xs border-b border-white/5 space-y-1">
                  <div className="font-mono">
                    {String(t.sender_user_id ?? "")}
                    {" -> "}
                    {String(t.receiver_user_id ?? "")} / {String(t.status ?? "")}
                  </div>
                  <div className="text-neutral-400">{String(t.message ?? "-")}</div>
                  <div className="flex gap-2">
                    <button className="px-2 py-1 rounded bg-white/10 border border-white/20" onClick={() => ackTransfer(String(t.id), "read")}>read</button>
                    <button className="px-2 py-1 rounded bg-emerald-500/20 border border-emerald-400/40" onClick={() => ackTransfer(String(t.id), "accepted")}>accept</button>
                    <button className="px-2 py-1 rounded bg-rose-500/20 border border-rose-400/40" onClick={() => ackTransfer(String(t.id), "rejected")}>reject</button>
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            <h2 className="font-semibold">Friend Invite Codes</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <input
                className="md:col-span-2 bg-black/40 border border-white/10 rounded p-2 text-xs"
                value={inviteTarget}
                onChange={(e) => setInviteTarget(e.target.value)}
                placeholder="target user id (optional)"
              />
              <button className="px-3 py-2 rounded bg-emerald-500/20 border border-emerald-400/40 text-xs" onClick={createInvite}>
                Create Code
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <input
                className="md:col-span-2 bg-black/40 border border-white/10 rounded p-2 text-xs"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                placeholder="invite code"
              />
              <button className="px-3 py-2 rounded bg-lime-500/20 border border-lime-400/40 text-xs" onClick={acceptInvite}>
                Accept Code
              </button>
            </div>
            <button className="px-3 py-2 rounded bg-white/10 border border-white/20 text-xs" onClick={refreshInvites}>List My Invites</button>
            <div className="max-h-40 overflow-auto border border-white/10 rounded">
              {(invites || []).map((inv) => (
                <div key={String(inv.id)} className="p-2 text-xs border-b border-white/5">
                  <span className="font-mono">{String(inv.code ?? "")}</span> → {String(inv.target_user_id ?? "anyone")} [{String(inv.status ?? "")}]
                </div>
              ))}
            </div>
          </article>

          <article className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            <h2 className="font-semibold">Tenant Shared Pipeline</h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              <select className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={jobType} onChange={(e) => setJobType(e.target.value)}>
                <option value="rag">rag</option>
                <option value="ingest">ingest</option>
                <option value="approval">approval</option>
                <option value="train">train</option>
                <option value="export">export</option>
                <option value="batch">batch</option>
              </select>
              <select className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={flow} onChange={(e) => setFlow(e.target.value)}>
                <option value="interactive">interactive</option>
                <option value="approval">approval</option>
                <option value="ingest">ingest</option>
                <option value="batch">batch</option>
              </select>
              <input className="md:col-span-2 bg-black/40 border border-white/10 rounded p-2 text-xs font-mono" value={jobInputText} onChange={(e) => setJobInputText(e.target.value)} placeholder='{"query":"..."}' />
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="px-3 py-2 rounded bg-amber-500/20 border border-amber-400/40 text-xs" onClick={submitJob}>Submit Job</button>
              <input className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={jobIdForLookup} onChange={(e) => setJobIdForLookup(e.target.value)} placeholder="job id" />
              <button className="px-3 py-2 rounded bg-white/10 border border-white/20 text-xs" onClick={fetchJob}>Get Job</button>
              <button className="px-3 py-2 rounded bg-white/10 border border-white/20 text-xs" onClick={refreshTenantStatus}>Tenant Status</button>
            </div>
            <pre className="text-[11px] bg-black/40 p-3 rounded overflow-auto">{JSON.stringify(tenantStatus || jobDetail || {}, null, 2)}</pre>
          </article>

          <article className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            <h2 className="font-semibold">RAG Query (Cause / Effect / Prediction)</h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              <input className="md:col-span-2 bg-black/40 border border-white/10 rounded p-2 text-xs" value={ragQuery} onChange={(e) => setRagQuery(e.target.value)} placeholder="query" />
              <input className="bg-black/40 border border-white/10 rounded p-2 text-xs" type="number" value={ragTopK} onChange={(e) => setRagTopK(Number(e.target.value || 5))} min={1} max={20} />
              <input className="bg-black/40 border border-white/10 rounded p-2 text-xs" type="number" step="0.01" value={ragThreshold} onChange={(e) => setRagThreshold(Number(e.target.value || 0.6))} min={0} max={1} />
            </div>
            <button className="px-3 py-2 rounded bg-sky-500/20 border border-sky-400/40 text-xs" onClick={queryRag}>Run Query</button>
            <pre className="text-[11px] bg-black/40 p-3 rounded overflow-auto">{JSON.stringify(ragResult || {}, null, 2)}</pre>
          </article>
        </section>

        <section className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
          <h2 className="font-semibold">Tenant Admin Logs</h2>
          <div className="flex gap-2">
            <button className="px-3 py-2 rounded bg-white/10 border border-white/20 text-xs" onClick={refreshTenantLogs}>Load Tenant Logs</button>
          </div>
          <pre className="text-[11px] bg-black/40 p-3 rounded overflow-auto max-h-64">{JSON.stringify(tenantLogs, null, 2)}</pre>
        </section>

        <section className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
          <h2 className="font-semibold">RAG Access Policy (by Role)</h2>
          <div className="text-xs text-neutral-400">
            현재 역할은 로그인 세션(NextAuth)에서 자동으로 결정됩니다. (기본: analyst, `PRECISO_ADMIN_EMAILS`에 포함되면 admin)
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
            <div className="rounded-lg border border-white/10 bg-black/40 p-3">
              <div className="text-neutral-300 font-semibold">viewer</div>
              <div className="text-neutral-500 mt-1">top_k: 2</div>
              <div className="text-neutral-500">evidence: off</div>
              <div className="text-neutral-500">prediction: off</div>
            </div>
            <div className="rounded-lg border border-white/10 bg-black/40 p-3">
              <div className="text-neutral-300 font-semibold">analyst</div>
              <div className="text-neutral-500 mt-1">top_k: 5</div>
              <div className="text-neutral-500">evidence: on</div>
              <div className="text-neutral-500">prediction: off</div>
            </div>
            <div className="rounded-lg border border-white/10 bg-black/40 p-3">
              <div className="text-neutral-300 font-semibold">reviewer</div>
              <div className="text-neutral-500 mt-1">top_k: 8</div>
              <div className="text-neutral-500">evidence: on</div>
              <div className="text-neutral-500">prediction: on</div>
            </div>
            <div className="rounded-lg border border-white/10 bg-black/40 p-3">
              <div className="text-neutral-300 font-semibold">admin</div>
              <div className="text-neutral-500 mt-1">top_k: 12</div>
              <div className="text-neutral-500">evidence: on</div>
              <div className="text-neutral-500">prediction: on</div>
            </div>
          </div>
          <div className="text-[11px] text-neutral-500">
            정책은 서버에서 강제됩니다. (환경변수 `RAG_ROLE_POLICY_JSON`으로 오버라이드 가능)
          </div>
        </section>

        <section className="rounded-xl border border-white/10 bg-white/5 p-4">
          <h2 className="font-semibold mb-2">Action Output</h2>
          {error && <div className="text-xs text-rose-300 mb-2">{error}</div>}
          <pre className="text-[11px] bg-black/40 p-3 rounded overflow-auto">{output}</pre>
        </section>
      </div>
    </div>
  );
}
