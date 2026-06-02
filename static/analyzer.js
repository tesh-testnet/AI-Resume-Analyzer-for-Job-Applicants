"use strict";

// ========== API BASE (empty = same origin, works on Render) ==========
const API_BASE = "";

// ========== GLOBAL STATE ==========
let currentRoleResult = null;
let currentCustomResult = null;
let lastRoleFile = null,
  lastRole = "",
  lastLevel = "";
let lastCustomFile = null,
  lastCustomJD = "";
let activeMode = "role";
let predChartInst = null;
let analysisLimitReached = false;
let analysisLimitReady = false;
let isAuthenticated = false;

// ========== DOM ELEMENTS ==========
const uploadScreen = document.getElementById("upload-screen");
const loadingScreen = document.getElementById("loading-screen");
const errorScreen = document.getElementById("error-screen");
const resultsRole = document.getElementById("results-screen-role");
const resultsCustom = document.getElementById("results-screen-custom");
const toastEl = document.getElementById("toast");
const toastMsg = document.getElementById("toast-msg");
const modeBtns = document.querySelectorAll(".mode-btn");
const roleModeForm = document.getElementById("role-mode-form");
const customModeForm = document.getElementById("custom-mode-form");
const dropZoneRole = document.getElementById("drop-zone-role");
const fileInputRole = document.getElementById("file-input-role");
const roleFilenameSpan = document.getElementById("drop-filename-role");
const roleSelect = document.getElementById("role-select");
const levelSelect = document.getElementById("level-select");
const submitRoleBtn = document.getElementById("submit-role-btn");
const dropZoneCustom = document.getElementById("drop-zone-custom");
const fileInputCustom = document.getElementById("file-input-custom");
const customFilenameSpan = document.getElementById("drop-filename-custom");
const jdTextarea = document.getElementById("job-description");
const jdCounter = document.getElementById("jd-counter");
const submitCustomBtn = document.getElementById("submit-custom-btn");
const prevBanner = document.getElementById("prev-banner");
const prevSummary = document.getElementById("prev-summary");
const newAnalysisBtn = document.getElementById("new-analysis-btn");
const usageLimitBanner = document.getElementById("usage-limit-banner");
const signupLink = document.getElementById("signup-link");

// ========== ANONYMOUS LIMIT (localStorage) ==========
const ANONYMOUS_LIMIT = 2;
const ANON_COUNT_KEY = "anonymousAnalysisCount";

function getAnonymousCount() {
  const val = localStorage.getItem(ANON_COUNT_KEY);
  return val ? parseInt(val, 10) : 0;
}

function incrementAnonymousCount() {
  const newCount = getAnonymousCount() + 1;
  localStorage.setItem(ANON_COUNT_KEY, newCount);
  return newCount;
}

function resetAnonymousCount() {
  localStorage.removeItem(ANON_COUNT_KEY);
}

// ========== CHECK LIMIT BASED ON AUTH STATE ==========
async function checkAndApplyLimit() {
  if (isAuthenticated) {
    analysisLimitReached = false;
    analysisLimitReady = true;
    if (usageLimitBanner) usageLimitBanner.style.display = "none";
    disableSubmitButtons(false);
    console.log("[LIMIT] Authenticated user – unlimited access");
    return;
  }

  const used = getAnonymousCount();
  analysisLimitReached = used >= ANONYMOUS_LIMIT;
  analysisLimitReady = true;
  if (usageLimitBanner) {
    usageLimitBanner.style.display = analysisLimitReached ? "block" : "none";
  }
  disableSubmitButtons(analysisLimitReached);
  console.log(
    "[LIMIT] Anonymous user, used:",
    used,
    "reached:",
    analysisLimitReached,
  );
}

function disableSubmitButtons(disabled) {
  if (submitRoleBtn) submitRoleBtn.disabled = disabled || !lastRoleFile;
  if (submitCustomBtn)
    submitCustomBtn.disabled =
      disabled || !(lastCustomFile && jdTextarea.value.trim().length >= 20);
}

window.setAuthenticated = (auth) => {
  isAuthenticated = auth;
  checkAndApplyLimit();
};
window.checkAndApplyLimit = checkAndApplyLimit;

async function incrementAnalysisCount() {
  if (isAuthenticated) return;
  incrementAnonymousCount();
  await checkAndApplyLimit();
}
window.incrementAnalysisCount = incrementAnalysisCount;

// ========== UTILITIES ==========
function showToast(msg) {
  toastMsg.textContent = msg;
  toastEl.classList.add("show");
  setTimeout(() => toastEl.classList.remove("show"), 4500);
}

function showLoading(text) {
  document.getElementById("loader-text").textContent = text;
  uploadScreen.style.display = "none";
  resultsRole.classList.remove("active");
  resultsCustom.classList.remove("active");
  errorScreen.classList.remove("active");
  loadingScreen.classList.add("active");
  newAnalysisBtn.style.display = "none";
  console.log("[LOADING]", text);
}

function hideLoading() {
  loadingScreen.classList.remove("active");
  console.log("[LOADING] hidden");
}

function showError(title, body, detail) {
  hideLoading();
  uploadScreen.style.display = "none";
  resultsRole.classList.remove("active");
  resultsCustom.classList.remove("active");
  document.getElementById("err-title").textContent = title;
  document.getElementById("err-body").textContent = body;
  const codeEl = document.getElementById("err-code");
  if (detail) {
    codeEl.style.display = "block";
    codeEl.textContent = detail;
  } else codeEl.style.display = "none";
  errorScreen.classList.add("active");
  lucide.createIcons();
  console.error("[ERROR]", title, body, detail);
}

