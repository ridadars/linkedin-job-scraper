"use strict";

/* LinkedIn Job Scraper dashboard.
 * Uses only the existing Phase 5 JSON APIs. All dynamic values are rendered
 * with textContent and createElement to avoid HTML injection.
 */

const API = "/api";
const POLL_INTERVAL_MS = 2500; // never poll faster than every 2-3s
const ACTIVE_STATES = ["pending", "running"];
const PAGE_SIZE = 10;

const state = {
  scrapingJobId: null,
  pollTimer: null,
  submitting: false,
  mode: "browse", // "browse" (/api/jobs) or "search" (scraping-job results)
  page: 1,
  totalPages: 1,
};

const $ = (id) => document.getElementById(id);

/* ---------- fetch helper ---------- */
async function apiFetch(path, options) {
  let res;
  try {
    res = await fetch(API + path, options);
  } catch (networkErr) {
    const e = new Error("Network or API request failed. Please try again.");
    e.kind = "network";
    throw e;
  }
  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    /* some responses (exports) are not JSON; not used here */
  }
  if (!res.ok) {
    const e = new Error((data && data.detail) || res.statusText || "Request failed");
    e.status = res.status;
    e.data = data;
    throw e;
  }
  return data;
}

/* ---------- messaging ---------- */
function showMessage(kind, text) {
  const box = $("message");
  box.className = "message message--" + kind;
  box.textContent = text;
  box.hidden = false;
}
function clearMessage() {
  const box = $("message");
  box.hidden = true;
  box.textContent = "";
}

// Map a scraping job's failure/status into a readable, responsible message.
function blockedMessageFor(reason) {
  const r = (reason || "").toLowerCase();
  if (r.includes("captcha")) {
    return "CAPTCHA detected. The system stopped and did not attempt to solve or bypass it.";
  }
  if (r.includes("authentication") || r.includes("sign-in") || r.includes("signin")) {
    return "LinkedIn showed a sign-in wall. The system stopped and did not log in or bypass it.";
  }
  if (r.includes("access") || r.includes("restrict") || r.includes("rate")) {
    return "Access was restricted (possible rate limit). The system stopped and did not bypass it.";
  }
  if (r.includes("timeout")) {
    return "The request timed out while loading the page.";
  }
  return null;
}

/* ---------- safe DOM helpers ---------- */
function td(text, className) {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  cell.textContent = text === null || text === undefined || text === "" ? "—" : String(text);
  return cell;
}

function formatSalary(job) {
  if (job.salary_text) return job.salary_text;
  if (job.salary_min || job.salary_max) {
    const cur = job.salary_currency ? job.salary_currency + " " : "";
    const lo = job.salary_min != null ? job.salary_min : "";
    const hi = job.salary_max != null ? job.salary_max : "";
    return `${cur}${lo}${hi && hi !== lo ? " - " + hi : ""}`.trim();
  }
  return "";
}

function formatDate(value) {
  if (!value) return "";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString();
}

/* ---------- results table ---------- */
function renderJobs(items) {
  const body = $("results-body");
  body.textContent = ""; // clear safely
  items.forEach((job) => {
    const row = document.createElement("tr");
    row.appendChild(td(job.title, "wrap"));
    row.appendChild(td(job.company_name));
    row.appendChild(td(job.location));
    row.appendChild(td(job.workplace_type));
    row.appendChild(td(job.employment_type));
    row.appendChild(td(job.experience_level));
    row.appendChild(td(Array.isArray(job.skills) ? job.skills.join(", ") : "", "wrap"));
    row.appendChild(td(formatSalary(job)));
    row.appendChild(td(job.salary_period));
    row.appendChild(td(job.applicant_count));
    row.appendChild(td(formatDate(job.posted_date)));
    row.appendChild(td(job.easy_apply === true ? "Yes" : job.easy_apply === false ? "No" : ""));

    const actions = document.createElement("td");
    const viewBtn = document.createElement("button");
    viewBtn.type = "button";
    viewBtn.className = "btn";
    viewBtn.textContent = "View";
    viewBtn.addEventListener("click", () => openModal(job.id));
    actions.appendChild(viewBtn);

    if (job.job_url) {
      const link = document.createElement("a");
      link.href = job.job_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.className = "link-out";
      link.textContent = " LinkedIn";
      actions.appendChild(link);
    }
    row.appendChild(actions);
    body.appendChild(row);
  });
}

function updatePagination(page, totalPages) {
  state.page = page;
  state.totalPages = Math.max(totalPages, 1);
  $("page-info").textContent = `Page ${page} of ${state.totalPages}`;
  $("page-prev").disabled = page <= 1;
  $("page-next").disabled = page >= state.totalPages;
}

