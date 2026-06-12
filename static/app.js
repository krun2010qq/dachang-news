const state = {
  platform: "",
  query: "",
};

const platformTabs = document.getElementById("platform-tabs");
const newsGrid = document.getElementById("news-grid");
const statsGrid = document.getElementById("stats-grid");
const statusPill = document.getElementById("status-pill");
const lastUpdated = document.getElementById("last-updated");
const refreshBtn = document.getElementById("refresh-btn");
const searchInput = document.getElementById("search-input");

function badgeClass(platform) {
  const key = (platform || "").toLowerCase();
  if (key.includes("google")) return "google";
  if (key.includes("百度") || key.includes("baidu")) return "baidu";
  if (key.includes("bing")) return "bing";
  if (key.includes("政务") || key.includes("gov")) return "gov";
  return "default";
}

function renderStats(stats) {
  const platformText = (stats.platforms || [])
    .slice(0, 3)
    .map((p) => `${p.name} ${p.count}`)
    .join(" · ");

  statsGrid.innerHTML = `
    <div class="stat-card">
      <div class="stat-label">新闻总数</div>
      <div class="stat-value">${stats.total || 0}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">平台覆盖</div>
      <div class="stat-value">${(stats.platforms || []).length}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">最近抓取</div>
      <div class="stat-value" style="font-size:1.1rem">${stats.last_fetch || "暂无"}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">热门来源</div>
      <div class="stat-value" style="font-size:0.95rem;font-weight:500;line-height:1.5">${platformText || "暂无"}</div>
    </div>
  `;

  const tabs = ['<button class="tab active" data-platform="">全部平台</button>'];
  for (const p of stats.platforms || []) {
    tabs.push(
      `<button class="tab" data-platform="${p.name}">${p.name} (${p.count})</button>`
    );
  }
  platformTabs.innerHTML = tabs.join("");
  platformTabs.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.platform = btn.dataset.platform || "";
      platformTabs.querySelectorAll(".tab").forEach((el) => el.classList.remove("active"));
      btn.classList.add("active");
      loadNews();
    });
  });

  lastUpdated.textContent = `最近更新：${stats.last_fetch || "暂无"}`;
  statusPill.textContent = stats.last_status === "error" ? "抓取异常" : "系统正常";
  statusPill.className = `status-pill ${stats.last_status === "error" ? "error" : "ok"}`;
}

function renderNews(items) {
  if (!items.length) {
    newsGrid.innerHTML = '<div class="empty-card">暂无匹配新闻，可点击右上角立即刷新。</div>';
    return;
  }

  newsGrid.innerHTML = items
    .map(
      (item) => `
      <article class="news-card">
        <div class="news-top">
          <span class="badge ${badgeClass(item.platform)}">${item.platform}</span>
          <span class="news-time">${item.published_at || item.fetched_at?.slice(0, 16) || ""}</span>
        </div>
        <h2><a href="${item.url}" target="_blank" rel="noopener noreferrer">${item.title}</a></h2>
        <p class="news-summary">${item.summary || "点击查看原文"}</p>
        <div class="news-footer">
          <span>${item.source}</span>
          <span class="category-pill">${item.category}</span>
        </div>
      </article>
    `
    )
    .join("");
}

async function loadStats() {
  const res = await fetch("/api/stats");
  const stats = await res.json();
  renderStats(stats);
}

async function loadNews() {
  const params = new URLSearchParams();
  if (state.platform) params.set("platform", state.platform);
  if (state.query) params.set("q", state.query);
  const res = await fetch(`/api/news?${params.toString()}`);
  const data = await res.json();
  renderNews(data.items || []);
}

async function refreshNews() {
  refreshBtn.disabled = true;
  refreshBtn.textContent = "刷新中...";
  try {
    await fetch("/api/refresh", { method: "POST" });
    await Promise.all([loadStats(), loadNews()]);
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.textContent = "立即刷新";
  }
}

searchInput.addEventListener("input", () => {
  state.query = searchInput.value.trim();
  loadNews();
});

refreshBtn.addEventListener("click", refreshNews);

Promise.all([loadStats(), loadNews()]).catch(() => {
  newsGrid.innerHTML = '<div class="empty-card">加载失败，请稍后重试。</div>';
});