function resetToUpload() {
  errorScreen.classList.remove("active");
  resultsRole.classList.remove("active");
  resultsCustom.classList.remove("active");
  uploadScreen.style.display = "";
  newAnalysisBtn.style.display = "none";
  if (activeMode === "role") {
    lastRoleFile = null;
    dropZoneRole.classList.remove("has-file");
    roleFilenameSpan.textContent = "";
    fileInputRole.value = "";
    submitRoleBtn.disabled = analysisLimitReached || true;
  } else {
    lastCustomFile = null;
    dropZoneCustom.classList.remove("has-file");
    customFilenameSpan.textContent = "";
    fileInputCustom.value = "";
    jdTextarea.value = "";
    jdCounter.textContent = "0 characters";
    submitCustomBtn.disabled = analysisLimitReached || true;
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
  updatePrevBanner();
  console.log("[UI] Reset to upload screen");
}

function updatePrevBanner() {
  if (activeMode === "role" && currentRoleResult) {
    prevSummary.innerHTML = `Last: <strong>${currentRoleResult.selected_role} (${currentRoleResult.selected_level})</strong> — Score ${currentRoleResult.overall_score.toFixed(1)} · ${currentRoleResult.fit_label}`;
    prevBanner.classList.add("visible");
  } else if (activeMode === "custom" && currentCustomResult) {
    const title = currentCustomResult.job_title || "Custom JD";
    prevSummary.innerHTML = `Last: <strong>${escapeHtml(title)}</strong> — Similarity ${currentCustomResult.similarity_score}% · ${currentCustomResult.matching_skills.length} matching skills`;
    prevBanner.classList.add("visible");
  } else {
    prevBanner.classList.remove("visible");
  }
}

function viewPreviousResult() {
  if (activeMode === "role" && currentRoleResult)
    showRoleResults(currentRoleResult);
  else if (activeMode === "custom" && currentCustomResult)
    showCustomResults(currentCustomResult);
}

// ========== LOAD ROLES FROM BACKEND (dynamic select) ==========
async function loadRoleSuggestions() {
  try {
    const res = await fetch(API_BASE + "/roles");
    if (!res.ok) throw new Error("Failed to fetch roles");
    const roles = await res.json();
    if (roleSelect) {
      roleSelect.innerHTML = "";
      roles.forEach((role) => {
        const option = document.createElement("option");
        option.value = role;
        option.textContent = role;
        roleSelect.appendChild(option);
      });
      if (roles.length > 0) roleSelect.value = roles[0];
      console.log("[ROLES] Loaded:", roles);
    }
  } catch (err) {
    console.warn("[ROLES] Could not load roles from backend:", err);
    roleSelect.innerHTML = '<option value="">Select a role...</option>';
  }
}

// ========== DRAG & DROP ROLE ==========
function onRoleFileSelected(file) {
  if (!file) return;
  const ext = file.name.split(".").pop().toLowerCase();
  if (!["pdf", "docx", "txt"].includes(ext)) {
    showToast("Only PDF, DOCX, or TXT files are supported.");
    return;
  }
  lastRoleFile = file;
  dropZoneRole.classList.add("has-file");
  const sizeStr =
    file.size > 1048576
      ? (file.size / 1048576).toFixed(1) + " MB"
      : (file.size / 1024).toFixed(0) + " KB";
  roleFilenameSpan.textContent = "✓ " + file.name + " (" + sizeStr + ")";
  submitRoleBtn.disabled = analysisLimitReached || false;
  console.log("[ROLE] File selected:", file.name);
}
dropZoneRole.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZoneRole.classList.add("drag-over");
});
dropZoneRole.addEventListener("dragleave", () =>
  dropZoneRole.classList.remove("drag-over"),
);
dropZoneRole.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZoneRole.classList.remove("drag-over");
  if (e.dataTransfer.files[0]) onRoleFileSelected(e.dataTransfer.files[0]);
});
fileInputRole.addEventListener("change", () => {
  if (fileInputRole.files[0]) onRoleFileSelected(fileInputRole.files[0]);
});

// ========== DRAG & DROP CUSTOM ==========
function onCustomFileSelected(file) {
  if (!file) return;
  const ext = file.name.split(".").pop().toLowerCase();
  if (!["pdf", "docx", "txt"].includes(ext)) {
    showToast("Only PDF, DOCX, or TXT files are supported.");
    return;
  }
  lastCustomFile = file;
  dropZoneCustom.classList.add("has-file");
  const sizeStr =
    file.size > 1048576
      ? (file.size / 1048576).toFixed(1) + " MB"
      : (file.size / 1024).toFixed(0) + " KB";
  customFilenameSpan.textContent = "✓ " + file.name + " (" + sizeStr + ")";
  validateCustomForm();
  console.log("[CUSTOM] File selected:", file.name);
}
dropZoneCustom.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZoneCustom.classList.add("drag-over");
});
dropZoneCustom.addEventListener("dragleave", () =>
  dropZoneCustom.classList.remove("drag-over"),
);
dropZoneCustom.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZoneCustom.classList.remove("drag-over");
  if (e.dataTransfer.files[0]) onCustomFileSelected(e.dataTransfer.files[0]);
});
fileInputCustom.addEventListener("change", () => {
  if (fileInputCustom.files[0]) onCustomFileSelected(fileInputCustom.files[0]);
});
jdTextarea.addEventListener("input", () => {
  jdCounter.textContent = jdTextarea.value.length + " characters";
  validateCustomForm();
});
function validateCustomForm() {
  const hasFile = lastCustomFile !== null;
  const hasJD = jdTextarea.value.trim().length >= 20;
  submitCustomBtn.disabled = analysisLimitReached || !(hasFile && hasJD);
}

