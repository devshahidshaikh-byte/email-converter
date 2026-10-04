const state = {
  domains: [],
  results: [],
  page: 1,
  pageSize: 50,
  lastPayload: null
};

const $ = id => document.getElementById(id);

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), 2200);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[char]));
}

function normalizeDomain(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/^www\./, "")
    .replace(/^@/, "")
    .replace(/\/.*$/, "")
    .replace(/\.$/, "");
}

function addDomain(rawValue = null) {
  const input = $("domainInput");
  const raw = rawValue ?? input.value;
  const values = String(raw)
    .split(/[\s,;]+/)
    .map(normalizeDomain)
    .filter(Boolean);

  let added = false;
  for (const domain of values) {
    if (!state.domains.includes(domain)) {
      state.domains.push(domain);
      added = true;
    }
  }

  input.value = "";
  renderDomains();
  if (added) saveDraft();
}

function removeDomain(index) {
  state.domains.splice(index, 1);
  renderDomains();
  saveDraft();
}

function renderDomains() {
  $("domainTags").innerHTML = state.domains.map((domain, index) => `
    <span class="domain-tag">
      <span>${escapeHtml(domain)}</span>
      <button type="button" aria-label="Remove ${escapeHtml(domain)}" onclick="removeDomain(${index})">×</button>
    </span>
  `).join("");
}

function buildPayload() {
  return {
    first_name: $("firstName").value.trim(),
    last_name: $("lastName").value.trim(),
    domains: [...state.domains]
  };
}

function validateForm() {
  const first = $("firstName").value.trim();
  const last = $("lastName").value.trim();

  if (!first) return "Enter a first name.";
  if (!last) return "Enter a last name.";
  if (!state.domains.length) return "Add at least one company domain.";
  return "";
}

function setLoading(loading) {
  const button = $("generateBtn");
  button.disabled = loading;
  button.classList.toggle("loading", loading);
  $("formStatus").textContent = loading ? "Generating candidates…" : "";
  $("formStatus").classList.remove("success");
}

async function generate(event) {
  event?.preventDefault();
  const error = validateForm();
  if (error) {
    $("formStatus").textContent = error;
    $("formStatus").classList.remove("success");
    return;
  }

  const payload = buildPayload();
  state.lastPayload = payload;
  saveDraft();
  setLoading(true);

  try {
    const data = await API.generate(payload);
    state.results = Array.isArray(data.results) ? data.results : [];
    state.page = 1;
    renderResults();
    $("formStatus").textContent = `${data.total} unique candidates generated.`;
    $("formStatus").classList.add("success");
    if (state.results.length) {
      $("resultsSection").scrollIntoView({ behavior: "smooth", block: "start" });
      toast(`${data.total} candidates generated`);
    }
  } catch (error) {
    $("formStatus").textContent = error.message || "Generation failed.";
    toast("Could not generate results");
  } finally {
    setLoading(false);
  }
}

function filteredResults() {
  const query = $("searchInput").value.trim().toLowerCase();
  if (!query) return state.results;
  return state.results.filter(item =>
    String(item.email).toLowerCase().includes(query) ||
    String(item.label).toLowerCase().includes(query) ||
    String(item.domain).toLowerCase().includes(query)
  );
}

function renderResults() {
  const rows = filteredResults();
  const total = rows.length;
  const pages = Math.max(1, Math.ceil(total / state.pageSize));
  if (state.page > pages) state.page = pages;

  const start = (state.page - 1) * state.pageSize;
  const visible = rows.slice(start, start + state.pageSize);

  $("totalStat").textContent = state.results.length.toLocaleString();
  $("domainStat").textContent = new Set(state.results.map(r => r.domain)).size.toLocaleString();
  $("visibleStat").textContent = total.toLocaleString();
  $("resultMeta").textContent = state.results.length
    ? `${state.results.length.toLocaleString()} generated candidates${total !== state.results.length ? ` · ${total.toLocaleString()} match your search` : ""}.`
    : "Your results will appear here.";

  $("copyAllBtn").disabled = state.results.length === 0;
  $("exportBtn").disabled = state.results.length === 0;
  $("searchInput").disabled = state.results.length === 0;
  $("prevBtn").disabled = state.page <= 1 || !total;
  $("nextBtn").disabled = state.page >= pages || !total;

  if (!visible.length) {
    const message = state.results.length ? "No matching results" : "No results yet";
    const hint = state.results.length ? "Try a different search term." : "Enter a name and domain above, then click Generate emails.";
    $("resultsBody").innerHTML = `
      <tr class="empty-row"><td colspan="4"><div class="empty-state">
        <div class="empty-state-icon"><span>${state.results.length ? "⌕" : "@"}</span></div>
        <strong>${message}</strong><p>${hint}</p>
      </div></td></tr>`;
  } else {
    $("resultsBody").innerHTML = visible.map(item => `
      <tr>
        <td>${escapeHtml(item.email)}</td>
        <td><code>${escapeHtml(item.label || item.pattern || "Standard")}</code></td>
        <td>${escapeHtml(item.domain)}</td>
        <td><button class="copy-row-btn" type="button" data-email="${escapeHtml(item.email)}">Copy</button></td>
      </tr>
    `).join("");
  }

  const first = total ? start + 1 : 0;
  const last = Math.min(start + state.pageSize, total);
  $("pageMeta").textContent = total ? `${first}–${last} of ${total}` : (state.results.length ? "No matches" : "Ready when you are.");
}

