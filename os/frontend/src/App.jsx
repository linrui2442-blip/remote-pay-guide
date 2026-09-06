import React, { useEffect, useMemo, useState } from "react";
import {
  apiGet,
  beginYouTubeOAuth,
  collectPublishTaskAnalytics,
  createAccount,
  createProductionTask,
  getAccounts,
  getAnalyticsCollectorStatus,
  getProductionProviders,
  getProductionStatus,
  getProductionTasks,
  getPublishTasks,
  getYouTubeOAuthStatus,
  runProductionTask,
} from "./api";
import YouTubeOAuthCallback from "./pages/YouTubeOAuthCallback.jsx";

const NAV_ITEMS = [
  ["overview", "总览", "⌂"],
  ["accounts", "平台账号", "◎"],
  ["production", "生产中心", "▶"],
  ["publishing", "发布中心", "↑"],
  ["analytics", "数据中心", "▥"],
  ["platforms", "平台能力", "◇"],
];

function Badge({ tone = "neutral", children }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function EmptyState({ title, description }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">·</div>
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
  );
}

function StatCard({ label, value, hint }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}

function JsonDetails({ title = "查看原始数据", data }) {
  return (
    <details className="json-details">
      <summary>{title}</summary>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}

function App() {
  if (window.location.pathname === "/oauth/youtube/callback") {
    return <YouTubeOAuthCallback />;
  }

  const [activeView, setActiveView] = useState("overview");
  const [system, setSystem] = useState(null);
  const [assets, setAssets] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [platforms, setPlatforms] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [analyticsMessage, setAnalyticsMessage] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [accountReadiness, setAccountReadiness] = useState({});
  const [youtubeOAuthStatus, setYouTubeOAuthStatus] = useState(null);
  const [newYouTubeAccount, setNewYouTubeAccount] = useState("");
  const [oauthMessage, setOAuthMessage] = useState("");
  const [productionStatus, setProductionStatus] = useState(null);
  const [productionTasks, setProductionTasks] = useState([]);
  const [providers, setProviders] = useState([]);
  const [provider, setProvider] = useState("github");

  const refreshProduction = () => {
    getProductionStatus().then(setProductionStatus).catch(() => {});
    getProductionTasks().then(setProductionTasks).catch(() => {});
    getProductionProviders().then(setProviders).catch(() => {});
  };

  const refreshAnalytics = () => {
    apiGet("/analytics/metrics/current").then(setMetrics).catch(() => {});
  };

  const refreshPublishTasks = () => {
    getPublishTasks().then(setTasks).catch(() => {});
  };

  const refreshAccounts = () => {
    getAccounts()
      .then(async (records) => {
        setAccounts(records);
        const youtubeAccounts = records.filter(
          (account) => String(account.platform || "").toLowerCase() === "youtube"
        );
        const statuses = await Promise.all(
          youtubeAccounts.map(async (account) => {
            try {
              const status = await getAnalyticsCollectorStatus("youtube", account.id);
              return [account.id, status];
            } catch (error) {
              return [account.id, { ready: false, reason: error.message }];
            }
          })
        );
        setAccountReadiness(Object.fromEntries(statuses));
      })
      .catch((error) => setOAuthMessage(error.message));
  };

  useEffect(() => {
    apiGet("/").then(setSystem).catch(() => setSystem({ status: "offline" }));
    apiGet("/assets").then(setAssets).catch(() => {});
    refreshPublishTasks();
    apiGet("/publish/platforms").then(setPlatforms).catch(() => {});
    refreshAnalytics();
    getYouTubeOAuthStatus()
      .then(setYouTubeOAuthStatus)
      .catch((error) => setYouTubeOAuthStatus({ configured: false, reason: error.message }));
    refreshAccounts();
    refreshProduction();
  }, []);

  const createTask = () => {
    createProductionTask({
      task_type: provider === "ai_gateway" ? "video_generation" : "video_render",
      provider,
      workflow: "render.yml",
      branch: "main",
    }).then(refreshProduction);
  };

  const runTask = (id) => runProductionTask(id).then(refreshProduction);

  const addYouTubeAccount = () => {
    const accountName = newYouTubeAccount.trim();
    if (!accountName) {
      setOAuthMessage("请先输入 YouTube 账号名称。");
      return;
    }
    createAccount({ platform: "youtube", account_name: accountName, status: "inactive" })
      .then(() => {
        setNewYouTubeAccount("");
        setOAuthMessage("账号已添加。下一步连接 Google 完成发布与数据权限授权。");
        refreshAccounts();
      })
      .catch((error) => setOAuthMessage(error.message));
  };

  const connectYouTube = (accountId) => {
    if (youtubeOAuthStatus && youtubeOAuthStatus.configured === false) {
      const missing = (youtubeOAuthStatus.missing_configuration || []).join(", ");
      setOAuthMessage(
        missing ? `YouTube OAuth 配置不完整：${missing}` : "YouTube OAuth 配置不完整。"
      );
      return;
    }

    setOAuthMessage("正在打开 Google 授权页面…");
    beginYouTubeOAuth(accountId, "full")
      .then((result) => {
        if (!result?.authorization_url) {
          throw new Error("未收到 YouTube 授权地址");
        }
        window.location.assign(result.authorization_url);
      })
      .catch((error) => setOAuthMessage(error.message));
  };

  const collectTaskAnalytics = (task) => {
    setAnalyticsMessage(`正在采集发布任务 #${task.id} 的 YouTube 数据…`);
    collectPublishTaskAnalytics(task.id)
      .then((result) => {
        setAnalyticsMessage(
          `采集完成：${result.video_id || task.platform_video_id}，${result.views ?? 0} 次观看。`
        );
        refreshAnalytics();
      })
      .catch((error) => setAnalyticsMessage(error.message));
  };

  const canCollectTask = (task) =>
    String(task.platform || "").toLowerCase() === "youtube" &&
    String(task.status || "").toLowerCase() === "published" &&
    Boolean(task.platform_video_id) &&
    task.account_id != null;

  const publishedCount = tasks.filter(
    (task) => String(task.status || "").toLowerCase() === "published"
  ).length;
  const readyAccounts = accounts.filter((account) => accountReadiness[account.id]?.ready === true).length;
  const totalViews = useMemo(
    () => metrics.reduce((sum, item) => sum + Number(item.views || 0), 0),
    [metrics]
  );
  const totalClicks = useMemo(
    () => metrics.reduce((sum, item) => sum + Number(item.clicks || 0), 0),
    [metrics]
  );

  const renderOverview = () => (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">CONTROL CENTER</span>
          <h1>Remote Pay Guide OS</h1>
          <p>内容生产、发布、流量和转化数据统一控制台。</p>
        </div>
        <Badge tone={system?.status === "running" ? "success" : "danger"}>
          <span className="status-dot" /> {system?.status === "running" ? "系统运行中" : "系统离线"}
        </Badge>
      </div>

      <div className="stats-grid">
        <StatCard label="视频资产" value={assets.length} hint="已登记到资产层" />
        <StatCard label="发布任务" value={publishedCount} hint={`共 ${tasks.length} 个任务`} />
        <StatCard label="可用账号" value={readyAccounts} hint={`共 ${accounts.length} 个平台账号`} />
        <StatCard label="当前观看" value={totalViews.toLocaleString()} hint={`${totalClicks.toLocaleString()} 次点击`} />
      </div>

      <div className="dashboard-grid">
        <section className="panel panel-wide">
          <div className="panel-header">
            <div>
              <span className="section-kicker">BUSINESS LOOP</span>
              <h2>增长闭环</h2>
            </div>
          </div>
          <div className="flow-row">
            {["内容", "流量", "用户意图", "Binance 转化", "AI Intelligence", "下一轮生产"].map(
              (item, index, array) => (
                <React.Fragment key={item}>
                  <div className="flow-node">{item}</div>
                  {index < array.length - 1 && <span className="flow-arrow">→</span>}
                </React.Fragment>
              )
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <span className="section-kicker">YOUTUBE</span>
              <h2>授权状态</h2>
            </div>
            <button className="text-button" onClick={() => setActiveView("accounts")}>管理账号</button>
          </div>
          <div className="status-list">
            <div><span>OAuth 配置</span><Badge tone={youtubeOAuthStatus?.configured ? "success" : "warning"}>{youtubeOAuthStatus?.configured ? "已配置" : "待配置"}</Badge></div>
            <div><span>Analytics API</span><Badge tone="success">已接入</Badge></div>
            <div><span>已授权账号</span><strong>{readyAccounts}</strong></div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <span className="section-kicker">PRODUCTION</span>
              <h2>生产运行时</h2>
            </div>
            <button className="text-button" onClick={() => setActiveView("production")}>打开生产中心</button>
          </div>
          <div className="provider-pills">
            <Badge tone="neutral">GitHub Actions</Badge>
            <Badge tone="info">AI Gateway · Remote</Badge>
          </div>
          <p className="muted">现有 GitHub 生产线保持不变，AI 视频生产通过远程 Gateway 调用外部服务。</p>
        </section>
      </div>
    </>
  );

  const renderAccounts = () => (
    <>
      <div className="page-heading compact">
        <div><span className="eyebrow">ACCOUNTS</span><h1>平台账号</h1><p>连接发布账号并管理数据读取权限。</p></div>
      </div>

      <section className="panel">
        <div className="panel-header">
          <div><span className="section-kicker">YOUTUBE OAUTH</span><h2>添加 YouTube 账号</h2></div>
          <Badge tone={youtubeOAuthStatus?.configured ? "success" : "warning"}>{youtubeOAuthStatus?.configured ? "OAuth 已就绪" : "OAuth 未配置"}</Badge>
        </div>
        <div className="form-row">
          <input value={newYouTubeAccount} onChange={(event) => setNewYouTubeAccount(event.target.value)} placeholder="例如：Remote Pay Guide YouTube" />
          <button className="primary-button" onClick={addYouTubeAccount}>添加账号</button>
        </div>
        {oauthMessage && <div className="notice">{oauthMessage}</div>}
      </section>

      <div className="cards-list">
        {accounts.length === 0 ? (
          <EmptyState title="还没有平台账号" description="先添加 YouTube 账号，然后完成 Google 授权。" />
        ) : accounts.map((account) => {
          const readiness = accountReadiness[account.id];
          const isYoutube = String(account.platform || "").toLowerCase() === "youtube";
          return (
            <section className="account-card" key={account.id}>
              <div className="account-avatar">YT</div>
              <div className="account-main">
                <div className="account-title-row"><strong>{account.account_name}</strong><Badge tone={readiness?.ready ? "success" : "warning"}>{readiness?.ready ? "发布 + Analytics 已授权" : "需要授权"}</Badge></div>
                <span className="muted">{account.platform} · Account #{account.id}</span>
                {readiness?.reason && !readiness.ready && <span className="small-warning">{readiness.reason}</span>}
              </div>
              {isYoutube && (
                <button className="primary-button" onClick={() => connectYouTube(account.id)} disabled={youtubeOAuthStatus?.configured === false}>
                  {readiness?.ready ? "重新授权" : "连接 YouTube"}
                </button>
              )}
            </section>
          );
        })}
      </div>
      <JsonDetails title="OAuth 技术状态" data={youtubeOAuthStatus || { status: "checking" }} />
    </>
  );

  const renderProduction = () => (
    <>
      <div className="page-heading compact"><div><span className="eyebrow">PRODUCTION</span><h1>生产中心</h1><p>统一调度 GitHub 生产线与 AI Gateway 远程生产线。</p></div></div>
      <section className="panel">
        <div className="panel-header"><div><span className="section-kicker">NEW TASK</span><h2>创建生产任务</h2></div><Badge tone="success">{productionStatus?.status || "ready"}</Badge></div>
        <div className="form-row">
          <select value={provider} onChange={(event) => setProvider(event.target.value)}>
            <option value="github">GitHub Actions</option>
            <option value="ai_gateway">AI Gateway（远程）</option>
          </select>
          <button className="primary-button" onClick={createTask}>创建任务</button>
        </div>
      </section>
      <section className="panel">
        <div className="panel-header"><div><span className="section-kicker">TASKS</span><h2>生产任务</h2></div><span className="muted">{productionTasks.length} 条</span></div>
        {productionTasks.length === 0 ? <EmptyState title="暂无生产任务" description="创建任务后会显示在这里。" /> : (
          <div className="table-wrap"><table><thead><tr><th>ID</th><th>类型</th><th>Provider</th><th>状态</th><th></th></tr></thead><tbody>{productionTasks.map((task) => <tr key={task.id}><td>#{task.id}</td><td>{task.task_type || "—"}</td><td>{task.provider || "—"}</td><td><Badge tone={task.status === "completed" ? "success" : "neutral"}>{task.status || "created"}</Badge></td><td className="table-action"><button className="secondary-button" onClick={() => runTask(task.id)}>运行</button></td></tr>)}</tbody></table></div>
        )}
      </section>
      <JsonDetails title="Provider 技术信息" data={providers} />
    </>
  );

  const renderPublishing = () => (
    <>
      <div className="page-heading compact"><div><span className="eyebrow">PUBLISHING</span><h1>发布中心</h1><p>查看各平台发布状态，并从已发布视频直接采集数据。</p></div></div>
      {analyticsMessage && <div className="notice">{analyticsMessage}</div>}
      <section className="panel">
        <div className="panel-header"><div><span className="section-kicker">TASKS</span><h2>发布任务</h2></div><span className="muted">{tasks.length} 条</span></div>
        {tasks.length === 0 ? <EmptyState title="暂无本地发布任务" description="现有 legacy/Postiz 发布记录尚未导入 OS Publish Center。" /> : (
          <div className="table-wrap"><table><thead><tr><th>ID</th><th>平台</th><th>视频</th><th>状态</th><th></th></tr></thead><tbody>{tasks.map((task) => <tr key={task.id}><td>#{task.id}</td><td className="capitalize">{task.platform}</td><td>{task.platform_video_id || task.video_id || "—"}</td><td><Badge tone={task.status === "published" ? "success" : task.status === "failed" ? "danger" : "neutral"}>{task.status}</Badge></td><td className="table-action">{canCollectTask(task) && <button className="secondary-button" onClick={() => collectTaskAnalytics(task)} disabled={accountReadiness[task.account_id]?.ready !== true}>采集 Analytics</button>}</td></tr>)}</tbody></table></div>
        )}
      </section>
    </>
  );

  const renderAnalytics = () => (
    <>
      <div className="page-heading compact"><div><span className="eyebrow">DATA CENTER</span><h1>数据中心</h1><p>当前平台流量快照。历史快照继续保留，但决策使用最新数据。</p></div></div>
      <div className="stats-grid">
        <StatCard label="当前观看" value={totalViews.toLocaleString()} />
        <StatCard label="当前点击" value={totalClicks.toLocaleString()} />
        <StatCard label="指标快照" value={metrics.length} />
        <StatCard label="视频资产" value={assets.length} />
      </div>
      <section className="panel">
        <div className="panel-header"><div><span className="section-kicker">TRAFFIC</span><h2>平台表现</h2></div></div>
        {metrics.length === 0 ? <EmptyState title="还没有 Analytics 数据" description="完成 YouTube 授权后，可从发布中心采集真实数据。" /> : (
          <div className="table-wrap"><table><thead><tr><th>视频</th><th>平台</th><th>观看</th><th>点击</th><th>平均观看</th><th>留存</th></tr></thead><tbody>{metrics.map((item, index) => <tr key={`${item.video_id || "metric"}-${index}`}><td>{item.video_id || item.content_id || "—"}</td><td className="capitalize">{item.platform}</td><td>{Number(item.views || 0).toLocaleString()}</td><td>{Number(item.clicks || 0).toLocaleString()}</td><td>{item.average_view_duration ?? "—"}</td><td>{item.retention != null ? `${item.retention}%` : "—"}</td></tr>)}</tbody></table></div>
        )}
      </section>
    </>
  );

  const renderPlatforms = () => (
    <>
      <div className="page-heading compact"><div><span className="eyebrow">PLATFORMS</span><h1>平台能力</h1><p>当前 Adapter 与能力状态。未来新增平台无需改核心发布逻辑。</p></div></div>
      <div className="platform-grid">
        {platforms.map((item) => {
          const capability = item.capabilities || {};
          return <section className="platform-card" key={item.platform}>
            <div className="platform-card-header"><div className="platform-logo">{String(item.platform || "?").slice(0, 2).toUpperCase()}</div><div><strong className="capitalize">{item.platform}</strong><span>{item.adapter}</span></div><Badge tone="success">ready</Badge></div>
            <div className="capability-row"><span>发布</span><Badge tone={capability.publish_supported ? "success" : "neutral"}>{capability.publish_supported ? "支持" : "未启用"}</Badge></div>
            <div className="capability-row"><span>Analytics</span><Badge tone={capability.analytics_supported ? "success" : "neutral"}>{capability.analytics_supported ? "支持" : "未启用"}</Badge></div>
            <div className="metric-tags">{(capability.metric_types || []).map((metric) => <span key={metric}>{metric}</span>)}</div>
          </section>;
        })}
      </div>
    </>
  );

  const views = {
    overview: renderOverview,
    accounts: renderAccounts,
    production: renderProduction,
    publishing: renderPublishing,
    analytics: renderAnalytics,
    platforms: renderPlatforms,
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">R</div>
          <div><strong>Remote Pay</strong><span>Guide OS</span></div>
        </div>
        <nav>
          {NAV_ITEMS.map(([key, label, icon]) => (
            <button key={key} className={activeView === key ? "nav-item active" : "nav-item"} onClick={() => setActiveView(key)}>
              <span className="nav-icon">{icon}</span>{label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className={system?.status === "running" ? "health-dot online" : "health-dot"} />
          <div><strong>{system?.status === "running" ? "Local OS Online" : "Local OS Offline"}</strong><span>localhost:8000</span></div>
        </div>
      </aside>
      <main className="content-area">{views[activeView]()}</main>
    </div>
  );
}

export default App;