// ========== MODE SWITCHING ==========
function setMode(mode) {
  activeMode = mode;
  modeBtns.forEach((btn) => {
    if (btn.dataset.mode === mode) btn.classList.add("active");
    else btn.classList.remove("active");
  });
  if (mode === "role") {
    roleModeForm.classList.add("active");
    customModeForm.classList.remove("active");
  } else {
    roleModeForm.classList.remove("active");
    customModeForm.classList.add("active");
    validateCustomForm();
  }
  updatePrevBanner();
  console.log("[MODE] Switched to", mode);
}
modeBtns.forEach((btn) =>
  btn.addEventListener("click", () => setMode(btn.dataset.mode)),
);

// ========== ANIMATION HELPER ==========
function animateCount(el, from, to, dur, suffix, dec) {
  if (!el) return;
  let start = null;
  function tick(ts) {
    if (!start) start = ts;
    const p = Math.min((ts - start) / dur, 1);
    const ease = 1 - Math.pow(1 - p, 3);
    el.textContent = (from + (to - from) * ease).toFixed(dec) + (suffix || "");
    if (p < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

window.scrollToRole = function (id) {
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: "smooth" });
  else console.warn("[SCROLL] Element not found:", id);
};

// ========== ROLE ANALYSIS ==========
submitRoleBtn.addEventListener("click", async () => {
  if (analysisLimitReached && !isAuthenticated) {
    showError(
      "Usage limit reached",
      "You have used your 2 free analyses. Please sign in to continue.",
      "LIMIT",
    );
    return;
  }
  if (!lastRoleFile) {
    showToast("Please select a resume file.");
    return;
  }
  const role = roleSelect.value.trim();
  const level = levelSelect.value;
  if (!role || role === "") {
    showToast("Please select a target role.");
    return;
  }
  lastRole = role;
  lastLevel = level;

  const fd = new FormData();
  fd.append("file", lastRoleFile);
  fd.append("role", role);
  fd.append("level", level);

  showLoading("Analyzing against role profile…");
  try {
    console.log("[API] POST /analyze", { role, level });
    const res = await fetch(API_BASE + "/analyze", {
      method: "POST",
      body: fd,
      signal: AbortSignal.timeout(60000),
    });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`HTTP ${res.status}: ${errText}`);
    }
    const data = await res.json();
    if (!data || typeof data.overall_score === "undefined") {
      throw new Error("Invalid response structure: missing overall_score");
    }
    currentRoleResult = data;
    showRoleResults(data);
    hideLoading();
    await window.incrementAnalysisCount();
    await checkAndApplyLimit();
  } catch (err) {
    console.error("[API] Role analysis failed:", err);
    hideLoading();
    showError("Role analysis failed", err.message, "Check console for details");
  }
});

