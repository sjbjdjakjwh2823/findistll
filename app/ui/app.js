let currentCaseId = "";
let lastDocId = "";

function setStatus(id, text) {
  const el = document.getElementById(id);
  if (el) {
    el.textContent = text;
  }
}

async function createCase() {
  const titleEl = document.getElementById("caseTitle");
  const title = titleEl ? titleEl.value : "Untitled";
  const res = await fetch("/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title })
  });
  const data = await res.json();
  currentCaseId = data.case_id;
  const caseIdEl = document.getElementById("caseId");
  if (caseIdEl) {
    caseIdEl.value = currentCaseId;
  }
  setStatus("caseStatus", `Case 생성됨: ${currentCaseId}`);
}

async function uploadDoc() {
  if (!currentCaseId) {
    alert("먼저 Case를 생성하세요.");
    return;
  }
  const content = document.getElementById("content").value || "Sample content";
  const filename = document.getElementById("filename").value || "sample.txt";
  const mimeType = document.getElementById("mimeType").value || "text/plain";

  const res = await fetch(`/cases/${currentCaseId}/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source: "ui",
      filename,
      mime_type: mimeType,
      content
    })
  });
  const data = await res.json();
  lastDocId = data.doc_id;
  setStatus("docStatus", `문서 업로드 완료: ${lastDocId}`);
}

async function runPipeline() {
  if (!currentCaseId) {
    alert("먼저 Case를 생성하세요.");
    return;
  }
  const res = await fetch(`/cases/${currentCaseId}/run`, { method: "POST" });
  const data = await res.json();
  const distillEl = document.getElementById("distillOut");
  const decisionEl = document.getElementById("decisionOut");
  const pipelineEl = document.getElementById("pipelineOut");
  if (distillEl) {
    distillEl.textContent = JSON.stringify(data.distill, null, 2);
  }
  if (decisionEl) {
    decisionEl.textContent = JSON.stringify(data.decision, null, 2);
  }
  if (pipelineEl) {
    pipelineEl.textContent = JSON.stringify(data, null, 2);
  }
}

function loadSample() {
  const titleEl = document.getElementById("caseTitle");
  if (titleEl) {
    titleEl.value = "Tesla Q3 2025 Risk Review";
  }
  const contentEl = document.getElementById("content");
  if (contentEl) {
    contentEl.value = "Tesla reported revenue of 25.1B with gross margin 18.2%. Net income declined due to FX headwinds.";
  }
}

async function loadCases() {
  const tableBody = document.getElementById("casesTable");
  if (!tableBody) return;
  const res = await fetch("/cases");
  const data = await res.json();
  tableBody.innerHTML = "";
  data.forEach((c) => {
    const row = document.createElement("tr");
    row.innerHTML = `<td>${c.case_id}</td><td>${c.title}</td><td>${c.status}</td>`;
    tableBody.appendChild(row);
  });
}

async function loadDocuments() {
  const tableBody = document.getElementById("docsTable");
  if (!tableBody) return;
  const res = await fetch("/documents");
  const data = await res.json();
  tableBody.innerHTML = "";
  data.forEach((d) => {
    const row = document.createElement("tr");
    row.innerHTML = `<td>${d.doc_id}</td><td>${d.filename || ""}</td><td>${d.mime_type || ""}</td>`;
    tableBody.appendChild(row);
  });
}

async function loadDecisions() {
  const tableBody = document.getElementById("decisionsTable");
  if (!tableBody) return;
  const res = await fetch("/cases");
  const data = await res.json();
  tableBody.innerHTML = "";
  data.forEach((c) => {
    const decision = c.decision ? c.decision.decision : "-";
    const rationale = c.decision ? c.decision.rationale : "-";
    const row = document.createElement("tr");
    row.innerHTML = `<td>${c.case_id}</td><td>${decision}</td><td>${rationale}</td>`;
    tableBody.appendChild(row);
  });
}

window.addEventListener("load", () => {
  loadCases();
  loadDocuments();
  loadDecisions();
});