function currentFilters() {
  const params = new URLSearchParams();
  const map = {
    keyword: "f-keyword", company: "f-company", location: "f-location",
    country: "f-country", skill: "f-skill", workplace_type: "f-workplace_type",
    employment_type: "f-employment_type", experience_level: "f-experience_level",
    easy_apply: "f-easy_apply",
  };
  for (const [key, id] of Object.entries(map)) {
    const val = $(id).value.trim();
    if (val !== "") params.set(key, val);
  }
  const sort = $("f-sort").value;
  if (sort) params.set("sort", sort);
  return params;
}

async function loadTable(page) {
  const loading = $("results-loading");
  const empty = $("results-empty");
  loading.hidden = false;
  empty.hidden = true;
  try {
    let data;
    if (state.mode === "search" && state.scrapingJobId) {
      data = await apiFetch(
        `/scraping-jobs/${state.scrapingJobId}/results?page=${page}&page_size=${PAGE_SIZE}`
      );
    } else {
      const params = currentFilters();
      params.set("page", page);
      params.set("page_size", PAGE_SIZE);
      data = await apiFetch(`/jobs?${params.toString()}`);
    }
    const items = data.items || [];
    renderJobs(items);
    empty.hidden = items.length > 0;
    updatePagination(data.pagination.page, data.pagination.total_pages);
  } catch (err) {
    showMessage("error", err.message);
  } finally {
    loading.hidden = true;
  }
}

/* ---------- scraping flow ---------- */
function buildSearchPayload() {
  const payload = { keywords: $("keywords").value.trim() };
  const optional = ["location", "experience_level", "employment_type", "workplace_type", "date_posted"];
  optional.forEach((name) => {
    const v = $(name).value.trim();
    if (v) payload[name] = v;
  });
  payload.easy_apply_only = $("easy_apply_only").checked;
  const maxJobs = parseInt($("max_jobs").value, 10);
  if (!Number.isNaN(maxJobs)) payload.max_jobs = maxJobs;
  return payload;
}

function validateSearch() {
  const kw = $("keywords");
  if (!kw.value.trim()) {
    kw.classList.add("invalid");
    $("form-error").textContent = "Keywords are required.";
    kw.focus();
    return false;
  }
  kw.classList.remove("invalid");
  $("form-error").textContent = "";
  return true;
}

function setStat(id, value) {
  $(id).textContent = value != null ? value : 0;
}

function renderProgress(job) {
  $("progress-section").hidden = false;
  const badge = $("job-status");
  badge.textContent = job.status;
  badge.dataset.status = job.status;
  setStat("stat-discovered", job.discovered_jobs);
  setStat("stat-processed", job.processed_jobs);
  setStat("stat-successful", job.successful_jobs);
  setStat("stat-duplicate", job.duplicate_jobs);
  setStat("stat-failed", job.failed_jobs);
  $("job-started").textContent = job.started_at ? new Date(job.started_at).toLocaleString() : "—";
  $("job-completed").textContent = job.completed_at ? new Date(job.completed_at).toLocaleString() : "—";

  let pct = 0;
  if (["completed", "partially_completed"].includes(job.status)) pct = 100;
  else if (job.discovered_jobs > 0) pct = Math.round((job.processed_jobs / job.discovered_jobs) * 100);
  pct = Math.max(0, Math.min(100, pct));
  $("progress-fill").style.width = pct + "%";
  $("progress-percent").textContent = pct + "%";
}

function stopPolling() {
  if (state.pollTimer) {
    clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }
}

async function pollStatus() {
  try {
    const job = await apiFetch(`/scraping-jobs/${state.scrapingJobId}`);
    renderProgress(job);
    if (ACTIVE_STATES.includes(job.status)) {
      state.pollTimer = setTimeout(pollStatus, POLL_INTERVAL_MS);
      return;
    }
    // Terminal state.
    stopPolling();
    handleTerminal(job);
  } catch (err) {
    stopPolling();
    showMessage("error", err.message);
  }
}

function handleTerminal(job) {
  const blocked = blockedMessageFor(job.error_message);
  if (job.status === "completed") {
    showMessage("success", "Scraping completed. Loading results…");
    loadSearchResults();
  } else if (job.status === "partially_completed") {
    showMessage("warn", "Scraping partially completed — some jobs could not be processed. Loading results…");
    loadSearchResults();
  } else if (job.status === "failed") {
    showMessage("error", blocked || "Scraping failed. No results were saved.");
  } else if (job.status === "cancelled") {
    showMessage("warn", "Scraping was cancelled. Any completed results are preserved.");
    loadSearchResults();
  }
}

function loadSearchResults() {
  state.mode = "search";
  loadTable(1);
}

