/**
 * Recovery Queue & Payment Explorer
 */

window.PaymentsView = {
  currentPage: 0,
  pageSize: 50,
  totalItems: 0,

  load: async () => {
    const statusFilter = document.getElementById("queue-filter-status").value;
    const failureFilter = document.getElementById("queue-filter-failure").value;
    const offset = window.PaymentsView.currentPage * window.PaymentsView.pageSize;

    let url = `/api/payments?limit=${window.PaymentsView.pageSize}&offset=${offset}`;
    if (statusFilter) url += `&status=${statusFilter}`;
    if (failureFilter) url += `&failure_type=${failureFilter}`;

    try {
      const data = await API.get(url);
      window.PaymentsView.totalItems = data.total;
      window.PaymentsView.renderTable(data.items);
      window.PaymentsView.updatePagination();
    } catch (err) {
      console.error("Queue load error:", err);
      showToast("Error loading recovery queue", "error");
    }
  },

  renderTable: (payments) => {
    const tbody = document.getElementById("tbody-queue");
    if (!tbody) return;

    if (!payments || payments.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-muted);">No failed payments match filter criteria.</td></tr>`;
      return;
    }

    tbody.innerHTML = payments
      .map((p) => {
        const isRecovered = p.status === "RECOVERED";
        const statusBadge = isRecovered
          ? `<span class="badge badge-success">Recovered</span>`
          : `<span class="badge badge-danger">Failed</span>`;

        const isHard = ["CARD_LOST_STOLEN", "MANDATE_REVOKED", "ACCOUNT_CLOSED", "PERMANENT_DECLINE"].includes(p.failure_type);
        const failureChip = isHard
          ? `<span class="badge badge-danger" title="Hard Decline">${p.failure_type}</span>`
          : `<span class="badge badge-neutral">${p.failure_type}</span>`;

        return `
          <tr data-payment-id="${p.payment_id}">
            <td><code style="color: #60a5fa; font-weight: 600;">${p.payment_id}</code></td>
            <td><b>${formatINR(p.amount)}</b></td>
            <td><span class="badge badge-neutral">${p.payment_method}</span></td>
            <td>${failureChip}</td>
            <td>${p.retry_count}</td>
            <td><span class="badge badge-${p.risk_tier === 'HIGH' ? 'danger' : (p.risk_tier === 'MEDIUM' ? 'warning' : 'neutral')}">${p.risk_tier}</span></td>
            <td>${statusBadge}</td>
            <td>
              <button class="btn btn-secondary btn-sm btn-inspect-payment" data-id="${p.payment_id}" style="padding: 3px 8px; font-size: 0.75rem;">
                Trace & Replay
              </button>
            </td>
          </tr>
        `;
      })
      .join("");

    // Attach click handlers
    document.querySelectorAll(".btn-inspect-payment").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const payId = btn.getAttribute("data-id");
        window.location.hash = "replay";
        setTimeout(() => {
          const input = document.getElementById("replay-input-payment-id");
          if (input) input.value = payId;
          if (window.DecisionReplayView) window.DecisionReplayView.replayPayment(payId);
        }, 100);
      });
    });

    document.querySelectorAll("#tbody-queue tr").forEach((tr) => {
      tr.addEventListener("click", () => {
        const payId = tr.getAttribute("data-payment-id");
        if (payId) {
          window.location.hash = "replay";
          setTimeout(() => {
            const input = document.getElementById("replay-input-payment-id");
            if (input) input.value = payId;
            if (window.DecisionReplayView) window.DecisionReplayView.replayPayment(payId);
          }, 100);
        }
      });
    });
  },

  updatePagination: () => {
    const start = window.PaymentsView.currentPage * window.PaymentsView.pageSize + 1;
    const end = Math.min(start + window.PaymentsView.pageSize - 1, window.PaymentsView.totalItems);
    const info = document.getElementById("queue-pagination-info");
    if (info) {
      info.textContent = `Showing ${start.toLocaleString()}-${end.toLocaleString()} of ${window.PaymentsView.totalItems.toLocaleString()}`;
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  const prevBtn = document.getElementById("btn-queue-prev");
  const nextBtn = document.getElementById("btn-queue-next");
  const filterStatus = document.getElementById("queue-filter-status");
  const filterFailure = document.getElementById("queue-filter-failure");
  const searchInput = document.getElementById("queue-search");

  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (window.PaymentsView.currentPage > 0) {
        window.PaymentsView.currentPage--;
        window.PaymentsView.load();
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      if ((window.PaymentsView.currentPage + 1) * window.PaymentsView.pageSize < window.PaymentsView.totalItems) {
        window.PaymentsView.currentPage++;
        window.PaymentsView.load();
      }
    });
  }

  if (filterStatus) filterStatus.addEventListener("change", () => { window.PaymentsView.currentPage = 0; window.PaymentsView.load(); });
  if (filterFailure) filterFailure.addEventListener("change", () => { window.PaymentsView.currentPage = 0; window.PaymentsView.load(); });
});
