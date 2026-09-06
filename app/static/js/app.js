/**
 * Recovery Governor - Main SPA Router & Core State
 * Zero Node/NPM Dependencies - Pure Vanilla ES6
 */

const API = {
  get: async (url) => {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status} from ${url}`);
    return res.json();
  },
  post: async (url, body = {}) => {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} from ${url}`);
    return res.json();
  },
};

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${type === "error" ? "❌" : "ℹ️"}</span> <span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    toast.style.transition = "all 0.2s ease";
    setTimeout(() => toast.remove(), 200);
  }, 4000);
}

function formatINR(val) {
  if (val === undefined || val === null) return "₹0.00";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(val);
}

// Router & View Switcher
function switchView(viewName) {
  const sections = document.querySelectorAll(".view-section");
  sections.forEach((sec) => (sec.style.display = "none"));

  const targetSec = document.getElementById(`view-${viewName}`);
  if (targetSec) {
    targetSec.style.display = "block";
  }

  // Update nav item active states
  const navItems = document.querySelectorAll(".nav-item");
  navItems.forEach((item) => {
    if (item.getAttribute("data-view") === viewName) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });

  // Update Top Bar titles
  const titles = {
    overview: ["Overview", "Real-Time Financial Recovery Analytics"],
    intelligence: ["Payment Intelligence", "Predict → Prevent → Recover → Prove Architecture"],
    sandbox: ["Recovery Sandbox", "Interactive What-If Simulation, Strategy Arena & Governed Execution"],
    queue: ["Recovery Queue", "Live Stream of Failed Payments & Policy Actions"],
    replay: ["Decision Replay", "Step-by-Step Chronological Audit & Causal Trace"],
    benchmark: ["Three-Way Benchmark", "Control vs Naive Baseline vs Recovery Governor"],
    experiments: ["Experiments", "Multi-Arm A/B/n Recovery Strategy Optimization"],
    chaos: ["Chaos Lab", "Resilience & Adversarial Financial Safety Tests"],
    audit: ["Audit Trail", "Cryptographically Chained SHA-256 Event Logs"],
    demo: ["Live Demo", "2-Minute Interactive Showcase of Core Value"],
    settings: ["Settings", "Policy Thresholds & Hardware Boundaries"],
  };

  const [title, sub] = titles[viewName] || ["Overview", "Revenue Recovery Engine"];
  document.getElementById("current-page-title").textContent = title;
  document.getElementById("current-page-subtitle").textContent = sub;

  // Trigger view-specific data loads
  if (viewName === "overview" && window.DashboardView) window.DashboardView.load();
  if (viewName === "intelligence" && window.IntelligenceView) window.IntelligenceView.init();
  if (viewName === "sandbox" && window.SandboxView) window.SandboxView.init();
  if (viewName === "queue" && window.PaymentsView) window.PaymentsView.load();
  if (viewName === "benchmark" && window.BenchmarkView) window.BenchmarkView.load();
  if (viewName === "experiments" && window.ExperimentsView) window.ExperimentsView.load();
  if (viewName === "chaos" && window.ChaosView) window.ChaosView.load();
  if (viewName === "audit" && window.AuditView) window.AuditView.load();
  if (viewName === "demo" && window.LiveDemoView) window.LiveDemoView.init();
}

// Global Modal handlers
function openDecisionTraceModal(title, htmlContent) {
  document.getElementById("modal-trace-title").textContent = title;
  document.getElementById("modal-trace-body").innerHTML = htmlContent;
  document.getElementById("modal-trace").classList.add("active");
}

function closeDecisionTraceModal() {
  document.getElementById("modal-trace").classList.remove("active");
}

document.addEventListener("DOMContentLoaded", () => {
  // Hash routing
  const handleRoute = () => {
    const hash = window.location.hash.replace("#", "") || "overview";
    switchView(hash);
  };

  window.addEventListener("hashchange", handleRoute);
  handleRoute();

  // Refresh button
  document.getElementById("btn-refresh-data").addEventListener("click", () => {
    const hash = window.location.hash.replace("#", "") || "overview";
    switchView(hash);
    showToast("Dashboard data refreshed.");
  });

  // Modal close
  document.getElementById("modal-trace-close").addEventListener("click", closeDecisionTraceModal);
  document.getElementById("modal-trace").addEventListener("click", (e) => {
    if (e.target.id === "modal-trace") closeDecisionTraceModal();
  });

  // Check Emergency Kill Switch state
  if (window.SandboxView) {
    window.SandboxView.checkKillSwitch();
  }

  // Fetch health check for AI status
  API.get("/health")
    .then((health) => {
      const isGemini = health.ai_provider === "GEMINI";
      const dot = document.getElementById("ai-status-dot");
      const text = document.getElementById("ai-status-text");
      if (dot && text) {
        dot.className = isGemini ? "status-dot" : "status-dot fallback";
        text.textContent = `AI: ${health.ai_provider}`;
      }
      const settingsAi = document.getElementById("settings-ai-mode");
      if (settingsAi) {
        settingsAi.textContent = health.ai_provider;
        settingsAi.className = isGemini ? "badge badge-success" : "badge badge-warning";
      }
    })
    .catch((err) => console.error("Health check error:", err));
});