// ========== FULL ROLE RESULTS RENDERING ==========
function showRoleResults(d) {
  console.log("[RENDER] Showing role results");
  const role = d.selected_role || "Unknown";
  const level = d.selected_level || "—";
  const score = typeof d.overall_score === "number" ? d.overall_score : 0;
  const fitLabel = d.fit_label || "Low";
  const cs = d.component_scores || {};
  const cp = d.candidate_profile || {};
  const rp = d.role_prediction || {};
  const lr = d.level_recommendation || {};
  const matchingSkills = Array.isArray(d.matching_skills)
    ? d.matching_skills
    : [];
  const missingSkills = Array.isArray(d.missing_skills) ? d.missing_skills : [];
  const detectedSkills = Array.isArray(cp.detected_skills)
    ? cp.detected_skills
    : [];
  const skillPct =
    typeof d.skill_match_percentage === "number" ? d.skill_match_percentage : 0;
  const recs = Array.isArray(d.recommendations) ? d.recommendations : [];
  const sectionC = cp.section_completeness || {};
  const contactInfo = cp.contact_info || {};

  const html = `
    <section class="r-hero">
      <div class="r-hero-bg"></div>
      <div class="r-hero-content">
        <div class="r-eyebrow"><i data-lucide="check-circle" style="width:12px;height:12px"></i> Analysis Complete</div>
        <h2 class="r-heading">${escapeHtml(role)},<br><em>analyzed.</em></h2>
        <p class="r-sub">Role: ${escapeHtml(role)} (${escapeHtml(level)}) · ${escapeHtml(fitLabel)}. Detected ${detectedSkills.length} skills across ${(cp.experience_years || 0).toFixed(1)} years of experience.</p>
        <div class="score-ring"><svg class="score-ring-svg" viewBox="0 0 200 200" fill="none"><circle cx="100" cy="100" r="82" stroke="var(--border)" stroke-width="8"/><circle id="r-arc" cx="100" cy="100" r="82" stroke="var(--p)" stroke-width="8" stroke-linecap="round" stroke-dasharray="515" stroke-dashoffset="515" transform="rotate(-90 100 100)"/><circle id="r-arc-glow" cx="100" cy="100" r="82" stroke="var(--p)" stroke-width="14" stroke-linecap="round" stroke-dasharray="515" stroke-dashoffset="515" transform="rotate(-90 100 100)" opacity=".15" filter="url(#rblur)"/><defs><filter id="rblur"><feGaussianBlur stdDeviation="3"/></filter></defs></svg><div class="score-ring-inner"><div class="score-big"><span id="r-score-num">0</span></div><div class="score-ring-label">Overall Score</div></div></div>
        <div class="fit-badge ${fitLabel.toLowerCase().includes("high") ? "fit-high" : fitLabel.toLowerCase().includes("medium") ? "fit-medium" : "fit-low"}"><i data-lucide="target" style="width:14px;height:14px"></i><span>${escapeHtml(fitLabel)} — ${escapeHtml(role)} (${escapeHtml(level)})</span></div>
        <div class="r-cta"><button class="btn btn-primary" onclick="scrollToRole('r-scores')"><i data-lucide="bar-chart-2"></i> View Full Report</button><button class="btn btn-ghost" onclick="scrollToRole('r-recs')"><i data-lucide="lightbulb"></i> See Recommendations</button></div>
      </div>
      <div class="scroll-hint"><i data-lucide="chevrons-down"></i></div>
    </section>
    <section class="scores-section" id="r-scores"><div class="scores-grid"><div class="score-cell"><div class="score-cell-num"><span id="sc-text">0</span>%</div><div class="score-cell-label">Text Similarity</div><div class="score-cell-bar" id="bar-text" style="background:var(--warn)"></div></div><div class="score-cell"><div class="score-cell-num"><span id="sc-skill">0</span>%</div><div class="score-cell-label">Skill Match</div><div class="score-cell-bar" id="bar-skill"></div></div><div class="score-cell"><div class="score-cell-num"><span id="sc-exp">0</span>%</div><div class="score-cell-label">Experience Match</div><div class="score-cell-bar" id="bar-exp" style="background:var(--success)"></div></div><div class="score-cell"><div class="score-cell-num"><span id="sc-edu">0</span>%</div><div class="score-cell-label">Education Match</div><div class="score-cell-bar" id="bar-edu" style="background:var(--success)"></div></div></div></section>
    <section class="section" id="r-skills"><div class="container"><div class="section-header"><div class="snum">Skills Analysis</div><h2 class="stitle">What you <em>bring</em> to the role</h2><p class="ssub" id="skills-sub"></p></div><div class="skills-layout"><div class="skills-panel"><div class="sp-header"><div class="sp-icon" style="background:var(--ph2);color:var(--p)"><i data-lucide="check-circle-2"></i></div><div><div class="sp-title">Matching Skills</div><div class="sp-sub" id="match-count"></div></div></div><div class="chips" id="matching-chips"></div><div class="progress-wrap"><div class="pr-row"><span class="pr-name">Required skills coverage</span><span class="pr-pct" id="skill-pct-label">0%</span></div><div class="bar-track"><div class="bar-fill" id="skill-bar"></div></div></div></div><div class="skills-panel"><div class="sp-header"><div class="sp-icon" style="background:var(--surface-off);color:var(--muted)"><i data-lucide="layers"></i></div><div><div class="sp-title">All Detected Skills</div><div class="sp-sub" id="detected-count"></div></div></div><div class="chips" id="detected-chips"></div><div id="missing-alert"></div></div></div></div></section>
    <hr class="divider"><section class="section" id="r-pred"><div class="container"><div class="section-header"><div class="snum">Role Prediction</div><h2 class="stitle">What your resume <em>signals</em></h2><p class="ssub">Based on your skills and experience, our ML model predicts your strongest role alignments.</p></div><div class="pred-layout"><div class="pred-card"><div style="display:flex;align-items:center;gap:var(--s3);margin-bottom:var(--s2)"><div style="width:40px;height:40px;border-radius:var(--r-md);background:var(--ph2);display:flex;align-items:center;justify-content:center;color:var(--p)"><i data-lucide="brain"></i></div><div><div style="font-size:var(--text-xs);font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)">Predicted Role</div><div style="font-family:var(--fd);font-size:var(--text-xl);font-style:italic" id="pred-role-name"></div></div></div><div id="pred-match-note"></div><div class="pred-list" id="pred-list"></div></div><div class="chart-wrap"><div class="chart-title">Confidence Distribution</div><div class="chart-sub">Top predicted roles</div><div class="chart-inner"><canvas id="predChart"></canvas></div></div></div></div></section>
    <hr class="divider"><section class="section" id="r-levels"><div class="container"><div class="section-header"><div class="snum">Level Recommendation</div><h2 class="stitle">Where you <em>fit</em> best</h2><p class="ssub" id="level-sub"></p></div><div class="level-grid" id="level-grid"></div><div class="meta-grid" id="meta-grid"></div></div></section>
    <hr class="divider"><section class="section" style="padding-block:var(--s12)" id="r-complete"><div class="container"><div class="section-header"><div class="snum">Resume Completeness</div><h2 class="stitle">Section <em>checklist</em></h2></div><div class="complete-grid" id="complete-grid"></div></div></section>
    <hr class="divider"><section class="section" id="r-recs"><div class="container"><div class="section-header"><div class="snum">Recommendations</div><h2 class="stitle">Your action <em>plan</em></h2><p class="ssub">Prioritized steps to strengthen your resume and improve your fit score.</p></div><div class="recs-list" id="recs-list"></div></div></section>
    <footer class="footer"><div class="footer-logo">ResumeAI</div><div class="footer-sub">Powered by machine learning · CRF NER · Custom role classification</div></footer>
  `;
  resultsRole.innerHTML = html;
  resultsRole.classList.add("active");
  uploadScreen.style.display = "none";
  newAnalysisBtn.style.display = "flex";
  updatePrevBanner();
  window.scrollTo({ top: 0, behavior: "smooth" });
  lucide.createIcons();

  const fitLow = fitLabel.toLowerCase();
  const arcEl = document.getElementById("r-arc");
  const glowEl = document.getElementById("r-arc-glow");
  const arcClass = fitLow.includes("high")
    ? "arc-high"
    : fitLow.includes("medium")
      ? "arc-medium"
      : "arc-low";
  if (arcEl) arcEl.setAttribute("class", arcClass);
  if (glowEl) glowEl.setAttribute("class", arcClass);
  setTimeout(() => {
    const offset = 515 - (score / 100) * 515;
    if (arcEl) arcEl.style.strokeDashoffset = offset;
    if (glowEl) glowEl.style.strokeDashoffset = offset;
    animateCount(document.getElementById("r-score-num"), 0, score, 1800, "", 1);
  }, 200);

  const textSim = (cs.text_similarity || 0) * 100;
  const skillMatch = (cs.skill_match || 0) * 100;
  const expMatch = (cs.experience_match || 0) * 100;
  const eduMatch = (cs.education_match || 0) * 100;
  setTimeout(() => {
    animateCount(document.getElementById("sc-text"), 0, textSim, 1200, "", 1);
    animateCount(
      document.getElementById("sc-skill"),
      0,
      skillMatch,
      1200,
      "",
      1,
    );
    animateCount(document.getElementById("sc-exp"), 0, expMatch, 1200, "", 1);
    animateCount(document.getElementById("sc-edu"), 0, eduMatch, 1200, "", 1);
    const barText = document.getElementById("bar-text");
    const barSkill = document.getElementById("bar-skill");
    const barExp = document.getElementById("bar-exp");
    const barEdu = document.getElementById("bar-edu");
    if (barText) barText.style.width = textSim + "%";
    if (barSkill) barSkill.style.width = skillMatch + "%";
    if (barExp) barExp.style.width = expMatch + "%";
    if (barEdu) barEdu.style.width = eduMatch + "%";
  }, 400);

  document.getElementById("skills-sub").textContent =
    `Matching your detected skills against the job requirements for ${role} (${level}).`;
  document.getElementById("match-count").textContent =
    matchingSkills.length +
    " of " +
    (matchingSkills.length + missingSkills.length) +
    " required skills";
  document.getElementById("detected-count").textContent =
    detectedSkills.length + " skills from resume";
  const matchWrap = document.getElementById("matching-chips");
  const detWrap = document.getElementById("detected-chips");
  if (matchWrap && detWrap) {
    matchWrap.innerHTML = "";
    detWrap.innerHTML = "";
    const matchSet = new Set(matchingSkills);
    matchingSkills.forEach((s) => {
      const c = document.createElement("span");
      c.className = "chip chip-match";
      c.innerHTML = `<i data-lucide="check" style="width:10px;height:10px"></i>${escapeHtml(s)}`;
      matchWrap.appendChild(c);
    });
    missingSkills.forEach((s) => {
      const c = document.createElement("span");
      c.className = "chip chip-missing";
      c.innerHTML = `<i data-lucide="x" style="width:10px;height:10px"></i>${escapeHtml(s)}`;
      matchWrap.appendChild(c);
    });
    detectedSkills.forEach((s) => {
      const c = document.createElement("span");
      c.className =
        "chip " + (matchSet.has(s) ? "chip-match" : "chip-detected");
      c.textContent = s;
      detWrap.appendChild(c);
    });
  }
  const mAlert = document.getElementById("missing-alert");
  if (mAlert) {
    if (missingSkills.length) {
      mAlert.innerHTML = `<div class="alert-box alert-err"><div class="alert-title">Missing Required Skills</div><div class="alert-body"><strong>${missingSkills.map((s) => escapeHtml(s.toUpperCase())).join(", ")}</strong> — not detected.</div></div>`;
    } else {
      mAlert.innerHTML = `<div class="alert-box alert-success"><div class="alert-title">All required skills matched!</div><div class="alert-body">Every required skill for ${role} was found.</div></div>`;
    }
  }
  setTimeout(() => {
    animateCount(
      document.getElementById("skill-pct-label"),
      0,
      skillPct,
      1400,
      "%",
      1,
    );
    const skillBar = document.getElementById("skill-bar");
    if (skillBar) skillBar.style.width = skillPct + "%";
  }, 600);

  const predRoleName = document.getElementById("pred-role-name");
  if (predRoleName) predRoleName.textContent = rp.predicted_role || "—";
  const noteDiv = document.getElementById("pred-match-note");
  if (noteDiv) {
    if (rp.matches_selected_role) {
      noteDiv.innerHTML = `<div class="alert-box alert-success"><div class="alert-title">Role Match Confirmed</div><div class="alert-body">Strong alignment with your selected role.</div></div>`;
    } else {
      noteDiv.innerHTML = `<div class="alert-box alert-warn"><div class="alert-title">Role Mismatch Note</div><div class="alert-body">Model predicts <strong>${escapeHtml(rp.predicted_role || "?")}</strong> but you selected <strong>${escapeHtml(role)}</strong>. Consider adding more ${escapeHtml(role)}-specific terminology.</div></div>`;
    }
  }
  const preds = rp.top_3_predictions || [];
  const predList = document.getElementById("pred-list");
  if (predList) {
    predList.innerHTML = "";
    preds.forEach((p, i) => {
      const pct = (p.confidence * 100).toFixed(1);
      const div = document.createElement("div");
      div.className = "pred-row" + (i === 0 ? " pred-top" : "");
      div.innerHTML = `<div class="pred-meta"><span class="pred-name">${escapeHtml(p.role)}</span><span class="pred-conf">${pct}%</span></div><div class="bar-track"><div class="bar-fill" data-width="${pct}" style="${i > 0 ? "background:var(--muted)" : ""}"></div></div>`;
      predList.appendChild(div);
    });
    setTimeout(() => {
      predList.querySelectorAll(".bar-fill[data-width]").forEach((b) => {
        b.style.width = b.dataset.width + "%";
      });
    }, 700);
  }

  const levelGrid = document.getElementById("level-grid");
  if (levelGrid) {
    levelGrid.innerHTML = "";
    const levelScores = lr.level_fit_scores || {};
    const recommended = lr.recommended_level || "";
    Object.entries(levelScores).forEach(([lvl, scoreVal]) => {
      const pct = (scoreVal * 100).toFixed(1);
      const div = document.createElement("div");
      div.className = "level-card" + (lvl === recommended ? " rec" : "");
      div.innerHTML = `${lvl === recommended ? '<div class="level-badge">Best Fit</div>' : ""}<div class="level-name">${escapeHtml(lvl)} Level</div><div class="level-num">${pct}%</div><div class="level-label">Fit Score</div><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>`;
      levelGrid.appendChild(div);
    });
  }
  const levelSub = document.getElementById("level-sub");
  if (levelSub) {
    levelSub.textContent = `Fit scores based on ${(cp.experience_years || 0).toFixed(1)} years of experience and ${cp.education || "—"} education.`;
  }

  const metaGrid = document.getElementById("meta-grid");
  if (metaGrid) {
    metaGrid.innerHTML = `<div class="meta-item"><div class="meta-icon"><i data-lucide="graduation-cap"></i></div><div><div class="meta-label">Education</div><div class="meta-value">${escapeHtml(cp.education || "—")}</div></div></div><div class="meta-item"><div class="meta-icon"><i data-lucide="briefcase"></i></div><div><div class="meta-label">Experience</div><div class="meta-value">${(cp.experience_years || 0).toFixed(1)} Years</div></div></div><div class="meta-item"><div class="meta-icon"><i data-lucide="mail"></i></div><div><div class="meta-label">Contact</div><div class="meta-value">${escapeHtml(contactInfo.email || "—")}</div></div></div>`;
  }

  const completeGrid = document.getElementById("complete-grid");
  if (completeGrid) {
    completeGrid.innerHTML = "";
    const checks = [
      { key: "has_summary", label: "Professional Summary" },
      { key: "has_experience", label: "Work Experience" },
      { key: "has_education", label: "Education" },
      { key: "has_skills", label: "Skills" },
      { key: "has_projects", label: "Projects" },
    ];
    checks.forEach(({ key, label }) => {
      const has = !!sectionC[key];
      const div = document.createElement("div");
      div.className = "complete-item";
      div.innerHTML = `<div class="cdot ${has ? "yes" : "no"}"></div><span class="cname">${escapeHtml(label)}</span><span class="cstatus ${has ? "yes" : "no"}">${has ? "Present" : "Missing"}</span>`;
      completeGrid.appendChild(div);
    });
  }

  const recsList = document.getElementById("recs-list");
  if (recsList) {
    recsList.innerHTML = "";
    const priorityMap = {
      High: { cls: "badge-high", accent: "var(--err)", icon: "alert-circle" },
      Medium: {
        cls: "badge-medium",
        accent: "var(--warn)",
        icon: "alert-triangle",
      },
      Info: {
        cls: "badge-info",
        accent: "var(--success)",
        icon: "check-circle",
      },
    };
    recs.forEach((rec) => {
      const p = priorityMap[rec.priority] || priorityMap.Info;
      const div = document.createElement("div");
      div.className = "rec-card";
      div.style.setProperty("--ra", p.accent);
      div.innerHTML = `<div class="rec-icon"><i data-lucide="${p.icon}"></i></div><div class="rec-body"><div class="rec-cat">${escapeHtml(rec.category || "General")}</div><div class="rec-msg">${escapeHtml(rec.message)}</div><div class="rec-action">${escapeHtml(rec.action || "")}</div></div><span class="rec-badge ${p.cls}">${escapeHtml(rec.priority || "Info")}</span>`;
      recsList.appendChild(div);
    });
  }

  if (predChartInst) predChartInst.destroy();
  if (preds.length) {
    const ctx = document.getElementById("predChart");
    if (ctx) {
      const isDark =
        document.documentElement.getAttribute("data-theme") === "dark";
      const primary = getComputedStyle(document.documentElement)
        .getPropertyValue("--p")
        .trim();
      const labels = preds.map((p) => p.role);
      const values = preds.map((p) => +(p.confidence * 100).toFixed(1));
      const rem = Math.max(0, 100 - values.reduce((a, b) => a + b, 0));
      predChartInst = new Chart(ctx, {
        type: "doughnut",
        data: {
          labels: [...labels, "Other"],
          datasets: [
            {
              data: [...values, rem],
              backgroundColor: [
                primary,
                isDark ? "rgba(255,255,255,.14)" : "rgba(0,0,0,.1)",
                isDark ? "rgba(255,255,255,.07)" : "rgba(0,0,0,.05)",
                isDark ? "rgba(255,255,255,.03)" : "rgba(0,0,0,.02)",
              ],
              borderColor: "transparent",
              borderWidth: 0,
              hoverOffset: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "70%",
          animation: { duration: 1200 },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (c) => ` ${c.label}: ${c.parsed.toFixed(1)}%`,
              },
            },
          },
        },
      });
    }
  }

  lucide.createIcons();
  console.log("[RENDER] Role results displayed successfully");
}

