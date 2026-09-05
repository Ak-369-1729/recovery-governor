/**
 * Recovery Sandbox - Interactive Decision Simulator & Portfolio Arena
 * Supports: Mode A (Single Event), Mode B (Portfolio Simulation), Dynamic What-If Matrix,
 * AI vs Governor Visualizer, Counterfactual Replay, Recovery AI Readiness Score, and Emergency Kill Switch.
 */

window.SandboxView = {
  activeMode: "single", // "single" | "portfolio"
  presets: {},
  currentScenarioResult: null,

  init: async function () {
    this.bindEvents();
    await this.loadPresets();
    await this.loadAutonomyStatus();
    await this.checkKillSwitch();
    // Default load preset A
    this.selectPreset("scenario_a");
  },

  bindEvents: function () {
    // Mode switcher buttons
    const btnModeSingle = document.getElementById("btn-mode-single");
    const btnModePortfolio = document.getElementById("btn-mode-portfolio");
    if (btnModeSingle && btnModePortfolio) {
      btnModeSingle.addEventListener("click", () => this.switchMode("single"));
      btnModePortfolio.addEventListener("click", () => this.switchMode("portfolio"));
    }

    // Preset selector buttons
    document.querySelectorAll(".btn-preset-chip").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const presetKey = e.currentTarget.getAttribute("data-preset");
        this.selectPreset(presetKey);
      });
    });

    // Run Single Event Scenario
    const btnRunScenario = document.getElementById("btn-run-sandbox-scenario");
    if (btnRunScenario) {
      btnRunScenario.addEventListener("click", () => this.runSingleScenario());
    }

    // Run Portfolio Simulation
    const btnRunPortfolio = document.getElementById("btn-run-portfolio-sim");
    if (btnRunPortfolio) {
      btnRunPortfolio.addEventListener("click", () => this.runPortfolioSimulation());
    }

    // Run Sensitivity Analysis
    const btnRunSensitivity = document.getElementById("btn-run-sensitivity-analysis");
    if (btnRunSensitivity) {
      btnRunSensitivity.addEventListener("click", () => this.runSensitivityAnalysis());
    }

    // Emergency Kill Switch Header Button
    const btnKill = document.getElementById("btn-kill-switch");
    if (btnKill) {
      btnKill.addEventListener("click", () => this.toggleKillSwitch());
    }
  },

  switchMode: function (mode) {
    this.activeMode = mode;
    const singleContainer = document.getElementById("sandbox-single-container");
    const portfolioContainer = document.getElementById("sandbox-portfolio-container");
    const btnSingle = document.getElementById("btn-mode-single");
    const btnPortfolio = document.getElementById("btn-mode-portfolio");

    if (mode === "single") {
      singleContainer.style.display = "block";
      portfolioContainer.style.display = "none";
      btnSingle.classList.add("active");
      btnPortfolio.classList.remove("active");
    } else {
      singleContainer.style.display = "none";
      portfolioContainer.style.display = "block";
      btnSingle.classList.remove("active");
      btnPortfolio.classList.add("active");
      this.runPortfolioSimulation();
    }
  },

  loadPresets: async function () {
    try {
      const res = await API.get("/api/sandbox/presets");
      if (res && res.presets) {
        this.presets = res.presets;
      }
    } catch (e) {
      console.error("Failed to load presets:", e);
    }
  },

  selectPreset: function (presetKey) {
    const preset = this.presets[presetKey];
    if (!preset) return;

    // Highlight active chip
    document.querySelectorAll(".btn-preset-chip").forEach((chip) => {
      if (chip.getAttribute("data-preset") === presetKey) {
        chip.classList.add("active");
      } else {
        chip.classList.remove("active");
      }
    });

    // Populate form fields
    document.getElementById("sbx-amount").value = preset.amount || 4999;
    document.getElementById("sbx-method").value = preset.payment_method || "UPI";
    document.getElementById("sbx-failure-type").value = preset.failure_type || "TEMPORARY_ISSUER_FAILURE";
    document.getElementById("sbx-failure-code").value = preset.failure_code || "ISSUER_504_TIMEOUT";
    document.getElementById("sbx-retry-count").value = preset.retry_count || 0;
    document.getElementById("sbx-customer-ltv").value = preset.customer_ltv || 15000;
    document.getElementById("sbx-contact-count").value = preset.customer_contact_count || 0;
    document.getElementById("sbx-risk-tier").value = preset.risk_tier || "LOW";
    document.getElementById("sbx-channel").value = preset.channel || "MOBILE_APP";

    if (preset.chaos_injection) {
      document.getElementById("sbx-chaos-injection").value = preset.chaos_injection;
    } else {
      document.getElementById("sbx-chaos-injection").value = "";
    }

    if (preset.policy_overrides && preset.policy_overrides.economic_hurdle) {
      document.getElementById("sbx-hurdle").value = preset.policy_overrides.economic_hurdle;
    } else {
      document.getElementById("sbx-hurdle").value = 10.0;
    }

    // Auto-run preset to immediately show results to the judge
    this.runSingleScenario();
  },

  runSingleScenario: async function () {
    const btn = document.getElementById("btn-run-sandbox-scenario");
    if (btn) btn.disabled = true;

    const payload = {
      amount: parseFloat(document.getElementById("sbx-amount").value) || 4999.0,
      currency: "INR",
      payment_method: document.getElementById("sbx-method").value,
      failure_type: document.getElementById("sbx-failure-type").value,
      failure_code: document.getElementById("sbx-failure-code").value,
      retry_count: parseInt(document.getElementById("sbx-retry-count").value) || 0,
      time_since_failure_minutes: 5,
      customer_ltv: parseFloat(document.getElementById("sbx-customer-ltv").value) || 15000.0,
      customer_contact_count: parseInt(document.getElementById("sbx-contact-count").value) || 0,
      risk_tier: document.getElementById("sbx-risk-tier").value,
      channel: document.getElementById("sbx-channel").value,
      operating_mode: document.getElementById("sbx-operating-mode").value,
      chaos_injection: document.getElementById("sbx-chaos-injection").value || null,
      policy_overrides: {
        economic_hurdle: parseFloat(document.getElementById("sbx-hurdle").value) || 10.0,
      },
    };

    try {
      const res = await API.post("/api/sandbox/run", payload);
      this.currentScenarioResult = res;
      this.renderScenarioResults(res);
      showToast("Scenario executed through 10-step Governor pipeline.", "info");
    } catch (err) {
      console.error("Scenario execution error:", err);
      showToast("Execution error: " + err.message, "error");
    } finally {
      if (btn) btn.disabled = false;
    }
  },

  renderScenarioResults: function (data) {
    const dec = data.governor_decision;
    const diag = data.ai_diagnosis;
    const whatif = data.what_if_comparison;
    const exec = data.execution;
    const ver = data.verification;
    const attr = data.attribution;
    const cf = data.counterfactual_replay;

    // 1. Render AI vs Governor Visual Card
    const isOverridden = (dec.selected_action === "STOP" || dec.selected_action === "NO_ACTION") && diag.candidate_actions && diag.candidate_actions.length > 0 && diag.candidate_actions[0].action !== dec.selected_action;
    const isShadow = dec.operating_mode === "SHADOW" || dec.decision_outcome === "SHADOW_APPROVED";

    const aiProposedAction = (diag.candidate_actions && diag.candidate_actions[0]) ? diag.candidate_actions[0].action : "NO_ACTION";

    const htmlAIGov = `
      <div class="ai-side-box">
        <div style="font-size: 0.72rem; font-weight: 700; color: #c4b5fd; text-transform: uppercase; margin-bottom: 6px;">AI Recommendation</div>
        <div style="font-size: 1.25rem; font-weight: 800; color: var(--text-primary);">${aiProposedAction}</div>
        <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px;">Confidence: <b>${Math.round(diag.confidence * 100)}%</b> • Model: <b>${dec.ai_mode}</b></div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 6px; font-style: italic;">"${diag.diagnosis}"</div>
      </div>

      <div class="gate-spine-divider">
        <div class="gate-spine-pill">8 POLICY GATES</div>
        <div style="font-size: 1.1rem; color: ${isOverridden ? 'var(--color-warning)' : 'var(--color-success)'};">
          ${isOverridden ? '⚠️ OVERRIDDEN' : '✓ AUTHORIZED'}
        </div>
      </div>

      <div class="gov-side-box" style="border-color: ${isOverridden ? 'rgba(239, 68, 68, 0.4)' : (isShadow ? 'rgba(245, 158, 11, 0.5)' : 'rgba(16, 185, 129, 0.4)')};">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <div style="font-size: 0.72rem; font-weight: 700; color: var(--color-success); text-transform: uppercase;">Deterministic Governor Decision</div>
          <span class="badge ${dec.decision_outcome === 'APPROVED' ? 'badge-success' : (dec.decision_outcome === 'SHADOW_APPROVED' ? 'badge-warning' : 'badge-danger')}">${dec.decision_outcome}</span>
        </div>
        <div style="font-size: 1.25rem; font-weight: 800; color: var(--text-primary);">${dec.selected_action}</div>
        <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px;">Authority: <b>Deterministic 8-Gate Safety Engine</b></div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 6px;">${dec.reason}</div>
      </div>
    `;
    document.getElementById("sbx-ai-gov-card").innerHTML = htmlAIGov;

    // 2. Render Dynamic What-If Comparison Matrix
    document.getElementById("whatif-action-count-badge").textContent = `${whatif.total_candidate_actions_evaluated} candidate actions evaluated`;

    let whatifHtml = "";
    whatif.evaluations.forEach((item) => {
      const isBest = item.is_governor_choice;
      const isEligible = item.governor_eligible;
      whatifHtml += `
        <tr class="${isBest ? 'whatif-best-row' : (isEligible ? '' : 'whatif-blocked-row')}">
          <td>
            <div style="display: flex; align-items: center; gap: 8px;">
              <b>${item.action_label}</b>
              ${isBest ? '<span class="badge badge-success" style="font-size: 0.65rem;">★ GOVERNOR CHOICE</span>' : ''}
            </div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">${item.description}</div>
          </td>
          <td><b>${(item.recovery_probability * 100).toFixed(1)}%</b></td>
          <td>${formatINR(item.expected_gross_recovery)}</td>
          <td>${formatINR(item.intervention_cost)}</td>
          <td>${formatINR(item.friction_cost + item.risk_cost)}</td>
          <td><b class="${item.net_erv > 0 ? 'text-success' : 'text-danger'}">${formatINR(item.net_erv)}</b></td>
          <td>
            ${isEligible ?
              '<span class="badge badge-success">✓ ELIGIBLE</span>' :
              `<span class="badge badge-danger" title="${item.gate_block_reasons.join(' | ')}">✕ BLOCKED</span>`
            }
          </td>
        </tr>
      `;
    });
    document.getElementById("tbody-whatif-matrix").innerHTML = whatifHtml;

    // 3. Render 10-Stage Execution Trace
    const htmlTrace = `
      <div style="display: flex; flex-direction: column; gap: 14px;">
        <div class="card" style="padding: 16px; background: rgba(255, 255, 255, 0.02);">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <b>STAGE 1 — AI DIAGNOSIS</b>
            <span class="badge badge-purple">${diag.confidence ? (diag.confidence * 100).toFixed(0) + '% Confidence' : 'FALLBACK'}</span>
          </div>
          <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 6px;">${diag.diagnosis}</div>
        </div>

        <div class="card" style="padding: 16px; background: rgba(255, 255, 255, 0.02);">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <b>STAGE 2 — WHAT-IF ERV MODELING</b>
            <span class="badge badge-neutral">${whatif.total_candidate_actions_evaluated} Actions Modeled</span>
          </div>
          <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 6px;">Selected: <b>${whatif.governor_selected_action}</b> with Net ERV of <b>${formatINR(whatif.governor_selected_net_erv)}</b>.</div>
        </div>

        <div class="card" style="padding: 16px; background: rgba(255, 255, 255, 0.02);">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <b>STAGE 3 — GOVERNOR 8 POLICY GATES</b>
            <span class="badge ${dec.decision_outcome.includes('APPROVED') ? 'badge-success' : 'badge-danger'}">${dec.decision_outcome}</span>
          </div>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px;">
            ${dec.policy_checks.map(g => `
              <div style="font-size: 0.75rem; padding: 6px 10px; background: var(--bg-card); border-radius: 4px; border-left: 3px solid ${g.status === 'PASSED' ? 'var(--color-success)' : 'var(--color-danger)'};">
                <div style="font-weight: 700;">${g.gate_name}</div>
                <div style="color: var(--text-muted); font-size: 0.7rem;">${g.status}: ${g.reason.slice(0, 50)}...</div>
              </div>
            `).join('')}
          </div>
        </div>

        <div class="card" style="padding: 16px; background: rgba(255, 255, 255, 0.02);">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <b>STAGE 4 — SIMULATED EXECUTION</b>
            <span class="badge ${exec.adapter_type === 'SHADOW_MODE' ? 'badge-warning' : 'badge-neutral'}">${exec.adapter_type}</span>
          </div>
          <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 6px;">${exec.response_payload.message || 'Action executed safely in simulation environment.'}</div>
        </div>

        <div class="card" style="padding: 16px; background: rgba(255, 255, 255, 0.02);">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <b>STAGE 5 — VERIFICATION & ATTRIBUTION</b>
            <span class="badge ${ver.status === 'SUCCEEDED' ? 'badge-success' : 'badge-warning'}">${ver.status}</span>
          </div>
          <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 6px;">
            Attribution Category: <b>${attr.category}</b> • Net Recovered: <b>${formatINR(attr.net_recovered_value)}</b>
          </div>
        </div>
      </div>
    `;
    document.getElementById("sbx-trace-timeline").innerHTML = htmlTrace;

    // 4. Render Counterfactual Replay
    let cfHtml = "";
    if (cf && cf.actual_path && cf.counterfactual_paths) {
      const allPaths = [cf.actual_path, ...cf.counterfactual_paths];
      allPaths.forEach((path) => {
        cfHtml += `
          <div class="cf-path-card ${!path.is_counterfactual ? 'actual-path' : ''}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <b>${path.label}</b>
              <span class="${!path.is_counterfactual ? 'badge badge-success' : 'badge-counterfactual'}">${!path.is_counterfactual ? 'ACTUAL EXECUTION' : 'SIMULATED COUNTERFACTUAL'}</span>
            </div>
            <div style="font-size: 0.82rem; color: var(--text-secondary);">${path.expected_outcome}</div>
            <div style="display: flex; justify-content: space-between; font-size: 0.82rem; margin-top: 4px; padding-top: 6px; border-top: 1px solid rgba(255, 255, 255, 0.05);">
              <span>Net Value: <b class="${path.net_value_inr >= 0 ? 'text-success' : 'text-danger'}">${formatINR(path.net_value_inr)}</b></span>
              <span style="font-size: 0.72rem; color: var(--text-muted);">${path.attribution_category}</span>
            </div>
            <div style="font-size: 0.7rem; color: var(--text-muted); font-style: italic;">${path.causal_disclaimer}</div>
          </div>
        `;
      });
    }
    document.getElementById("sbx-counterfactual-grid").innerHTML = cfHtml;
  },

  runPortfolioSimulation: async function () {
    const popSize = parseInt(document.getElementById("port-pop-size").value) || 500;
    const seed = parseInt(document.getElementById("port-seed").value) || 42;
    const hurdle = parseFloat(document.getElementById("port-hurdle").value) || 10.0;
    const maxRetries = parseInt(document.getElementById("port-retries").value) || 3;

    try {
      const res = await API.post("/api/sandbox/portfolio", {
        population_size: popSize,
        seed: seed,
        policy_overrides: {
          economic_hurdle: hurdle,
          max_retries: maxRetries,
        },
      });

      this.renderPortfolioResults(res);
      showToast(`Portfolio simulation complete (N = ${popSize}, Seed = ${seed}).`, "info");
    } catch (e) {
      console.error("Portfolio simulation error:", e);
      showToast("Portfolio simulation failed: " + e.message, "error");
    }
  },

  renderPortfolioResults: function (data) {
    const results = data.results;
    if (!results) return;

    // Render Cards
    const strats = ["CONTROL", "NAIVE_BASELINE", "FIXED_DELAY_2H", "ADAPTIVE", "GOVERNOR"];
    let cardsHtml = "";
    let tableHtml = "";

    strats.forEach((s) => {
      const item = results[s];
      if (!item) return;

      const isGov = s === "GOVERNOR";
      cardsHtml += `
        <div class="card" style="border-top: 4px solid ${isGov ? 'var(--color-success)' : (s === 'NAIVE_BASELINE' ? 'var(--color-warning)' : 'var(--text-muted)')}; ${isGov ? 'background: linear-gradient(180deg, rgba(16, 185, 129, 0.05), transparent);' : ''}">
          <div class="metric-label ${isGov ? 'text-success' : ''}">${item.strategy_label}</div>
          <div style="font-size: 1.25rem; font-weight: 800; margin: 8px 0;">${formatINR(item.net_recovery)}</div>
          <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 12px;">Net Recovery (N = ${item.sample_size.toLocaleString()})</div>
          <div style="display: flex; flex-direction: column; gap: 6px; font-size: 0.8rem;">
            <div style="display: flex; justify-content: space-between;"><span>Recovery Rate:</span><b>${(item.recovery_rate * 100).toFixed(1)}%</b></div>
            <div style="display: flex; justify-content: space-between;"><span>Total Costs:</span><b class="${item.intervention_cost > 0 ? 'text-danger' : ''}">${formatINR(item.intervention_cost + item.friction_cost + item.risk_cost)}</b></div>
            <div style="display: flex; justify-content: space-between;"><span>Unsafe Prevented:</span><b class="${item.unsafe_actions_prevented > 0 ? 'text-success' : ''}">${item.unsafe_actions_prevented}</b></div>
            ${item.recovery_lift ? `<div style="display: flex; justify-content: space-between; border-top: 1px solid var(--border-color); padding-top: 4px;"><span>Lift vs Baseline:</span><b class="text-success">${item.recovery_lift > 0 ? '+' : ''}${item.recovery_lift}%</b></div>` : ''}
          </div>
        </div>
      `;

      tableHtml += `
        <tr class="${isGov ? 'whatif-best-row' : ''}">
          <td><b>${item.strategy_label}</b></td>
          <td>${item.sample_size.toLocaleString()}</td>
          <td>${formatINR(item.failed_payment_value)}</td>
          <td>${formatINR(item.recovered_value)}</td>
          <td><b>${(item.recovery_rate * 100).toFixed(1)}%</b></td>
          <td>${formatINR(item.intervention_cost + item.risk_cost + item.friction_cost)}</td>
          <td><b class="${item.net_recovery > 0 ? 'text-success' : 'text-danger'}">${formatINR(item.net_recovery)}</b></td>
          <td><b class="${isGov ? 'text-success' : ''}">${item.unsafe_actions_prevented}</b></td>
        </tr>
      `;
    });

    document.getElementById("port-cards-grid").innerHTML = cardsHtml;
    document.getElementById("tbody-port-table").innerHTML = tableHtml;
  },

  runSensitivityAnalysis: async function () {
    try {
      const res = await API.get("/api/sandbox/sensitivity?population_size=500&seeds=42,43,44,45,46");
      const html = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 12px;">
          <div class="card" style="padding: 14px; background: rgba(16, 185, 129, 0.05);">
            <b class="text-success">GOVERNOR (5 Seeds)</b>
            <div style="font-size: 0.8rem; margin-top: 6px;">Mean Net: <b>${formatINR(res.governor_net_recovery.mean)}</b></div>
            <div style="font-size: 0.8rem;">Median Net: <b>${formatINR(res.governor_net_recovery.median)}</b></div>
            <div style="font-size: 0.8rem;">Min / Max: <b>${formatINR(res.governor_net_recovery.min)}</b> / <b>${formatINR(res.governor_net_recovery.max)}</b></div>
            <div style="font-size: 0.8rem;">Std Dev: <b>±${formatINR(res.governor_net_recovery.std_dev)}</b></div>
          </div>
          <div class="card" style="padding: 14px; background: rgba(245, 158, 11, 0.05);">
            <b class="text-warning">BASELINE (5 Seeds)</b>
            <div style="font-size: 0.8rem; margin-top: 6px;">Mean Net: <b>${formatINR(res.baseline_net_recovery.mean)}</b></div>
            <div style="font-size: 0.8rem;">Median Net: <b>${formatINR(res.baseline_net_recovery.median)}</b></div>
            <div style="font-size: 0.8rem;">Min / Max: <b>${formatINR(res.baseline_net_recovery.min)}</b> / <b>${formatINR(res.baseline_net_recovery.max)}</b></div>
            <div style="font-size: 0.8rem;">Std Dev: <b>±${formatINR(res.baseline_net_recovery.std_dev)}</b></div>
          </div>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 8px;">${res.summary}</div>
      `;
      document.getElementById("sensitivity-results-container").innerHTML = html;
      showToast("Multi-seed sensitivity sweep completed.", "info");
    } catch (e) {
      console.error("Sensitivity analysis error:", e);
      showToast("Sensitivity analysis failed: " + e.message, "error");
    }
  },

  loadAutonomyStatus: async function () {
    try {
      const res = await API.get("/api/sandbox/autonomy");
      if (!res) return;

      const rb = res.readiness_breakdown;
      document.getElementById("readiness-total-score").textContent = rb.total_score.toFixed(1);
      document.getElementById("autonomy-level-badge").textContent = res.level_name;

      const dimHtml = `
        <div class="readiness-dimension-row">
          <div>
            <b>Safety Rate</b>
            <div style="font-size: 0.72rem; color: var(--text-muted);">${rb.safety_notes}</div>
          </div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <div class="readiness-progress-bar-bg"><div class="readiness-progress-bar-fill" style="width: ${(rb.safety_score / rb.safety_max) * 100}%;"></div></div>
            <b>${rb.safety_score.toFixed(1)} / ${rb.safety_max}</b>
          </div>
        </div>
        <div class="readiness-dimension-row">
          <div>
            <b>Economic Efficiency</b>
            <div style="font-size: 0.72rem; color: var(--text-muted);">${rb.economic_efficiency_notes}</div>
          </div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <div class="readiness-progress-bar-bg"><div class="readiness-progress-bar-fill" style="width: ${(rb.economic_efficiency_score / rb.economic_efficiency_max) * 100}%;"></div></div>
            <b>${rb.economic_efficiency_score.toFixed(1)} / ${rb.economic_efficiency_max}</b>
          </div>
        </div>
        <div class="readiness-dimension-row">
          <div>
            <b>Fallback Reliability</b>
            <div style="font-size: 0.72rem; color: var(--text-muted);">${rb.fallback_reliability_notes}</div>
          </div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <div class="readiness-progress-bar-bg"><div class="readiness-progress-bar-fill" style="width: ${(rb.fallback_reliability_score / rb.fallback_reliability_max) * 100}%;"></div></div>
            <b>${rb.fallback_reliability_score.toFixed(1)} / ${rb.fallback_reliability_max}</b>
          </div>
        </div>
        <div class="readiness-dimension-row">
          <div>
            <b>Accuracy & Calibration</b>
            <div style="font-size: 0.72rem; color: var(--text-muted);">${rb.accuracy_calibration_notes}</div>
          </div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <div class="readiness-progress-bar-bg"><div class="readiness-progress-bar-fill" style="width: ${(rb.accuracy_calibration_score / rb.accuracy_calibration_max) * 100}%;"></div></div>
            <b>${rb.accuracy_calibration_score.toFixed(1)} / ${rb.accuracy_calibration_max}</b>
          </div>
        </div>
        <div class="readiness-dimension-row">
          <div>
            <b>Verification & Attribution</b>
            <div style="font-size: 0.72rem; color: var(--text-muted);">${rb.verification_attribution_notes}</div>
          </div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <div class="readiness-progress-bar-bg"><div class="readiness-progress-bar-fill" style="width: ${(rb.verification_attribution_score / rb.verification_attribution_max) * 100}%;"></div></div>
            <b>${rb.verification_attribution_score.toFixed(1)} / ${rb.verification_attribution_max}</b>
          </div>
        </div>
      `;
      document.getElementById("readiness-dimensions-container").innerHTML = dimHtml;
      document.getElementById("autonomy-invariant-notice").textContent = res.architectural_invariant;
    } catch (e) {
      console.error("Autonomy load error:", e);
    }
  },

  checkKillSwitch: async function () {
    try {
      const res = await API.get("/api/sandbox/kill-switch");
      this.updateKillSwitchUI(res);
    } catch (e) {
      console.error("Kill switch check error:", e);
    }
  },

  toggleKillSwitch: async function () {
    try {
      const current = await API.get("/api/sandbox/kill-switch");
      const targetState = !current.is_active;

      const res = await API.post(`/api/sandbox/kill-switch/toggle?active=${targetState}`);
      this.updateKillSwitchUI(res.emergency_stop);

      if (targetState) {
        showToast("🛑 EMERGENCY STOP ENGAGED: All automated recovery interventions globally halted.", "error");
      } else {
        showToast("✓ EMERGENCY STOP RESET: Governor operations restored.", "info");
      }
    } catch (e) {
      console.error("Kill switch toggle error:", e);
    }
  },

  updateKillSwitchUI: function (status) {
    const btn = document.getElementById("btn-kill-switch");
    const label = document.getElementById("kill-switch-label");
    const icon = document.getElementById("kill-switch-icon");
    if (!btn || !label || !icon) return;

    if (status.is_active) {
      btn.classList.add("active-stop");
      icon.textContent = "🛑";
      label.textContent = `STOP ACTIVE: ${status.actions_blocked} BLOCKED (${formatINR(status.potential_exposure_prevented)})`;
    } else {
      btn.classList.remove("active-stop");
      icon.textContent = "🛡️";
      label.textContent = "EMERGENCY STOP: READY";
    }
  },
};
