(function () {
  "use strict";

  // ── State ──────────────────────────────────────────────────────────────────
  const state = {
    userId: null,
    userName: "",
    userEmail: "",
    pollHandle: null,
  };

  // ── URL params ─────────────────────────────────────────────────────────────
  const params       = new URLSearchParams(window.location.search);
  const urlUserId    = params.get("user_id") || "";
  const urlEmail     = params.get("user_email") || params.get("email") || "";
  const urlName      = params.get("user_name")  || params.get("name")  || "";
  const urlEnrollId  = params.get("enrollment_id") || "";

  // ── DOM helpers ────────────────────────────────────────────────────────────
  const $   = (id) => document.getElementById(id);
  const VIEWS = ["identify","history","upload","reviewing","review","compare"];

  function showView(name) {
    VIEWS.forEach((v) => {
      const el = $("view-" + v);
      if (el) el.classList.toggle("hidden", v !== name);
    });
  }

  function esc(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function showError(msg) {
    $("error-msg").textContent = msg;
    $("error-banner").classList.remove("hidden");
    setTimeout(() => $("error-banner").classList.add("hidden"), 8000);
  }

  // ── Boot ───────────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    bindForms();
    bindNav();
    if (urlUserId) {
      identify(urlUserId, urlEmail, urlName, urlEnrollId);
    } else {
      showView("identify");
    }
  });

  // ── Identify ───────────────────────────────────────────────────────────────
  async function identify(thinkificId, email, name, enrollmentId) {
    try {
      const fd = new FormData();
      fd.append("thinkific_user_id", thinkificId);
      if (email)      fd.append("email", email);
      if (name)       fd.append("name", name);
      if (enrollmentId) fd.append("enrollment_id", enrollmentId);

      const res  = await fetch("/api/identify", { method: "POST", body: fd });
      if (!res.ok) throw new Error("Could not verify your account (" + res.status + ")");
      const data = await res.json();

      state.userId    = data.user_id;
      state.userName  = data.name  || name  || "";
      state.userEmail = data.email || email || "";

      if (state.userName)  $("user-name").textContent  = state.userName;
      if (state.userEmail) $("user-email").textContent = state.userEmail;

      await loadHistory();
    } catch (err) {
      showError(err.message);
      showView("identify");
    }
  }

  function bindForms() {
    // Identify form (fallback)
    $("identify-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const id    = $("manual-user-id").value.trim();
      const email = $("manual-email").value.trim();
      if (!id) return;
      await identify(id, email, "", "");
    });

    // Upload form
    $("upload-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const type   = $("submission-type").value;
      const fileEl = $("submission-file");
      if (!type || !fileEl.files?.length) return;

      const btn = $("btn-submit-upload");
      btn.disabled = true;
      btn.textContent = "Uploading…";

      const fd = new FormData();
      fd.append("user_id", state.userId);
      fd.append("submission_type", type);
      fd.append("file", fileEl.files[0]);

      try {
        const res = await fetch("/api/submissions", { method: "POST", body: fd });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Upload failed (" + res.status + ")");
        }
        const data = await res.json();
        $("reviewing-version").textContent =
          (type === "case_summary" ? "Case Summary" : "Case Report") +
          " v" + data.version_number;
        showView("reviewing");
        startPolling(data.submission_id);
      } catch (err) {
        showError(err.message);
        btn.disabled = false;
        btn.textContent = "Get AI Feedback";
      }
    });
  }

  function bindNav() {
    $("btn-new-submission").addEventListener("click", () => {
      $("upload-form").reset();
      $("btn-submit-upload").disabled = false;
      $("btn-submit-upload").textContent = "Get AI Feedback";
      showView("upload");
    });
    $("btn-cancel-upload").addEventListener("click",    loadHistory);
    $("btn-back-to-history").addEventListener("click",  loadHistory);
    $("btn-back-from-compare").addEventListener("click",loadHistory);
    $("btn-new-version").addEventListener("click", () => {
      $("upload-form").reset();
      $("btn-submit-upload").disabled = false;
      $("btn-submit-upload").textContent = "Get AI Feedback";
      showView("upload");
    });
    $("btn-compare").addEventListener("click", loadCompare);
  }

  // ── History ────────────────────────────────────────────────────────────────
  async function loadHistory() {
    stopPolling();
    showView("history");
    const list = $("submission-list");
    list.innerHTML = '<div class="status-msg">Loading your submissions…</div>';
    try {
      const res  = await fetch("/api/submissions?user_id=" + state.userId);
      const data = await res.json();
      renderHistory(data.submissions || []);
    } catch (err) {
      list.innerHTML = '<div class="status-msg error">' + esc(err.message) + '</div>';
    }
  }

  function renderHistory(subs) {
    const list = $("submission-list");
    if (!subs.length) {
      list.innerHTML = '<div class="status-msg">No submissions yet. Upload your first draft to get started.</div>';
      return;
    }
    list.innerHTML = "";
    subs.forEach((s) => {
      const typeLabel = s.submission_type === "case_summary" ? "Case Summary" : "Case Report";
      const date      = new Date(s.created_at).toLocaleDateString("en-US", { dateStyle: "medium" });
      const done      = s.review_status === "done";
      const running   = s.review_status === "running";

      let badge = "";
      if (done)    badge = '<span class="badge ' + (s.estimated_pass ? "badge-pass" : "badge-fail") + '">' + (s.estimated_pass ? "PASS" : "FAIL") + "</span>";
      else if (running) badge = '<span class="badge badge-pending">Analyzing…</span>';
      else         badge = '<span class="badge badge-pending">' + esc(s.review_status) + "</span>";

      const scoreText = s.estimated_total != null
        ? Math.round(s.estimated_total) + " / " + s.estimated_max + " (" + (s.estimated_pct || 0).toFixed(1) + "%)"
        : "—";

      const card = document.createElement("div");
      card.className = "sub-card";
      if (done) card.dataset.clickable = "1";
      card.innerHTML =
        '<div class="sub-card-top">' +
          '<div><span class="sub-type">' + esc(typeLabel) + "</span>" +
            '<span class="sub-ver">v' + s.version_number + "</span>" + badge + "</div>" +
          '<span class="sub-date">' + esc(date) + "</span>" +
        "</div>" +
        '<div class="sub-card-bot">' +
          '<span class="sub-file">' + esc(s.filename || "—") + "</span>" +
          '<span class="sub-score">' + esc(scoreText) + "</span>" +
        "</div>";

      if (done) card.addEventListener("click", () => loadReview(s.id));
      if (running) startPolling(s.id);
      list.appendChild(card);
    });
  }

  // ── Polling ────────────────────────────────────────────────────────────────
  function startPolling(submissionId) {
    stopPolling();
    let attempts = 0;
    async function poll() {
      try {
        const res  = await fetch("/api/submissions/" + submissionId);
        const data = await res.json();
        if (data.review_status === "done") { renderReview(data); return; }
        if (data.review_status === "error") {
          showError("AI feedback failed. Please try uploading again.");
          await loadHistory(); return;
        }
      } catch (_) {}
      attempts++;
      state.pollHandle = setTimeout(poll, Math.min(3000 + attempts * 500, 8000));
    }
    state.pollHandle = setTimeout(poll, 2000);
  }

  function stopPolling() {
    if (state.pollHandle) { clearTimeout(state.pollHandle); state.pollHandle = null; }
  }

  // ── Load existing review ───────────────────────────────────────────────────
  async function loadReview(submissionId) {
    try {
      const res  = await fetch("/api/submissions/" + submissionId);
      const data = await res.json();
      renderReview(data);
    } catch (err) { showError(err.message); }
  }

  // ── Render review dashboard ────────────────────────────────────────────────
  const SCORE_COLORS = ["#ef4444","#f97316","#eab308","#3b82f6","#22c55e"];

  function renderReview(sub) {
    stopPolling();
    const rev = sub.review;
    if (!rev) { showError("Feedback data unavailable."); return; }

    const typeLabel = sub.submission_type === "case_summary" ? "Case Summary" : "Case Report";
    const date      = new Date(sub.created_at).toLocaleDateString("en-US", { dateStyle: "long" });

    $("review-type").textContent    = typeLabel;
    $("review-version").textContent = "Version " + sub.version_number;
    $("review-date").textContent    = date;
    $("review-filename").textContent = sub.filename || "";

    // Score summary
    const total = rev.estimated_total ?? 0;
    const max   = rev.estimated_max   ?? 420;
    const pct   = rev.estimated_pct   ?? 0;
    const pass  = !!rev.estimated_pass;

    $("score-value").textContent  = Math.round(total) + " / " + max;
    $("score-pct").textContent    = pct.toFixed(1) + "%";
    $("score-verdict").textContent = pass ? "PASS" : "FAIL";
    $("score-verdict").className   = "verdict " + (pass ? "pass" : "fail");
    $("score-bar-fill").style.width      = Math.min(pct, 100) + "%";
    $("score-bar-fill").style.background = pass ? "#22c55e" : "#ef4444";

    // Sections
    const sectionsEl = $("section-scores");
    sectionsEl.innerHTML = "";
    Object.entries(rev.section_scores || {}).forEach(([key, val]) => {
      const score  = val.score ?? 0;
      const color  = SCORE_COLORS[score] || "#888";
      const label  = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
      const pctBar = (score / 4) * 100;

      const row = document.createElement("div");
      row.className = "sec-row";
      row.innerHTML =
        '<div class="sec-name">' + esc(label) + "</div>" +
        '<div class="sec-bar-wrap">' +
          '<div class="sec-bar"><div class="sec-bar-fill" style="width:' + pctBar + '%;background:' + color + '"></div></div>' +
          '<span class="sec-score-lbl" style="color:' + color + '">' + score + " / 4</span>" +
        "</div>" +
        '<div class="sec-rationale">' + esc(val.rationale || "") + "</div>";
      sectionsEl.appendChild(row);
    });

    // Overall impressions
    renderOI("oi-a", rev.overall_impression_a, rev.overall_impression_a_rationale,
      "Case management commensurate with ABVP diplomate level of practice");
    renderOI("oi-b", rev.overall_impression_b, rev.overall_impression_b_rationale,
      "Overall structure and presentation is of professional quality");

    // Word count
    const wcPass = !!rev.word_count_pass;
    $("wc-row").innerHTML =
      '<div class="oi-header">' +
        '<span class="' + (wcPass ? "pass-text" : "fail-text") + '">' + (wcPass ? "✓ PASS" : "✗ FAIL") + "</span>" +
        '<span class="oi-label">Word Count</span>' +
      "</div>" +
      '<div class="oi-rat oi-note">' + esc((rev.word_count_estimate || 0).toLocaleString()) + " words — " + esc(rev.word_count_note || "") + "</div>";

    // Auto-fails
    if (rev.auto_fail_reasons?.length) {
      $("section-autofails").classList.remove("hidden");
      renderList("autofails-list", rev.auto_fail_reasons, "");
    } else {
      $("section-autofails").classList.add("hidden");
    }

    // Formatting
    if (rev.formatting_deductions || rev.formatting_notes?.length) {
      $("section-formatting").classList.remove("hidden");
      $("fmt-deductions").textContent = rev.formatting_deductions + " pts";
      renderList("fmt-list", rev.formatting_notes || [], "");
    } else {
      $("section-formatting").classList.add("hidden");
    }

    // Strengths / Weaknesses
    renderList("strengths-list", rev.strengths  || [], "strength-item");
    renderList("weaknesses-list", rev.weaknesses || [], "weakness-item");

    showView("review");
    window.scrollTo(0, 0);
  }

  function renderOI(id, pass, rationale, label) {
    $(id).innerHTML =
      '<div class="oi-header">' +
        '<span class="' + (pass ? "pass-text" : "fail-text") + '">' + (pass ? "✓ PASS" : "✗ FAIL") + "</span>" +
        '<span class="oi-label">' + esc(label) + "</span>" +
      "</div>" +
      (rationale ? '<div class="oi-rat">' + esc(rationale) + "</div>" : "");
  }

  function renderList(id, items, cls) {
    const el = $(id);
    el.innerHTML = "";
    items.forEach((item) => {
      const li = document.createElement("li");
      if (cls) li.className = cls;
      li.textContent = item;
      el.appendChild(li);
    });
  }

  // ── Compare / progress ─────────────────────────────────────────────────────
  async function loadCompare() {
    try {
      const res  = await fetch("/api/submissions?user_id=" + state.userId);
      const data = await res.json();
      const subs = data.submissions || [];
      const csH  = subs.filter((s) => s.submission_type === "case_summary" && s.estimated_total != null);
      const crH  = subs.filter((s) => s.submission_type === "case_report"  && s.estimated_total != null);
      renderCompare(csH, crH);
    } catch (err) { showError(err.message); }
  }

  function renderCompare(csHistory, crHistory) {
    const wrap = $("compare-content");
    wrap.innerHTML = "";

    if (!csHistory.length && !crHistory.length) {
      wrap.innerHTML = '<div class="status-msg">No completed feedback sessions to compare yet.</div>';
      showView("compare"); return;
    }

    [
      { label: "Case Summary", history: csHistory, max: 400, passScore: 280 },
      { label: "Case Report",  history: crHistory, max: 420, passScore: 294 },
    ]
    .filter((g) => g.history.length)
    .forEach((g) => {
      const group = document.createElement("div");
      group.className = "compare-group";

      const title = document.createElement("div");
      title.className = "compare-group-title";
      title.textContent = g.label;
      group.appendChild(title);

      // Table
      const table = document.createElement("table");
      table.className = "compare-table";
      table.innerHTML =
        "<thead><tr><th>Version</th><th>Date</th><th>Score</th><th>%</th><th>Result</th></tr></thead>";
      const tbody = document.createElement("tbody");
      // Most recent first
      g.history.slice().reverse().forEach((s) => {
        const tr   = document.createElement("tr");
        tr.dataset.clickable = "1";
        const date = new Date(s.created_at).toLocaleDateString("en-US", { dateStyle: "medium" });
        tr.innerHTML =
          "<td>v" + s.version_number + "</td>" +
          "<td>" + esc(date) + "</td>" +
          "<td>" + Math.round(s.estimated_total) + " / " + g.max + "</td>" +
          "<td>" + (s.estimated_pct || 0).toFixed(1) + "%</td>" +
          '<td><span class="badge ' + (s.estimated_pass ? "badge-pass" : "badge-fail") + '">' +
            (s.estimated_pass ? "PASS" : "FAIL") + "</span></td>";
        tr.addEventListener("click", () => loadReview(s.id));
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      group.appendChild(table);

      // Bar chart (oldest to newest, left to right)
      if (g.history.length > 1) {
        const chart = document.createElement("div");
        chart.className = "progress-chart";

        const lbl = document.createElement("div");
        lbl.className = "chart-label";
        lbl.textContent = "Score progression (oldest → newest)";
        chart.appendChild(lbl);

        const bars = document.createElement("div");
        bars.className = "chart-bars";

        g.history.forEach((s) => {
          const pct  = ((s.estimated_total || 0) / g.max) * 100;
          const wrap2 = document.createElement("div");
          wrap2.className = "chart-bar-wrap";
          const bar = document.createElement("div");
          bar.className = "chart-bar";
          bar.style.height     = pct + "%";
          bar.style.background = s.estimated_pass ? "#22c55e" : "#ef4444";
          bar.title = Math.round(s.estimated_total) + "/" + g.max;
          const lbl2 = document.createElement("div");
          lbl2.className = "chart-bar-lbl";
          lbl2.textContent = "v" + s.version_number;
          wrap2.appendChild(bar);
          wrap2.appendChild(lbl2);
          bars.appendChild(wrap2);
        });

        // 70% threshold line
        const passLinePct = (g.passScore / g.max * 100).toFixed(1);
        const thr = document.createElement("div");
        thr.className = "chart-threshold";
        thr.style.bottom = passLinePct + "%";
        const thrLbl = document.createElement("span");
        thrLbl.className = "chart-threshold-lbl";
        thrLbl.textContent = "70% pass";
        thr.appendChild(thrLbl);
        bars.appendChild(thr);

        chart.appendChild(bars);
        group.appendChild(chart);
      }

      wrap.appendChild(group);
    });

    showView("compare");
    window.scrollTo(0, 0);
  }

})();