// ========== CUSTOM JD ANALYSIS ==========
submitCustomBtn.addEventListener("click", async () => {
  if (analysisLimitReached && !isAuthenticated) {
    showError(
      "Usage limit reached",
      "You have used your 2 free analyses. Please sign in to continue.",
      "LIMIT",
    );
    return;
  }
  if (!lastCustomFile) {
    showToast("Please select a resume file.");
    return;
  }
  const jdText = jdTextarea.value.trim();
  if (jdText.length < 20) {
    showToast("Job description must be at least 20 characters.");
    return;
  }
  lastCustomJD = jdText;

  const fd = new FormData();
  fd.append("file", lastCustomFile);
  fd.append("jd_text", jdText);

  showLoading("Comparing resume with job description…");
  try {
    console.log("[API] POST /compare-job-description");
    const res = await fetch(API_BASE + "/compare-job-description", {
      method: "POST",
      body: fd,
      signal: AbortSignal.timeout(60000),
    });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`HTTP ${res.status}: ${errText}`);
    }
    const data = await res.json();
    console.log("[API] Custom response:", data);
    if (typeof data.similarity_score === "undefined") {
      throw new Error("Invalid response: missing similarity_score");
    }
    currentCustomResult = data;
    showCustomResults(data);
    hideLoading();
    await window.incrementAnalysisCount();
    await checkAndApplyLimit();
  } catch (err) {
    console.error("[API] Custom analysis failed:", err);
    hideLoading();
    showError("Comparison failed", err.message, "Check console for details");
  }
});

