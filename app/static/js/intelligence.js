/**
 * Payment Intelligence View: Predict -> Prevent -> Recover -> Prove
 * Orchestrates:
 * - Pre-Flight Risk Radar
 * - Simulated Network Health Board & 7-Step Temporal Degradation Timeline
 * - Unified 13-Stage Lifecycle Stepper
 * - Quantitative Prediction Reliability (Precision, Recall, F1, Brier Score, 5-Bin Curve)
 * - Prevention Economics Panel
 * - Explainability Drawer
 */

const IntelligenceView = {
  activeTrace: null,

  init: async function () {
    this.bindEvents();
    await this.loadNetworkHealth();
    await this.loadReliabilityMetrics();
    await this.loadPreventionEconomics();
    await this.loadPredictionHistory();
  },

  bindEvents: function () {
    const btnSim = document.getElementById("btn-intel-run-sim");
    if (btnSim) {
      btnSim.onclick = () => this.runLifecycleSimulation();
    }

    const scenarioSel = document.getElementById("intel-scenario-select");
    if (scenarioSel) {
      scenarioSel.onchange = () => this.loadNetworkHealth();
    }

    const seedInput = document.getElementById("intel-seed-input");
    if (seedInput) {
      seedInput.onchange = () => this.loadNetworkHealth();
    }
  },

  loadNetworkHealth: async function () {
    try {
      const scenario = document.getElementById("intel-scenario-select")?.value || "SBI_DEGRADED";
      const seed = parseInt(document.getElementById("intel-seed-input")?.value || "42", 10);
      const data = await API.post("/api/network/simulate", { scenario, seed, target_rail: "UPI_SBI" });
      this.renderNetworkHealth(data.rails, data.timeline, data.scenario);
    } catch (err) {
      console.error("Error loading network health:", err);
    }
  },

  renderNetworkHealth: function (rails, timeline, scenario) {
    const container = document.getElementById("intel-rail-cards");
    if (!container) return;

    let html = "";
    for (const [railId, r] of Object.entries(rails)) {
      const statusColor = r.health_score >= 80 ? "var(--success)" : (r.health_score >= 40 ? "var(--warning)" : "var(--danger)");
      const statusBadge = r.health_score >= 80 ? "badge-success" : (r.health_score >= 40 ? "badge-warning" : "badge-danger");
      html += `
        <div class="card" style="padding: 12px; background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); border-radius: 8px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
            <div>
              <div style="font-weight: 700; font-size: 0.85rem; color: var(--text-primary);">${r.rail_name}</div>
              <div style="font-size: 0.72rem; color: var(--text-muted); font-family: monospace;">${r.rail_id}</div>
            </div>
            <span class="badge ${statusBadge}">${r.status}</span>
          </div>
          <div style="display: flex; align-items: baseline; gap: 6px; margin-bottom: 4px;">
            <span style="font-size: 1.4rem; font-weight: 800; color: ${statusColor};">${r.health_score.toFixed(1)}</span>
            <span style="font-size: 0.75rem; color: var(--text-muted);">/ 100</span>
          </div>
          <div class="readiness-progress-bar-bg" style="height: 6px; margin-bottom: 8px;">
            <div class="readiness-progress-bar-fill" style="width: ${r.health_score}%; background: ${statusColor};"></div>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted);">
            <span>Latency: <b>${r.latency_ms.toFixed(0)} ms</b></span>
            <span>Timeout: <b>${(r.timeout_rate * 100).toFixed(1)}%</b></span>
          </div>
        </div>
      `;
    }
    container.innerHTML = html;

    // Render 7-step temporal degradation timeline
    const timelineContainer = document.getElementById("intel-timeline-steps");
    if (timelineContainer && timeline) {
      let tHtml = "";
      timeline.forEach((step, idx) => {
        const stepColor = step.health_score >= 80 ? "var(--success)" : (step.health_score >= 40 ? "var(--warning)" : "var(--danger)");
        tHtml += `
          <div style="flex: 1; text-align: center; padding: 6px; border-radius: 6px; background: rgba(255,255,255,0.02); border: 1px solid var(--border-color);">
            <div style="font-size: 0.7rem; color: var(--text-muted);">${step.time_label}</div>
            <div style="font-weight: 800; font-size: 0.95rem; color: ${stepColor}; margin: 2px 0;">${step.health_score}</div>
            <div style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase;">${step.status}</div>
          </div>
        `;
      });
      timelineContainer.innerHTML = tHtml;
    }
  },

  loadReliabilityMetrics: async function () {
    try {
      const data = await API.get("/api/prediction/reliability");
      this.renderReliabilityMetrics(data);
    } catch (err) {
      console.error("Error loading reliability metrics:", err);
    }
  },

  renderReliabilityMetrics: function (m) {
    const fmt = (val, isPct = true) => {
      if (val === undefined || val === null || val === "N/A") return "N/A";
      if (typeof val === "number") return isPct ? `${(val * 100).toFixed(1)}%` : val.toFixed(3);
      return val;
    };

    document.getElementById("rel-precision").textContent = fmt(m.precision);
    document.getElementById("rel-recall").textContent = fmt(m.recall);
    document.getElementById("rel-f1").textContent = fmt(m.f1_score);
    document.getElementById("rel-brier").textContent = fmt(m.brier_score, false);
    document.getElementById("rel-fpr").textContent = fmt(m.false_positive_rate);
    document.getElementById("rel-accuracy").textContent = fmt(m.accuracy);
    document.getElementById("rel-total-count").textContent = m.total_predictions.toLocaleString();

    // Render 5-Bin Reliability Breakdown
    const tbody = document.getElementById("tbody-reliability-buckets");
    if (tbody && m.reliability_buckets) {
      tbody.innerHTML = m.reliability_buckets.map((b) => `
        <tr>
          <td><b>${b.range_label}</b></td>
          <td style="text-align: center;">${b.sample_count}</td>
          <td style="text-align: right;">${typeof b.predicted_average === "number" ? (b.predicted_average * 100).toFixed(1) + "%" : "N/A"}</td>
          <td style="text-align: right;">${typeof b.actual_failure_rate === "number" ? (b.actual_failure_rate * 100).toFixed(1) + "%" : "N/A"}</td>
          <td style="text-align: right; color: ${typeof b.prediction_error === "number" && Math.abs(b.prediction_error) <= 0.05 ? "var(--success)" : "var(--warning)"}; font-weight: 700;">
            ${typeof b.prediction_error === "number" ? (b.prediction_error >= 0 ? "+" : "") + (b.prediction_error * 100).toFixed(1) + "%" : "N/A"}
          </td>
        </tr>
      `).join("");
    }
  },

  loadPreventionEconomics: async function () {
    try {
      const data = await API.get("/api/prevention/economics");
      document.getElementById("econ-total-attempts").textContent = data.total_payment_attempts.toLocaleString();
      document.getElementById("econ-high-risk").textContent = data.high_risk_predictions.toLocaleString();
      document.getElementById("econ-interventions-approved").textContent = data.preventive_actions_approved.toLocaleString();
      document.getElementById("econ-failures-prevented").textContent = data.failures_prevented.toLocaleString();
      document.getElementById("econ-unnecessary").textContent = data.unnecessary_interventions.toLocaleString();
      document.getElementById("econ-prevented-gmv").textContent = formatINR(data.estimated_prevented_gmv);
      document.getElementById("econ-intervention-cost").textContent = formatINR(data.preventive_intervention_cost);
      document.getElementById("econ-net-value").textContent = formatINR(data.net_preventive_economic_value);
    } catch (err) {
      console.error("Error loading prevention economics:", err);
    }
  },

  loadPredictionHistory: async function () {
    try {
      const items = await API.get("/api/prediction/history?limit=8");
      const tbody = document.getElementById("tbody-prediction-history");
      if (!tbody) return;

      if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No prediction outcome pairs recorded yet.</td></tr>`;
        return;
      }

      tbody.innerHTML = items.map((item) => {
        let badgeClass = "badge-info";
        if (item.classification_result === "TRUE_POSITIVE") badgeClass = "badge-success";
        else if (item.classification_result === "TRUE_NEGATIVE") badgeClass = "badge-secondary";
        else if (item.classification_result === "FALSE_POSITIVE") badgeClass = "badge-warning";
        else if (item.classification_result === "FALSE_NEGATIVE") badgeClass = "badge-danger";

        return `
          <tr>
            <td style="font-family: monospace; font-size: 0.75rem;">${item.payment_id}</td>
            <td><b>${(item.predicted_probability * 100).toFixed(1)}%</b></td>
            <td><span class="badge ${item.actual_outcome === 'SUCCESS' ? 'badge-success' : 'badge-danger'}">${item.actual_outcome}</span></td>
            <td style="font-family: monospace;">${item.probability_error >= 0 ? '+' : ''}${item.probability_error.toFixed(2)}</td>
            <td><span class="badge ${badgeClass}">${item.classification_result}</span></td>
          </tr>
        `;
      }).join("");
    } catch (err) {
      console.error("Error loading prediction history:", err);
    }
  },

  runLifecycleSimulation: async function () {
    const btn = document.getElementById("btn-intel-run-sim");
    const originalText = btn.innerHTML;
    btn.innerHTML = `<span>⏳ Simulating 13 Stages...</span>`;
    btn.disabled = true;

    try {
      const amount = parseFloat(document.getElementById("intel-amount-input")?.value || "49999");
      const method = document.getElementById("intel-method-select")?.value || "UPI";
      const scenario = document.getElementById("intel-scenario-select")?.value || "SBI_DEGRADED";
      const seed = parseInt(document.getElementById("intel-seed-input")?.value || "42", 10);
      const chaos = document.getElementById("intel-chaos-select")?.value || null;

      const payload = {
        amount,
        payment_method: method,
        rail_id: method === "UPI" ? "UPI_SBI" : (method === "CARD" ? "CARD_VISA" : "NETBANKING_SBI"),
        network_scenario: scenario,
        network_seed: seed,
        chaos_injection: chaos === "NONE" ? null : chaos,
      };

      const trace = await API.post("/api/lifecycle/simulate", payload);
      this.activeTrace = trace;
      this.renderLifecycleStepper(trace);
      this.renderPredictionRadar(trace);
      this.renderGovernorExplainability(trace);

      showToast("Unified Payment Lifecycle Simulation Complete", "success");

      // Reload updated live metrics
      await this.loadReliabilityMetrics();
      await this.loadPreventionEconomics();
      await this.loadPredictionHistory();
    } catch (err) {
      console.error("Simulation error:", err);
      showToast(err.message, "error");
    } finally {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  },

  renderPredictionRadar: function (trace) {
    const pred = trace.prediction;
    if (!pred) return;

    const probPct = (pred.simulated_failure_probability * 100).toFixed(1);
    document.getElementById("radar-prob-val").textContent = `${probPct}%`;
    document.getElementById("radar-prob-bar").style.width = `${probPct}%`;
    document.getElementById("radar-prob-bar").style.background = pred.simulated_failure_probability >= 0.5 ? "var(--danger)" : "var(--success)";
    
    document.getElementById("radar-confidence").textContent = pred.confidence;
    document.getElementById("radar-conf-score").textContent = `${(pred.confidence_score * 100).toFixed(0)}%`;
    document.getElementById("radar-source").textContent = pred.prediction_source;

    const factorContainer = document.getElementById("radar-factors-list");
    if (factorContainer && pred.contributing_factors) {
      factorContainer.innerHTML = pred.contributing_factors.map(f => `
        <li style="margin-bottom: 4px; color: var(--text-primary); font-size: 0.8rem;">• ${f}</li>
      `).join("");
    }
  },

  renderGovernorExplainability: function (trace) {
    const prevDec = trace.prevention_decision;
    if (!prevDec) return;

    document.getElementById("prev-decision-outcome").textContent = prevDec.decision_outcome;
    document.getElementById("prev-decision-outcome").className = `badge ${prevDec.decision_outcome === 'APPROVED' ? 'badge-success' : 'badge-warning'}`;
    document.getElementById("prev-selected-action").textContent = prevDec.selected_action;
    document.getElementById("prev-net-erv").textContent = formatINR(prevDec.net_preventive_erv);

    const exp = prevDec.explainability || {};
    document.getElementById("exp-why-act").textContent = exp.why_act || "N/A";
    document.getElementById("exp-why-this").textContent = exp.why_this_action || "N/A";
    document.getElementById("exp-why-not").textContent = exp.why_not_alternatives || "N/A";
    document.getElementById("exp-gates").textContent = exp.safety_gates_summary || "N/A";
  },

  renderLifecycleStepper: function (trace) {
    const container = document.getElementById("lifecycle-stepper-stages");
    if (!container || !trace.history) return;

    const stages = trace.history;
    container.innerHTML = stages.map((s, idx) => {
      let badgeClass = "badge-secondary";
      if (s.state.includes("APPROVED") || s.state.includes("SUCCEEDED") || s.state.includes("COMPLETED")) badgeClass = "badge-success";
      else if (s.state.includes("FAILED") || s.state.includes("REJECTED")) badgeClass = "badge-danger";
      else if (s.state.includes("PREDICTED") || s.state.includes("EVALUATION")) badgeClass = "badge-warning";

      const detailsStr = JSON.stringify(s.details || {}, null, 1).replace(/[{}]/g, "").trim();

      return `
        <div style="display: flex; gap: 14px; margin-bottom: 12px; position: relative;">
          <div style="display: flex; flex-direction: column; align-items: center;">
            <div style="width: 24px; height: 24px; border-radius: 50%; background: var(--bg-card); border: 2px solid var(--accent); display: flex; align-items: center; justify-content: center; font-size: 0.7rem; font-weight: 800; color: var(--accent);">
              ${idx + 1}
            </div>
            ${idx < stages.length - 1 ? `<div style="width: 2px; flex: 1; background: var(--border-color); margin: 4px 0;"></div>` : ''}
          </div>
          <div style="flex: 1; padding: 8px 12px; border-radius: 6px; background: rgba(255,255,255,0.02); border: 1px solid var(--border-color);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <span style="font-weight: 700; font-size: 0.85rem; color: var(--text-primary); font-family: monospace;">${s.state}</span>
              <span class="badge ${badgeClass}">${s.state.split('_').slice(-1)[0]}</span>
            </div>
            ${detailsStr ? `<div style="font-size: 0.72rem; color: var(--text-muted); font-family: monospace; white-space: pre-wrap;">${detailsStr}</div>` : ''}
          </div>
        </div>
      `;
    }).join("");
  },
};

window.IntelligenceView = IntelligenceView;
