/**
 * Decision Replay & Chronological Trace Component
 */

window.DecisionReplayView = {
  replayPayment: async (paymentId) => {
    const container = document.getElementById("replay-container");
    if (!container) return;

    container.innerHTML = `
      <div class="card" style="text-align: center; padding: 40px;">
        <div style="font-size: 1.2rem; margin-bottom: 8px;">⏳ Reconstructing Decision Pipeline...</div>
        <div style="color: var(--text-muted); font-size: 0.85rem;">Retrieving contextual event, AI diagnosis, ERV mathematics, and deterministic safety gates for ${paymentId}</div>
      </div>
    `;

    try {
      const data = await API.get(`/api/decisions/${paymentId}/replay`);
      window.DecisionReplayView.renderPipeline(data);
    } catch (err) {
      console.error("Replay error:", err);
      container.innerHTML = `
        <div class="card" style="border-color: var(--color-danger); padding: 32px; text-align: center;">
          <div style="color: var(--color-danger); font-weight: 600; margin-bottom: 8px;">Failed to Load Decision Replay</div>
          <div style="color: var(--text-secondary); font-size: 0.85rem;">${err.message}</div>
        </div>
      `;
    }
  },

  renderPipeline: (data) => {
    const container = document.getElementById("replay-container");
    if (!container) return;

    const { payment, decision, execution, verification, attribution, trace_steps } = data;

    // Header Summary Card
    const isHard = ["CARD_LOST_STOLEN", "MANDATE_REVOKED", "ACCOUNT_CLOSED", "PERMANENT_DECLINE"].includes(payment.failure_type);
    
    const outcome = decision.decision_outcome || decision.decision || 'APPROVED';
    const outcomeBadgeClass = (outcome === 'APPROVED' || outcome === 'EXECUTE') ? 'success' : (outcome === 'STOP' ? 'danger' : 'warning');
    const displayOutcome = (outcome === 'EXECUTE') ? 'APPROVED' : outcome;

    let html = `
      <div class="card" style="margin-bottom: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
          <div>
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
              <span style="font-size: 1.2rem; font-weight: 700; color: #fff;">${payment.payment_id || '—'}</span>
              <span class="badge badge-${outcomeBadgeClass}">
                Decision: ${displayOutcome}
              </span>
              <span class="badge badge-${decision.ai_mode === 'GEMINI' ? 'purple' : 'neutral'}">
                AI Mode: ${decision.ai_mode || 'DETERMINISTIC_FALLBACK'}
              </span>
            </div>
            <div style="font-size: 0.85rem; color: var(--text-secondary);">
              <b>${formatINR(payment.amount)}</b> via ${payment.payment_method} • Failure: <code style="color: #f87171;">${payment.failure_type}</code> • Risk: ${payment.risk_tier}
            </div>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 0.75rem; color: var(--text-muted);">Selected Action:</div>
            <div style="font-size: 1.1rem; font-weight: 700; color: #60a5fa;">${decision.selected_action}</div>
          </div>
        </div>
      </div>
    `;

    // Timeline steps
    html += `<div class="pipeline-timeline">`;

    trace_steps.forEach((step) => {
      let extraHtml = "";

      // Step 3: AI Diagnosis
      if (step.stage === "AI_DIAGNOSIS") {
        extraHtml = `
          <div style="margin-top: 10px;">
            <div style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 4px;">Candidate Actions Proposed by AI:</div>
            <div style="display: flex; flex-direction: column; gap: 6px;">
              ${(step.data.candidate_proposals || []).map(p => `
                <div style="background: rgba(17, 23, 38, 0.8); border: 1px solid var(--border-color); border-radius: 4px; padding: 8px 12px; font-size: 0.8rem;">
                  <b class="text-blue">${p.action || p}</b>: <span style="color: var(--text-secondary);">${p.reason || 'Proposed based on contextual failure patterns.'}</span>
                </div>
              `).join("")}
            </div>
          </div>
        `;
      }

      // Step 4: ERV Calculation Breakdown Table
      if (step.stage === "ERV_CALCULATION") {
        extraHtml = `
          <div class="table-container" style="margin-top: 12px;">
            <table>
              <thead>
                <tr>
                  <th>Candidate Action</th>
                  <th>Recovery Prob</th>
                  <th>Gross Recovery</th>
                  <th>Intervention Cost</th>
                  <th>Risk Cost</th>
                  <th>Friction Cost</th>
                  <th>Net ERV</th>
                  <th>Viable</th>
                </tr>
              </thead>
              <tbody>
                ${Object.values(step.data).map(erv => `
                  <tr>
                    <td><b>${erv.action}</b></td>
                    <td class="font-mono">${(erv.recovery_probability * 100).toFixed(1)}%</td>
                    <td>${formatINR(erv.gross_expected_recovery)}</td>
                    <td class="text-danger">-${formatINR(erv.intervention_cost)}</td>
                    <td class="text-danger">-${formatINR(erv.risk_cost)}</td>
                    <td class="text-danger">-${formatINR(erv.friction_cost)}</td>
                    <td class="font-mono ${erv.net_erv > 0 ? 'text-success' : 'text-danger'}"><b>${formatINR(erv.net_erv)}</b></td>
                    <td><span class="badge badge-${erv.is_economically_viable ? 'success' : 'danger'}">${erv.is_economically_viable ? 'YES' : 'NO'}</span></td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        `;
      }

      // Step 5: Governor Policy 8 Gates
      if (step.stage === "GOVERNOR_POLICY") {
        extraHtml = `
          <div style="margin-top: 12px; display: flex; flex-direction: column; gap: 8px;">
            ${(step.data.policy_checks || []).map(gate => `
              <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(17, 23, 38, 0.7); border: 1px solid var(--border-color); border-radius: 4px; padding: 8px 12px; font-size: 0.8rem;">
                <div>
                  <b>${gate.gate_name}</b>: <span style="color: var(--text-secondary);">${gate.reason}</span>
                </div>
                <span class="badge badge-${gate.status === 'PASSED' ? 'success' : (gate.status === 'BLOCKED' ? 'danger' : 'warning')}">
                  ${gate.status}
                </span>
              </div>
            `).join("")}
          </div>
        `;
      }

      // Step 6 & 7: Execution & Verification Raw payloads
      if (step.stage === "EXECUTION" || step.stage === "VERIFICATION" || step.stage === "ATTRIBUTION") {
        extraHtml = `
          <div class="step-code-box" style="margin-top: 8px;">
            ${JSON.stringify(step.data, null, 2)}
          </div>
        `;
      }

      html += `
        <div class="timeline-step">
          <div class="step-header">
            <div class="step-title">Stage ${step.step_number}: ${step.title}</div>
            <span style="font-size: 0.75rem; color: var(--text-muted);">${step.timestamp ? new Date(step.timestamp).toLocaleTimeString() : ''}</span>
          </div>
          <div class="step-summary">${step.summary}</div>
          ${extraHtml}
        </div>
      `;
    });

    html += `</div>`;
    container.innerHTML = html;
  },
};

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btn-replay-lookup");
  const input = document.getElementById("replay-input-payment-id");

  if (btn && input) {
    btn.addEventListener("click", () => {
      const pid = input.value.trim();
      if (pid) {
        window.DecisionReplayView.replayPayment(pid);
      } else {
        showToast("Please enter a Payment ID", "error");
      }
    });

    input.addEventListener("keypress", (e) => {
      if (e.key === "Enter") btn.click();
    });
  }
});