async function onSearchSubmit(event) {
  event.preventDefault();
  if (state.submitting) return; // avoid duplicate submissions
  if (!validateSearch()) return;

  state.submitting = true;
  const submitBtn = $("search-submit");
  submitBtn.disabled = true;
  clearMessage();
  stopPolling();

  try {
    const created = await apiFetch("/search-jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildSearchPayload()),
    });
    state.scrapingJobId = created.scraping_job_id;
    $("export-search-csv").disabled = false;
    $("export-search-json").disabled = false;

    try {
      await apiFetch(`/scraping-jobs/${state.scrapingJobId}/start`, { method: "POST" });
    } catch (startErr) {
      if (startErr.status === 409) {
        showMessage("warn", "This scraping job is already running.");
      } else {
        throw startErr;
      }
    }
    showMessage("info", "Scraping started. Tracking progress…");
    await pollStatus();
  } catch (err) {
    if (err.status === 422) {
      showMessage("error", "Invalid search. Please check your filters (keywords are required).");
    } else {
      showMessage("error", err.message);
    }
  } finally {
    state.submitting = false;
    submitBtn.disabled = false;
  }
}

/* ---------- modal ---------- */
function setField(id, value) {
  $(id).textContent = value === null || value === undefined || value === "" ? "Not available" : String(value);
}

async function openModal(jobId) {
  try {
    const job = await apiFetch(`/jobs/${encodeURIComponent(jobId)}`);
    setField("modal-title", job.title || "Untitled role");
    setField("modal-company", job.company_name);
    setField("modal-location", job.location);
    setField("modal-workplace", job.workplace_type);
    setField("modal-employment", job.employment_type);
    setField("modal-experience", job.experience_level);
    setField("modal-salary", formatSalary(job) || null);
    setField("modal-period", job.salary_period);
    setField("modal-applicants", job.applicant_count);
    setField("modal-posted", job.posted_date ? formatDate(job.posted_date) : null);
    setField("modal-recruiter", job.recruiter_name);

    const skills = $("modal-skills");
    skills.textContent = "";
    if (Array.isArray(job.skills) && job.skills.length) {
      job.skills.forEach((s) => {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = s;
        skills.appendChild(chip);
      });
    } else {
      skills.textContent = "Not available";
    }
    setField("modal-description", job.description);

    const link = $("modal-link");
    if (job.job_url) {
      link.href = job.job_url;
      link.hidden = false;
    } else {
      link.hidden = true;
    }

    const modal = $("job-modal");
    modal.hidden = false;
    $("modal-close").focus();
  } catch (err) {
    if (err.status === 404) {
      showMessage("error", "That job could not be found.");
    } else {
      showMessage("error", err.message);
    }
  }
}

function closeModal() {
  $("job-modal").hidden = true;
}

/* ---------- exports ---------- */
function download(url) {
  window.open(url, "_blank", "noopener");
}

/* ---------- wire up ---------- */
function init() {
  $("search-form").addEventListener("submit", onSearchSubmit);

  $("filter-form").addEventListener("submit", (e) => {
    e.preventDefault();
    state.mode = "browse";
    loadTable(1);
  });
  $("clear-filters").addEventListener("click", () => {
    ["f-keyword", "f-company", "f-location", "f-country", "f-skill"].forEach((id) => ($(id).value = ""));
    ["f-workplace_type", "f-employment_type", "f-experience_level", "f-easy_apply"].forEach((id) => ($(id).value = ""));
    $("f-sort").value = "newest";
    state.mode = "browse";
    loadTable(1);
  });

  $("page-prev").addEventListener("click", () => { if (state.page > 1) loadTable(state.page - 1); });
  $("page-next").addEventListener("click", () => { if (state.page < state.totalPages) loadTable(state.page + 1); });

  // Exports
  $("export-all-csv").addEventListener("click", () => download(`${API}/export/csv?${currentFilters().toString()}`));
  $("export-all-json").addEventListener("click", () => download(`${API}/export/json?${currentFilters().toString()}`));
  $("export-search-csv").addEventListener("click", () => {
    if (state.scrapingJobId) download(`${API}/scraping-jobs/${state.scrapingJobId}/export/csv`);
  });
  $("export-search-json").addEventListener("click", () => {
    if (state.scrapingJobId) download(`${API}/scraping-jobs/${state.scrapingJobId}/export/json`);
  });

  // Modal close interactions
  $("modal-close").addEventListener("click", closeModal);
  $("modal-backdrop").addEventListener("click", closeModal);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("job-modal").hidden) closeModal();
  });

  // Initial browse load (shows demo/existing data).
  loadTable(1);
}

document.addEventListener("DOMContentLoaded", init);
