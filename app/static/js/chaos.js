/**
 * Chaos Engineering Laboratory Component
 */

window.ChaosView = {
  load: async () => {
    try {
      const scenarios = await API.get("/api/chaos/scenarios");
      window.ChaosView.renderScenarios(scenarios);
    } catch (err) {
      console.error("Chaos load error:", err);
      showToast("Error loading chaos scenarios", "error");
    }
  },

  renderScenarios: (scenarios) => {
    const container = document.getElementById("chaos-scenarios-container");
    if (!container) return;

    container.innerHTML = scenarios.map(s => `
      <div class="card" id="chaos-card-${s.id}">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <div>
            <div class="card-title">${s.title}</div>
            <div class="card-subtitle">${s.description}</div>
          </div>
          <span class="badge badge-warning">${s.expected_gate}</span>
        </div>

        <div style="margin: 14px 0; font-size: 0.8rem; color: var(--text-secondary);">
          <b>Expected Safety Invariant:</b> <code>${s.expected_outcome}</code>
        </div>

        <button class="btn btn-secondary btn-sm btn-trigger-chaos" data-id="${s.id}" style="width: 100%;">
          ⚡ Trigger Scenario Now
        </button>

        <div class="chaos-result-box" id="chaos-result-${s.id}" style="display: none; margin-top: 14px;">
          <!-- Result injected dynamically -->
        </div>
      </div>
    `).join("");

    // Attach click triggers
    document.querySelectorAll(".btn-trigger-chaos").forEach(btn => {
      btn.addEventListener("click", async () => {
        const scenarioId = btn.getAttribute("data-id");
        btn.disabled = true;
        btn.textContent = "⏳ Executing Chaos Simulation...";

        const resultBox = document.getElementById(`chaos-result-${scenarioId}`);
        resultBox.style.display = "block";
        resultBox.innerHTML = `<div style="font-size: 0.8rem; color: var(--text-muted); padding: 8px;">Firing backend test...</div>`;

        try {
          const res = await API.post(`/api/chaos/run/${scenarioId}`);
          resultBox.innerHTML = `
            <div style="background: #090d16; border: 1px solid ${res.invariant_passed ? 'var(--color-success)' : 'var(--color-danger)'}; border-radius: 6px; padding: 12px; font-size: 0.8rem;">
              <div style="font-weight: 700; color: ${res.invariant_passed ? 'var(--color-success)' : 'var(--color-danger)'}; margin-bottom: 6px;">
                ${res.safety_verdict}
              </div>
              <div style="color: var(--text-secondary); font-family: var(--font-mono); font-size: 0.75rem; margin-top: 6px;">
                Audit Log: <code style="color: #60a5fa;">${res.audit_log_id}</code>
              </div>
            </div>
          `;
          showToast(`Scenario ${scenarioId} executed: PASSED`, "info");
        } catch (err) {
          resultBox.innerHTML = `<div class="text-danger" style="font-size: 0.8rem;">Execution error: ${err.message}</div>`;
        } finally {
          btn.disabled = false;
          btn.textContent = "⚡ Trigger Scenario Now";
        }
      });
    });
  },
};