async function copyText(text, message = "Copied") {
  try {
    await navigator.clipboard.writeText(text);
    toast(message);
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
    toast(message);
  }
}

function copyAll() {
  const rows = filteredResults();
  if (!rows.length) return;
  copyText(rows.map(item => item.email).join("\n"), `${rows.length} emails copied`);
}

function openExportMenu() {
  if ($("exportBtn").disabled) return;
  $("exportMenu").classList.toggle("hidden");
}

async function exportResults(type) {
  if (!state.lastPayload || !state.results.length) return;
  try {
    const blob = await API.export(state.lastPayload, type);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `email-patterns.${type}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    $("exportMenu").classList.add("hidden");
    toast("Export ready");
  } catch (error) {
    toast(error.message || "Export failed");
  }
}

function clearAll() {
  $("firstName").value = "";
  $("lastName").value = "";
  $("domainInput").value = "";
  state.domains = [];
  state.results = [];
  state.lastPayload = null;
  state.page = 1;
  $("searchInput").value = "";
  $("formStatus").textContent = "";
  $("bulkStatus").textContent = "";
  $("fileName").textContent = "No file selected";
  $("csvFile").value = "";
  renderDomains();
  renderResults();
  localStorage.removeItem("email-pattern-generator-draft");
  toast("Form cleared");
}

function saveDraft() {
  const draft = {
    first: $("firstName").value,
    last: $("lastName").value,
    domains: state.domains
  };
  localStorage.setItem("email-pattern-generator-draft", JSON.stringify(draft));
}

function loadDraft() {
  try {
    const draft = JSON.parse(localStorage.getItem("email-pattern-generator-draft") || "null");
    if (!draft) return;
    $("firstName").value = draft.first || "";
    $("lastName").value = draft.last || "";
    state.domains = Array.isArray(draft.domains) ? draft.domains : [];
    renderDomains();
  } catch {
    localStorage.removeItem("email-pattern-generator-draft");
  }
}

function toggleTheme() {
  const dark = document.body.classList.toggle("dark");
  localStorage.setItem("email-pattern-generator-theme", dark ? "dark" : "light");
}

function loadTheme() {
  if (localStorage.getItem("email-pattern-generator-theme") === "dark") {
    document.body.classList.add("dark");
  }
}

async function processBulk() {
  // The bulk feature is private. The backend performs the actual authorization
  // check, so this is not merely a visual/JavaScript restriction.
  const file = $("csvFile").files[0];
  if (!file) {
    toast("Choose a CSV file first");
    return;
  }

  const status = $("bulkStatus");
  const button = $("bulkBtn");
  button.disabled = true;
  status.textContent = "Uploading and processing securely…";

  try {
    const data = await API.bulkGenerate(file);

    state.results = Array.isArray(data.results) ? data.results : [];
    state.lastPayload = null;
    state.page = 1;
    renderResults();

    status.textContent =
      `Processed ${data.rows_processed} row(s) · ${state.results.length.toLocaleString()} unique candidates.`;

    toast("Private bulk processing complete");
    $("resultsSection").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    status.textContent = error.message || "Could not process CSV.";
    toast("Private bulk processing failed");
  } finally {
    button.disabled = false;
  }
}

function parseCSVLine(line) {
  const cells = [];
  let current = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"' && line[i + 1] === '"') {
      current += '"';
      i++;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      cells.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  cells.push(current.trim());
  return cells;
}

function handleKeyboard(event) {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    $("generatorForm").requestSubmit();
  }
}

$("generatorForm").addEventListener("submit", generate);
$("addDomainBtn").addEventListener("click", () => addDomain());
$("domainInput").addEventListener("keydown", event => {
  if (event.key === "Enter") {
    event.preventDefault();
    addDomain();
  }
});
$("domainInput").addEventListener("blur", () => {
  if ($("domainInput").value.trim()) addDomain();
});
$("firstName").addEventListener("input", saveDraft);
$("lastName").addEventListener("input", saveDraft);
$("clearBtn").addEventListener("click", clearAll);
$("themeBtn").addEventListener("click", toggleTheme);
$("copyAllBtn").addEventListener("click", copyAll);
$("exportBtn").addEventListener("click", openExportMenu);
$("searchInput").addEventListener("input", () => { state.page = 1; renderResults(); });
$("prevBtn").addEventListener("click", () => { state.page--; renderResults(); });
$("nextBtn").addEventListener("click", () => { state.page++; renderResults(); });
$("bulkBtn").addEventListener("click", processBulk);
$("csvFile").addEventListener("change", () => {
  $("fileName").textContent = $("csvFile").files[0]?.name || "No file selected";
});
document.addEventListener("keydown", handleKeyboard);
document.addEventListener("click", event => {
  if (!event.target.closest(".export-wrap")) $("exportMenu").classList.add("hidden");
  const copyButton = event.target.closest(".copy-row-btn");
  if (copyButton) copyText(copyButton.dataset.email, "Email copied");
});

loadTheme();
loadDraft();
renderResults();
