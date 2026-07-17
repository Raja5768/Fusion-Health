let token = localStorage.getItem("fusion_token") || "";

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, { ...options, headers });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(data.detail || text || "Request failed");
  return data;
}

async function authenticate(register = false) {
  const payload = { email: $("email").value, password: $("password").value };
  const data = await api(`/api/v1/auth/${register ? "register" : "login"}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  token = data.access_token;
  localStorage.setItem("fusion_token", token);
  await refresh();
}

async function refresh() {
  try {
    const [summary, decision] = await Promise.all([
      api("/api/v1/summary/today").catch(() => null),
      api("/api/v1/decision/today"),
    ]);
    $("readiness").textContent = decision.readiness_score;
    $("decision").textContent = decision.decision;
    $("sleep").textContent = summary?.sleep_hours ? `${summary.sleep_hours}h` : "--";
    $("recovery").textContent = summary?.recovery_score ? `${summary.recovery_score}%` : "--";
    $("summaryOutput").textContent = JSON.stringify({ summary, decision }, null, 2);
  } catch (error) {
    $("summaryOutput").textContent = error.message;
  }
}

$("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await authenticate(false);
});

$("register").addEventListener("click", () => authenticate(true));

$("connectWhoop").addEventListener("click", async () => {
  const data = await api("/api/v1/auth/whoop/connect");
  window.location.href = data.auth_url;
});

$("syncWhoop").addEventListener("click", async () => {
  $("summaryOutput").textContent = "Syncing WHOOP...";
  const result = await api("/api/v1/sync/whoop", { method: "POST" });
  $("connectionStatus").textContent = `Last sync: ${result.synced_at}`;
  await refresh();
});

$("generateKey").addEventListener("click", async () => {
  const data = await api("/api/v1/api-keys/generate", {
    method: "POST",
    body: JSON.stringify({ name: $("keyName").value || "Dashboard key" }),
  });
  $("apiKeyOutput").textContent = JSON.stringify(data, null, 2);
});

if (token) refresh();
