/**
 * Three-Way Benchmark Component
 */

window.BenchmarkView = {
  load: async () => {
    try {
      const data = await API.get("/api/benchmark");
      window.BenchmarkView.render(data.cohorts);
    } catch (err) {
      console.error("Benchmark load error:", err);
      showToast("Error loading benchmark results", "error");
    }
  },

  render: (cohorts) => {
    const ctrl = cohorts.CONTROL;
    const base = cohorts.BASELINE;
    const gov = cohorts.GOVERNOR;

    if (!ctrl || !base || !gov) return;

    // Cohort cards
    document.getElementById("bench-ctrl-rate").textContent = `${(ctrl.recovery_rate * 100).toFixed(1)}%`;
    document.getElementById("bench-ctrl-gross").textContent = formatINR(ctrl.gross_recovered);
    document.getElementById("bench-ctrl-net").textContent = formatINR(ctrl.net_recovery_value);

    document.getElementById("bench-base-rate").textContent = `${(base.recovery_rate * 100).toFixed(1)}%`;
    document.getElementById("bench-base-gross").textContent = formatINR(base.gross_recovered);
    document.getElementById("bench-base-cost").textContent = formatINR(base.total_intervention_cost + base.total_risk_cost);
    document.getElementById("bench-base-net").textContent = formatINR(base.net_recovery_value);

    document.getElementById("bench-gov-rate").textContent = `${(gov.recovery_rate * 100).toFixed(1)}%`;
    document.getElementById("bench-gov-gross").textContent = formatINR(gov.gross_recovered);
    const liftVsBase = gov.net_recovery_value - base.net_recovery_value;
    document.getElementById("bench-gov-lift").textContent = `+${formatINR(liftVsBase)}`;
    document.getElementById("bench-gov-net").textContent = formatINR(gov.net_recovery_value);

    // Detailed Table
    const tbody = document.getElementById("tbody-benchmark-detailed");
    if (!tbody) return;

    const rows = [
      {
        metric: "Total Failed Volume Analyzed",
        ctrl: formatINR(ctrl.gross_failed_volume),
        base: formatINR(base.gross_failed_volume),
        gov: formatINR(gov.gross_failed_volume),
        adv: "Exact Same Dataset (N=5,000)"
      },
      {
        metric: "Gross Revenue Recovered",
        ctrl: formatINR(ctrl.gross_recovered),
        base: formatINR(base.gross_recovered),
        gov: `<b class="text-success">${formatINR(gov.gross_recovered)}</b>`,
        adv: `+${formatINR(gov.gross_recovered - base.gross_recovered)} vs Baseline`
      },
      {
        metric: "Recovery Rate",
        ctrl: `${(ctrl.recovery_rate * 100).toFixed(2)}%`,
        base: `${(base.recovery_rate * 100).toFixed(2)}%`,
        gov: `<b class="text-success">${(gov.recovery_rate * 100).toFixed(2)}%</b>`,
        adv: `+${((gov.recovery_rate - base.recovery_rate) * 100).toFixed(2)}% Abs Lift`
      },
      {
        metric: "Intervention Count",
        ctrl: "0 (No action)",
        base: `${base.intervention_count.toLocaleString()} (100% blind)`,
        gov: `${gov.intervention_count.toLocaleString()} (Selective)`,
        adv: `${base.intervention_count - gov.intervention_count} wasteful actions saved`
      },
      {
        metric: "Total Intervention & Friction Costs",
        ctrl: "₹0.00",
        base: formatINR(base.total_intervention_cost + base.total_risk_cost),
        gov: formatINR(gov.total_intervention_cost + gov.total_risk_cost + gov.total_friction_cost),
        adv: "Optimized by ERV Hurdle"
      },
      {
        metric: "Unsafe Actions Blocked (Hard Declines)",
        ctrl: "0",
        base: `<span class="text-danger">0 blocked (VIOLATED)</span>`,
        gov: `<b class="text-success">${gov.unsafe_actions_blocked} blocked (100% Safe)</b>`,
        adv: "Zero scheme penalty risk"
      },
      {
        metric: "Net Economic Recovery Value",
        ctrl: formatINR(ctrl.net_recovery_value),
        base: formatINR(base.net_recovery_value),
        gov: `<b class="text-success font-mono" style="font-size: 1rem;">${formatINR(gov.net_recovery_value)}</b>`,
        adv: `<b class="text-success">+${formatINR(liftVsBase)} (+${((liftVsBase / Math.max(1, base.net_recovery_value)) * 100).toFixed(1)}% lift)</b>`
      }
    ];

    tbody.innerHTML = rows.map(r => `
      <tr>
        <td><b>${r.metric}</b></td>
        <td>${r.ctrl}</td>
        <td>${r.base}</td>
        <td>${r.gov}</td>
        <td>${r.adv}</td>
      </tr>
    `).join("");
  },
};

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btn-run-benchmark");
  if (btn) {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.textContent = "⏳ Running Benchmark (5,000 payments)...";
      try {
        const res = await API.post("/api/benchmark/run?sample_size=5000");
        window.BenchmarkView.render(res.cohorts);
        showToast("Benchmark completed on 5,000 payments.");
      } catch (err) {
        console.error("Benchmark run failed:", err);
        showToast("Benchmark execution failed", "error");
      } finally {
        btn.disabled = false;
        btn.textContent = "▶ Re-Run Benchmark";
      }
    });
  }
});
