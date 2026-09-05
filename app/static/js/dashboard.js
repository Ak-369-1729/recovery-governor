/**
 * Overview & Financial Dashboard Component
 */

window.DashboardView = {
  load: async () => {
    try {
      const [metrics, charts] = await Promise.all([
        API.get("/api/dashboard/metrics"),
        API.get("/api/dashboard/charts"),
      ]);

      // Metrics Grid
      document.getElementById("metric-revenue-at-risk").textContent = formatINR(metrics.revenue_at_risk);
      document.getElementById("metric-incrementally-recovered").textContent = formatINR(metrics.incrementally_recovered);
      document.getElementById("metric-recovery-rate").textContent = `${(metrics.recovery_rate * 100).toFixed(1)}%`;
      document.getElementById("metric-net-recovery-value").textContent = formatINR(metrics.net_recovery_value);
      document.getElementById("metric-unsafe-blocked").textContent = metrics.unsafe_actions_blocked;
      document.getElementById("metric-avg-time").textContent = `${metrics.average_time_to_recovery_minutes.toFixed(1)}m`;
      document.getElementById("metric-lift-badge").textContent = `↑ ${metrics.recovery_lift_vs_baseline.toFixed(1)}% Lift`;

      // Failure Taxonomy Matrix Table
      const tbodyFailures = document.getElementById("tbody-failure-breakdown");
      if (tbodyFailures && charts.failure_breakdown) {
        tbodyFailures.innerHTML = charts.failure_breakdown
          .map((f) => {
            const isHard = ["CARD_LOST_STOLEN", "MANDATE_REVOKED", "ACCOUNT_CLOSED", "PERMANENT_DECLINE"].includes(f.failure_type);
            const gateTag = isHard
              ? `<span class="badge badge-danger">Gate 1: Hard Decline Ban</span>`
              : `<span class="badge badge-success">Gate 5: ERV Optimizer</span>`;

            return `
              <tr>
                <td><b>${f.failure_type}</b></td>
                <td>${f.count.toLocaleString()}</td>
                <td>${formatINR(f.volume)}</td>
                <td>${f.recovered_count.toLocaleString()}</td>
                <td><span class="${f.recovery_rate > 0.5 ? 'text-success' : 'text-warning'} font-mono">${(f.recovery_rate * 100).toFixed(1)}%</span></td>
                <td>${gateTag}</td>
              </tr>
            `;
          })
          .join("");
      }

      // Bayesian Learned Models Table
      const tbodyBayes = document.getElementById("tbody-bayesian-models");
      if (tbodyBayes && charts.bayesian_models) {
        tbodyBayes.innerHTML = charts.bayesian_models
          .map((b) => {
            return `
              <tr>
                <td><code style="color: #60a5fa;">${b.failure_type}</code> <span class="text-muted">➔</span> <b>${b.action}</b></td>
                <td>Beta(${b.alpha_prior}, ${b.beta_prior})</td>
                <td><span class="text-success">${b.successes} S</span> / <span class="text-danger">${b.failures} F</span></td>
                <td><b class="text-blue font-mono">${(b.posterior_mean * 100).toFixed(1)}%</b></td>
                <td>± ${(b.std_dev * 100).toFixed(2)}%</td>
                <td><span class="badge badge-purple">${b.samples} updates</span></td>
              </tr>
            `;
          })
          .join("");
      }
    } catch (err) {
      console.error("Dashboard render error:", err);
      showToast("Error loading dashboard metrics", "error");
    }
  },
};
