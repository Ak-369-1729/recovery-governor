/**
 * Experiments Component (A/B/n Multi-Arm Testing)
 */

window.ExperimentsView = {
  load: async () => {
    try {
      const data = await API.get("/api/experiments");
      window.ExperimentsView.render(data.latest_experiment);
    } catch (err) {
      console.error("Experiments load error:", err);
      showToast("Error loading experiments", "error");
    }
  },

  render: (exp) => {
    if (!exp || !exp.arms) return;

    const grid = document.getElementById("experiments-arms-grid");
    if (grid) {
      grid.innerHTML = Object.entries(exp.arms).map(([key, arm]) => {
        const isWinner = arm.arm_name === exp.winner;
        return `
          <div class="metric-card" style="border-top: 4px solid ${isWinner ? 'var(--color-success)' : 'var(--border-light)'};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
              <span class="metric-label">${arm.arm_name}</span>
              ${isWinner ? '<span class="badge badge-success">WINNER</span>' : ''}
            </div>
            <div class="metric-value ${isWinner ? 'text-success' : ''}">${formatINR(arm.net_revenue)}</div>
            <div class="metric-subtext">Net Revenue (${(arm.recovery_rate * 100).toFixed(1)}% rate)</div>
            <div style="margin-top: 12px; font-size: 0.78rem; color: var(--text-secondary); display: flex; flex-direction: column; gap: 4px;">
              <div>Interventions: ${arm.intervention_count.toLocaleString()}</div>
              <div>Total Costs: ${formatINR(arm.intervention_cost + arm.risk_cost + arm.customer_friction_cost)}</div>
              <div>Safety Violations: <span class="${arm.unsafe_actions_attempted > 0 ? 'text-danger' : 'text-success'}">${arm.unsafe_actions_attempted || 0}</span></div>
            </div>
          </div>
        `;
      }).join("");
    }

    const tbody = document.getElementById("tbody-experiments");
    if (tbody) {
      tbody.innerHTML = Object.values(exp.arms).map(arm => `
        <tr>
          <td><b>${arm.arm_name}</b></td>
          <td>${arm.sample_size.toLocaleString()}</td>
          <td>${formatINR(arm.recovered_volume)}</td>
          <td class="font-mono">${(arm.recovery_rate * 100).toFixed(2)}%</td>
          <td>${formatINR(arm.intervention_cost + arm.risk_cost + arm.customer_friction_cost)}</td>
          <td><b class="${arm.arm_name === exp.winner ? 'text-success' : ''}">${formatINR(arm.net_revenue)}</b></td>
          <td><span class="badge badge-${arm.unsafe_actions_attempted > 0 ? 'danger' : 'success'}">${arm.unsafe_actions_attempted || 0}</span></td>
        </tr>
      `).join("");
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btn-run-experiment");
  if (btn) {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.textContent = "⏳ Running Experiment...";
      try {
        const res = await API.post("/api/experiments/run?sample_per_arm=500");
        window.ExperimentsView.render(res.results);
        showToast("Experiment completed across 4 strategies.");
      } catch (err) {
        console.error("Experiment failed:", err);
        showToast("Experiment run failed", "error");
      } finally {
        btn.disabled = false;
        btn.textContent = "▶ Run 4-Arm Experiment";
      }
    });
  }
});