function showCustomResults(data) {
  console.log("[RENDER] Showing custom results");
  const similarity = data.similarity_score;
  let scoreColor = "";
  let fitClass = "";
  if (similarity >= 70) {
    scoreColor = "var(--success)";
    fitClass = "fit-high";
  } else if (similarity >= 40) {
    scoreColor = "var(--warn)";
    fitClass = "fit-medium";
  } else {
    scoreColor = "var(--err)";
    fitClass = "fit-low";
  }

  const jobTitle = data.job_title || "Not specified";
  const requiredEducation = data.required_education || "Not specified";
  const requiredExperience =
    data.required_experience_years !== null &&
    data.required_experience_years !== undefined
      ? data.required_experience_years + " years"
      : "Not specified";

  const html = `
    <section class="r-hero" style="min-height: auto; padding-bottom: var(--s12);">
      <div class="r-hero-bg"></div>
      <div class="r-hero-content">
        <div class="r-eyebrow"><i data-lucide="git-compare" style="width:12px;height:12px"></i> Resume vs Job Description</div>
        <h2 class="r-heading">Comparison <em>results</em></h2>
        <p class="r-sub">Based on skills, experience, and job requirements.</p>
        <div class="custom-score-card" style="border-top: 6px solid ${scoreColor}; max-width: 400px; margin: 0 auto var(--s10);">
          <div class="custom-score-number" style="color: ${scoreColor}">${similarity}%</div>
          <div class="custom-score-label">Overall Match Score</div>
          <div class="progress-bar-custom" style="margin-top: var(--s4);"><div class="progress-fill" style="width: ${similarity}%; background: ${scoreColor}"></div></div>
        </div>
        <div class="fit-badge ${fitClass}" style="margin-bottom: var(--s8);"><i data-lucide="target" style="width:14px;height:14px"></i><span>${similarity >= 70 ? "Strong Match" : similarity >= 40 ? "Moderate Match" : "Weak Match"}</span></div>
      </div>
    </section>
    <section class="section"><div class="container"><div class="section-header"><div class="snum">Job Requirements</div><h2 class="stitle">What the <em>job description</em> asks for</h2><p class="ssub">Automatically extracted from the job posting.</p></div><div class="meta-grid" style="margin-top: 0;"><div class="meta-item"><div class="meta-icon"><i data-lucide="briefcase"></i></div><div><div class="meta-label">Position Title</div><div class="meta-value">${escapeHtml(jobTitle)}</div></div></div><div class="meta-item"><div class="meta-icon"><i data-lucide="graduation-cap"></i></div><div><div class="meta-label">Required Education</div><div class="meta-value">${escapeHtml(requiredEducation)}</div></div></div><div class="meta-item"><div class="meta-icon"><i data-lucide="clock"></i></div><div><div class="meta-label">Experience Required</div><div class="meta-value">${escapeHtml(requiredExperience)}</div></div></div></div><p class="ssub" style="text-align: center; margin-top: var(--s4); font-size: var(--text-xs);">⚡ These fields are automatically extracted from the job description. ${!data.job_title ? "Your backend can be enhanced to return more precise data by adding NLP extraction." : ""}</p></div></section>
    <hr class="divider">
    <section class="section"><div class="container"><div class="section-header"><div class="snum">Skill Gap Analysis</div><h2 class="stitle">What you <em>bring</em> vs <em>what’s needed</em></h2><p class="ssub">Comparing your resume skills against the job description.</p></div><div class="skills-layout"><div class="skills-panel"><div class="sp-header"><div class="sp-icon" style="background:var(--ph2);color:var(--p)"><i data-lucide="check-circle-2"></i></div><div><div class="sp-title">Matching Skills</div><div class="sp-sub">${data.matching_skills.length} skills found in both</div></div></div><div class="chips">${data.matching_skills.map((s) => `<span class="chip chip-match">${escapeHtml(s)}</span>`).join("") || '<span class="chip">None</span>'}</div></div><div class="skills-panel"><div class="sp-header"><div class="sp-icon" style="background:var(--err-bg);color:var(--err)"><i data-lucide="x-circle"></i></div><div><div class="sp-title">Missing in Resume</div><div class="sp-sub">Required by JD but not detected</div></div></div><div class="chips">${data.missing_in_resume.map((s) => `<span class="chip chip-missing">${escapeHtml(s)}</span>`).join("") || '<span class="chip">None – great job!</span>'}</div></div></div></div></section>
    <footer class="footer"><div class="footer-logo">ResumeAI</div><div class="footer-sub">Powered by machine learning · CRF NER · Custom role classification</div></footer>
  `;

  resultsCustom.innerHTML = html;
  resultsCustom.classList.add("active");
  uploadScreen.style.display = "none";
  newAnalysisBtn.style.display = "flex";
  updatePrevBanner();
  window.scrollTo({ top: 0, behavior: "smooth" });
  lucide.createIcons();
  console.log("[RENDER] Custom results displayed");
}

