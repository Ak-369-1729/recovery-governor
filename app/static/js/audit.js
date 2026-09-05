/**
 * Audit Trail & Cryptographic Verifier Component
 */

window.AuditView = {
  load: async () => {
    try {
      const data = await API.get("/api/audit?limit=50");
      window.AuditView.render(data.items);
    } catch (err) {
      console.error("Audit load error:", err);
      showToast("Error loading audit records", "error");
    }
  },

  render: (logs) => {
    const tbody = document.getElementById("tbody-audit");
    if (!tbody) return;

    if (!logs || logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No audit records generated yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = logs.map(l => {
      const shortHash = l.hash ? `${l.hash.substring(0, 10)}...${l.hash.substring(l.hash.length - 8)}` : '--';
      const shortPrev = l.prev_hash ? `${l.prev_hash.substring(0, 8)}...` : '--';

      return `
        <tr>
          <td><code style="color: #60a5fa;">${l.log_id}</code></td>
          <td style="font-size: 0.78rem; color: var(--text-muted);">${new Date(l.timestamp).toLocaleTimeString()}</td>
          <td><span class="badge badge-purple">${l.event_type}</span></td>
          <td><code style="color: #f8fafc;">${l.payment_id}</code></td>
          <td><code style="color: #10b981; font-size: 0.75rem;" title="${l.hash}">${shortHash}</code></td>
          <td><code style="color: #94a3b8; font-size: 0.75rem;" title="${l.prev_hash}">${shortPrev}</code></td>
        </tr>
      `;
    }).join("");
  },
};

// Live Demo View Controller
window.LiveDemoView = {
  init: () => {
    const btn = document.getElementById("btn-execute-live-demo");
    if (btn) {
      btn.onclick = async () => {
        btn.disabled = true;
        btn.textContent = "⏳ Executing Live Demonstration...";

        const container = document.getElementById("demo-scenarios-container");
        container.innerHTML = `<div class="card" style="text-align: center; padding: 40px; color: var(--text-muted);">Executing 3 canonical scenarios through real backend engine...</div>`;

        try {
          const res = await API.post("/api/demo/run");
          window.LiveDemoView.renderScenarios(res.scenarios);
          showToast("Live Demo executed successfully!");
        } catch (err) {
          container.innerHTML = `<div class="card text-danger" style="padding: 24px;">Demo error: ${err.message}</div>`;
        } finally {
          btn.disabled = false;
          btn.textContent = "▶ Run All 3 Scenarios";
        }
      };
    }
  },

  renderScenarios: (scenarios) => {
    const container = document.getElementById("demo-scenarios-container");
    if (!container || !scenarios) return;

    container.innerHTML = scenarios.map((s, idx) => {
      const rawOutcome = s.decision.decision_outcome || s.decision.decision;
      const outcome = (rawOutcome === 'EXECUTE') ? 'APPROVED' : (rawOutcome || 'APPROVED');
      const outcomeBadge = (outcome === 'APPROVED')
        ? `<span class="badge badge-success">APPROVED</span>`
        : (outcome === 'STOP' ? `<span class="badge badge-danger">STOP</span>` : `<span class="badge badge-warning">${outcome}</span>`);

      const actionDisplay = s.decision.selected_action || '—';
      const verifStatus = (s.verification && s.verification.status) ? s.verification.status : '—';
      const attrCategory = (s.attribution && s.attribution.category) ? s.attribution.category : '—';

      return `
        <div class="card" style="border-left: 4px solid var(--accent-blue);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
            <div>
              <div class="card-title" style="font-size: 1.05rem;">${s.title}</div>
              <div class="card-subtitle" style="margin-top: 4px; font-size: 0.85rem; color: var(--text-primary);">${s.narrative}</div>
            </div>
            <span class="badge badge-success">Scenario ${idx + 1}</span>
          </div>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-top: 14px; font-size: 0.82rem; background: #090d16; padding: 14px; border-radius: 6px;">
            <div>
              <span class="text-muted">Payment:</span><br>
              <b>${formatINR(s.payment.amount)}</b> via ${s.payment.payment_method}
            </div>
            <div>
              <span class="text-muted">Failure Etiology:</span><br>
              <code style="color: #f87171;">${s.payment.failure_type}</code>
            </div>
            <div>
              <span class="text-muted">Governor Decision:</span><br>
              <b class="text-blue">${actionDisplay}</b> (${outcomeBadge})
            </div>
            <div>
              <span class="text-muted">Settlement Outcome:</span><br>
              <b>${verifStatus}</b> (<span class="${attrCategory === 'ATTRIBUTED_RECOVERY' ? 'text-success' : 'text-muted'}">${attrCategory}</span>)
            </div>
          </div>
        </div>
      `;
    }).join("");
  }
};

document.addEventListener("DOMContentLoaded", () => {
  const verifyBtn = document.getElementById("btn-verify-audit");
  if (verifyBtn) {
    verifyBtn.addEventListener("click", async () => {
      verifyBtn.disabled = true;
      verifyBtn.textContent = "🛡️ Verifying SHA-256 Hashes...";
      try {
        const check = await API.get("/api/audit/verify");
        if (check.is_valid) {
          showToast(`Verified ${check.total_records} cryptographic blocks. Hash chain 100% intact!`, "info");
        } else {
          showToast(`Tampered block detected at: ${check.tampered_record_id}`, "error");
        }
      } catch (err) {
        showToast("Error verifying audit chain", "error");
      } finally {
        verifyBtn.disabled = false;
        verifyBtn.textContent = "🛡️ Verify Hash Chain Integrity";
      }
    });
  }
});