// ========== HEALTH CHECK & ADMIN ==========
async function checkHealth() {
  try {
    const res = await fetch(API_BASE + "/health", {
      signal: AbortSignal.timeout(5000),
    });
    if (res.ok) {
      document.getElementById("status-dot").className = "status-dot online";
      document.getElementById("status-text").textContent = "API Online";
    } else throw new Error();
  } catch {
    document.getElementById("status-dot").className = "status-dot offline";
    document.getElementById("status-text").textContent = "API Offline";
  }
}
checkHealth();
setInterval(checkHealth, 30000);

function openAdmin() {
  document.getElementById("admin-overlay").classList.add("open");
  document.getElementById("admin-sheet").classList.add("open");
  lucide.createIcons();
}
function closeAdmin() {
  document.getElementById("admin-overlay").classList.remove("open");
  document.getElementById("admin-sheet").classList.remove("open");
}
async function doRebuild() {
  const btn = document.getElementById("rebuild-btn");
  const statusDiv = document.getElementById("rebuild-status");
  const key = document.getElementById("admin-key").value.trim();
  if (!key) {
    statusDiv.innerHTML =
      '<span style="color:var(--err)">Enter admin key.</span>';
    return;
  }
  btn.disabled = true;
  statusDiv.innerHTML = "Rebuilding...";
  try {
    const res = await fetch(API_BASE + "/rebuild-profiles", {
      method: "POST",
      headers: { "X-Admin-Key": key },
      signal: AbortSignal.timeout(30000),
    });
    if (!res.ok) throw new Error();
    const data = await res.json();
    statusDiv.innerHTML =
      '<span style="color:var(--success)">✓ Profiles rebuilt.</span>';
  } catch {
    statusDiv.innerHTML =
      '<span style="color:var(--err)">Rebuild failed.</span>';
  } finally {
    btn.disabled = false;
  }
}

// ========== THEME ==========
(function () {
  const r = document.documentElement;
  let d =
    r.getAttribute("data-theme") ||
    (matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light");
  r.setAttribute("data-theme", d);
  function updateThemeIcon() {
    const t = document.querySelector("[data-theme-toggle]");
    if (t) {
      t.innerHTML =
        d === "dark"
          ? '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
          : '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
    }
  }
  updateThemeIcon();
  document
    .querySelector("[data-theme-toggle]")
    .addEventListener("click", () => {
      d = d === "dark" ? "light" : "dark";
      r.setAttribute("data-theme", d);
      updateThemeIcon();
      if (predChartInst) {
        const isDark = d === "dark";
        const primary = getComputedStyle(r).getPropertyValue("--p").trim();
        predChartInst.data.datasets[0].backgroundColor = [
          primary,
          isDark ? "rgba(255,255,255,.14)" : "rgba(0,0,0,.1)",
          isDark ? "rgba(255,255,255,.07)" : "rgba(0,0,0,.05)",
          isDark ? "rgba(255,255,255,.03)" : "rgba(0,0,0,.02)",
        ];
        predChartInst.update();
      }
    });
})();

// ========== INITIAL ANIMATIONS & MODE ==========
window.addEventListener("load", async () => {
  setTimeout(() => {
    const el = document.getElementById("u-eyebrow");
    if (el)
      Object.assign(el.style, { opacity: "1", transform: "translateY(0)" });
  }, 100);
  setTimeout(() => {
    const el = document.getElementById("u-heading");
    if (el) el.style.opacity = "1";
  }, 250);
  setTimeout(() => {
    const el = document.getElementById("u-sub");
    if (el)
      Object.assign(el.style, { opacity: "1", transform: "translateY(0)" });
  }, 400);
  lucide.createIcons();
  setMode("role");
  await loadRoleSuggestions();
  await checkAndApplyLimit();

  if (signupLink) {
    signupLink.href = "/static/auth.html";
    signupLink.target = "_self";
  }

  console.log("[INIT] App ready");
});

window.retryLastAnalysis = function () {
  if (activeMode === "role" && lastRoleFile) submitRoleBtn.click();
  else if (activeMode === "custom" && lastCustomFile) submitCustomBtn.click();
  else resetToUpload();
};

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/[&<>]/g, function (m) {
    if (m === "&") return "&amp;";
    if (m === "<") return "&lt;";
    if (m === ">") return "&gt;";
    return m;
  });
}
