import React, { useEffect, useMemo, useState } from "react";
import {
  apiGet,
  beginPlatformOAuth,
  collectPublishTaskAnalytics,
  createAccount,
  createProductionTask,
  getAccounts,
  getAnalyticsCollectorStatus,
  getNetworkProxySettings,
  getProductionProviders,
  getProductionStatus,
  getProductionTasks,
  getPublishTasks,
  runProductionTask,
  saveNetworkProxySettings,
  syncAccountAll,
} from "./api";
import PlatformOAuthCallback from "./pages/PlatformOAuthCallback.jsx";
import DataCenter from "./pages/DataCenter.jsx";

const NAV_ITEMS = [
  ["overview", "总览", "⌂"],
  ["accounts", "平台账号", "◎"],
  ["production", "生产中心", "▶"],
  ["publishing", "发布中心", "↑"],
  ["analytics", "数据中心", "▥"],
  ["platforms", "平台能力", "◇"],
  ["settings", "系统设置", "⚙"],
];

const PLATFORM_LABELS = {
  youtube: "YouTube",
  facebook: "Facebook",
  instagram: "Instagram",
  tiktok: "TikTok",
};


function platformLabel(name) {
  const key = String(name || "").toLowerCase();
  if (PLATFORM_LABELS[key]) return PLATFORM_LABELS[key];
  return key ? key.charAt(0).toUpperCase() + key.slice(1) : "Unknown";
}

function platformMark(name) {
  const label = platformLabel(name);
  if (label === "YouTube") return "YT";
  if (label === "Facebook") return "FB";
  if (label === "Instagram") return "IG";
  if (label === "TikTok") return "TK";
  return label.slice(0, 2).toUpperCase();
}

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

function PlatformPicker({ platforms, onClose, onSelect, connectingPlatform }) {
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section className="modal-card" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <span className="section-kicker">ADD PLATFORM</span>
            <h2>选择平台</h2>
            <p>平台列表来自当前运行时 Registry；以后新增 Adapter 会自动出现在这里。</p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭">×</button>
        </div>
        <div className="platform-picker-grid">
          {platforms.map((item) => {
            const name = String(item.platform || "").toLowerCase();
            const capability = item.capabilities || {};
            const runtime = item.runtime || {};
            const connector = runtime.account_connector;
            const connectable = Boolean(runtime.account_connector_registered);
            const configured = connector?.configured !== false;
            const connecting = connectingPlatform === name;
            return (
              <button
                key={name}
                className={`platform-choice ${connectable && configured ? "connectable" : ""}`}
                onClick={() => connectable && configured && onSelect(name)}
                disabled={!connectable || !configured || connecting}
              >
                <span className="platform-choice-logo">{platformMark(name)}</span>
                <span className="platform-choice-body">
                  <strong>{platformLabel(name)}</strong>
                  <small>
                    {connectable
                      ? configured
                        ? "点击后直接进入授权"
                        : "账号连接器已注册 · 配置待完成"
                      : capability.publish_supported
                        ? "发布适配器已存在 · 账号连接器待接入"
                        : "当前未启用连接"}
                  </small>
                </span>
                <span className="platform-choice-state">
                  {connecting ? "正在打开…" : connectable ? configured ? "连接" : "未配置" : "待接入"}
                </span>
              </button>
            );
          })}
        </div>
        {platforms.length === 0 && (
          <EmptyState title="正在读取平台 Registry" description="稍后会显示当前可用平台。" />
        )}
      </section>
    </div>
  );
}

function App() {
  const oauthCallbackMatch = window.location.pathname.match(/^\/oauth\/([^/]+)\/callback\/?$/i);
  if (oauthCallbackMatch) {
    return (
      <PlatformOAuthCallback
        platform={decodeURIComponent(oauthCallbackMatch[1]).toLowerCase()}
      />
    );
  }

  const viewFromUrl = new URLSearchParams(window.location.search).get("view");
  const [activeView, setActiveView] = useState(
    NAV_ITEMS.some(([key]) => key === viewFromUrl) ? viewFromUrl : "overview"
  );
  const [system, setSystem] = useState(null);
  const [assets, setAssets] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [platforms, setPlatforms] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [analyticsMessage, setAnalyticsMessage] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [accountReadiness, setAccountReadiness] = useState({});
  const [oauthMessage, setOAuthMessage] = useState("");
  const [productionStatus, setProductionStatus] = useState(null);
  const [productionTasks, setProductionTasks] = useState([]);
  const [providers, setProviders] = useState([]);
  const [provider, setProvider] = useState("github");
  const [githubWorkflow, setGithubWorkflow] = useState("");
  const [showPlatformPicker, setShowPlatformPicker] = useState(false);
  const [connectingPlatform, setConnectingPlatform] = useState("");
  const [syncingAccountId, setSyncingAccountId] = useState(null);
  const [proxySettings, setProxySettings] = useState({ mode: "system", proxy_url: "" });
  const [proxyMode, setProxyMode] = useState("system");
  const [proxyUrl, setProxyUrl] = useState("");
  const [proxyMessage, setProxyMessage] = useState("");
  const [savingProxy, setSavingProxy] = useState(false);

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
        const statuses = await Promise.all(
          records.map(async (account) => {
            const platform = String(account.platform || "").toLowerCase();
            if (!platform) return [account.id, { ready: false, reason: "account has no platform" }];
            try {
              const status = await getAnalyticsCollectorStatus(platform, account.id);
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

  const refreshProxy = () => {
    getNetworkProxySettings()
      .then((settings) => {
        setProxySettings(settings);
        setProxyMode(settings.mode || "system");
        setProxyUrl(settings.proxy_url || "");
      })
      .catch((error) => setProxyMessage(error.message));
  };

  useEffect(() => {
    apiGet("/").then(setSystem).catch(() => setSystem({ status: "offline" }));
    apiGet("/assets").then(setAssets).catch(() => {});
    refreshPublishTasks();
    apiGet("/publish/platforms").then(setPlatforms).catch(() => {});
    refreshAnalytics();
    refreshAccounts();
    refreshProduction();
    refreshProxy();
  }, []);

  const createTask = () => {
    const taskType = provider === "ai_gateway" ? "video_generation" : "video_batch";
    createProductionTask({
      task_type: taskType,
      provider,
      workflow: provider === "github" ? githubWorkflow : "",
      branch: "main",
      parameters: { task_type: taskType },
    }).then(refreshProduction);
  };

  const productionProviderRuntime = (providerName) =>
    providers.find((item) => item.name === providerName || item.provider === providerName) || {};

  const taskRunBlocker = (task) => {
    if (task.execution?.ready === false) {
      return task.execution.reason || "生产任务执行配置不完整";
    }
    const runtime = productionProviderRuntime(task.provider);
    if (task.provider === "ai_gateway" && runtime.configured === false) {
      const missing = (runtime.missing_configuration || []).join(", ");
      return missing ? `AI Gateway 尚未配置：${missing}` : "AI Gateway 远程端点尚未配置";
    }
    if (task.status && task.status !== "created") {
      return `当前状态 ${task.status} 不能重复启动`;
    }
    return "";
  };

  const runTask = (task) => {
    const blocker = taskRunBlocker(task);
    if (blocker) return;
    runProductionTask(task.id).then(refreshProduction);
  };

  const runtimeForPlatform = (platformName) => {
    const normalized = String(platformName || "").toLowerCase();
    return platforms.find(
      (item) => String(item.platform || "").toLowerCase() === normalized
    )?.runtime || {};
  };

  const connectPlatformAccount = async (accountId, platformName) => {
    const platform = String(platformName || "").toLowerCase();
    const runtime = runtimeForPlatform(platform);
    const connector = runtime.account_connector;
    if (!runtime.account_connector_registered) {
      throw new Error(`${platformLabel(platform)} 账号连接器尚未接入。`);
    }
    if (connector?.configured === false) {
      const missing = (connector.missing_configuration || []).join(", ");
      throw new Error(
        missing
          ? `${platformLabel(platform)} 账号连接配置不完整：${missing}`
          : `${platformLabel(platform)} 账号连接配置不完整。`
      );
    }

    const result = await beginPlatformOAuth(platform, accountId, "full");
    if (!result?.authorization_url) throw new Error(`未收到 ${platformLabel(platform)} 授权地址`);
    window.location.assign(result.authorization_url);
  };

  const addPlatform = async (platformName) => {
    const platform = String(platformName || "").toLowerCase();
    const runtime = runtimeForPlatform(platform);
    if (!runtime.account_connector_registered) {
      setOAuthMessage(`${platformLabel(platform)} 已有平台适配器，但账号授权连接器尚未接入。`);
      setShowPlatformPicker(false);
      return;
    }

    try {
      setConnectingPlatform(platform);
      setOAuthMessage(`正在创建 ${platformLabel(platform)} 账号连接并打开授权页面…`);
      const account = await createAccount({
        platform,
        account_name: `${platformLabel(platform)} Account`,
        status: "inactive",
      });
      setShowPlatformPicker(false);
      await connectPlatformAccount(account.id, platform);
    } catch (error) {
      setConnectingPlatform("");
      setOAuthMessage(error.message);
      refreshAccounts();
    }
  };

  const reconnectAccount = (account) => {
    const platform = String(account.platform || "").toLowerCase();
    setOAuthMessage(`正在打开 ${platformLabel(platform)} 授权页面…`);
    connectPlatformAccount(account.id, platform).catch((error) => setOAuthMessage(error.message));
  };

  const syncFullPlatformAccount = async (account) => {
    const platform = String(account.platform || "").toLowerCase();
    try {
      setSyncingAccountId(account.id);
      setOAuthMessage(`正在同步 ${platformLabel(platform)}：内容 → Analytics → AI Intelligence…`);
      const result = await syncAccountAll(account.id);
      const content = result.results?.find((item) => item.operation === "content_sync")?.result;
      const analytics = result.results?.find((item) => item.operation === "analytics_sync")?.result;
      const intelligence = result.results?.find((item) => item.operation === "intelligence_feedback")?.result;
      const firstFailure = result.failures?.[0]?.error;

      if (result.status === "failed") {
        throw new Error(firstFailure || `${platformLabel(platform)} 同步失败`);
      }

      const parts = [];
      if (content) {
        parts.push(`内容发现 ${content.found ?? 0}，新导入 ${content.imported ?? 0}`);
      }
      if (analytics) {
        parts.push(`Analytics 更新 ${analytics.collected ?? 0} 个 ACTIVE 内容`);
        if (analytics.account_metric) parts.push("账号级数据已更新");
      }
      if (intelligence) {
        parts.push(`Intelligence 新策略 ${intelligence.generated ?? 0}，复用 ${intelligence.reused ?? 0}`);
      }
      if ((result.skipped ?? 0) > 0) {
        parts.push("Intelligence 因上游失败未刷新");
      }
      if (result.status === "partial") {
        parts.push(`部分失败${firstFailure ? `：${firstFailure}` : ""}`);
      }
      setOAuthMessage(`同步完成：${parts.length ? parts.join("；") : "运行时任务已完成"}。`);
      apiGet("/assets").then(setAssets).catch(() => {});
      refreshPublishTasks();
      refreshAnalytics();
      refreshAccounts();
    } catch (error) {
      setOAuthMessage(error.message);
    } finally {
      setSyncingAccountId(null);
    }
  };

  const saveProxy = async () => {
    try {
      setSavingProxy(true);
      setProxyMessage("正在应用代理配置…");
      const result = await saveNetworkProxySettings({
        mode: proxyMode,
        proxy_url: proxyMode === "manual" ? proxyUrl.trim() : null,
      });
      setProxySettings(result);
      setProxyUrl(result.proxy_url || proxyUrl);
      setProxyMessage(
        proxyMode === "manual"
          ? "代理已保存并立即应用。以后更换代理，只需要回来修改这里。"
          : proxyMode === "disabled"
            ? "已关闭 OS 后端代理。"
            : "已切换为跟随系统代理。"
      );
    } catch (error) {
      setProxyMessage(error.message);
    } finally {
      setSavingProxy(false);
    }
  };

  const collectTaskAnalytics = (task) => {
    setAnalyticsMessage(`正在采集发布任务 #${task.id} 的 ${platformLabel(task.platform)} 数据…`);
    collectPublishTaskAnalytics(task.id)
      .then((result) => {
        setAnalyticsMessage(`采集完成：${result.video_id || task.platform_video_id}，${result.views ?? 0} 次观看。`);
        refreshAnalytics();
      })
      .catch((error) => setAnalyticsMessage(error.message));
  };

  const canCollectTask = (task) => {
    const runtime = runtimeForPlatform(task.platform);
    return Boolean(runtime.analytics_sync_registered) &&
      String(task.status || "").toLowerCase() === "published" &&
      Boolean(task.platform_video_id) &&
      task.account_id != null;
  };

  const publishedCount = tasks.filter(
    (task) => String(task.status || "").toLowerCase() === "published"
  ).length;
  const readyAccounts = accounts.filter(
    (account) => String(account.status || "").toLowerCase() === "connected" || accountReadiness[account.id]?.ready === true
  ).length;
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
          <div className="panel-header"><div><span className="section-kicker">BUSINESS LOOP</span><h2>增长闭环</h2></div></div>
          <div className="flow-row">
            {["内容", "流量", "用户意图", "Binance 转化", "AI Intelligence", "下一轮生产"].map((item, index, array) => (
              <React.Fragment key={item}>
                <div className="flow-node">{item}</div>
                {index < array.length - 1 && <span className="flow-arrow">→</span>}
              </React.Fragment>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header"><div><span className="section-kicker">ACCOUNTS</span><h2>平台连接</h2></div><button className="text-button" onClick={() => setActiveView("accounts")}>管理账号</button></div>
          <div className="status-list">
            <div><span>平台 Registry</span><strong>{platforms.length}</strong></div>
            <div><span>账号连接器</span><strong>{platforms.filter((item) => item.runtime?.account_connector_registered).length}</strong></div>
            <div><span>可用账号</span><strong>{readyAccounts}</strong></div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header"><div><span className="section-kicker">PRODUCTION</span><h2>生产运行时</h2></div><button className="text-button" onClick={() => setActiveView("production")}>打开生产中心</button></div>
          <div className="provider-pills"><Badge tone="neutral">GitHub Actions</Badge><Badge tone="info">AI Gateway · Remote</Badge></div>
          <p className="muted">现有 GitHub 生产线保持不变，AI 视频生产通过远程 Gateway 调用外部服务。</p>
        </section>
      </div>
    </>
  );

  const renderAccounts = () => (
    <>
      <div className="page-heading compact">
        <div><span className="eyebrow">ACCOUNTS</span><h1>平台账号</h1><p>账号连接、内容同步和 Analytics 统一通过运行时 Registry 调度。</p></div>
        <button className="primary-button add-platform-button" onClick={() => setShowPlatformPicker(true)}>+ 添加平台账号</button>
      </div>

      {oauthMessage && <div className="notice notice-page">{oauthMessage}</div>}

      <div className="cards-list">
        {accounts.length === 0 ? (
          <EmptyState title="还没有平台账号" description="点击“添加平台账号”，从当前 Platform Registry 选择要连接的平台。" />
        ) : accounts.map((account) => {
          const platform = String(account.platform || "").toLowerCase();
          const runtime = runtimeForPlatform(platform);
          const readiness = accountReadiness[account.id];
          const connector = runtime.account_connector;
          const connectable = Boolean(runtime.account_connector_registered);
          const connectorConfigured = connector?.configured !== false;
          const connected = String(account.status || "").toLowerCase() === "connected" || readiness?.ready === true;
          const syncable = Boolean(runtime.content_sync_registered || (runtime.analytics_supported && runtime.analytics_sync_registered));
          const syncing = syncingAccountId === account.id;
          return (
            <section className="account-card" key={account.id}>
              <div className="account-avatar">{platformMark(platform)}</div>
              <div className="account-main">
                <div className="account-title-row">
                  <strong>{platformLabel(platform)}</strong>
                  <Badge tone={connected ? "success" : "warning"}>{connected ? "已连接" : connectable ? connectorConfigured ? "需要授权" : "连接配置待完成" : "连接器待接入"}</Badge>
                </div>
                <span className="muted">{account.account_name} · Account #{account.id}</span>
                {readiness?.reason && runtime.analytics_supported && !readiness.ready && <span className="small-warning">{readiness.reason}</span>}
              </div>
              <div className="account-actions">
                {connected && syncable && (
                  <button className="secondary-button" onClick={() => syncFullPlatformAccount(account)} disabled={syncing}>
                    {syncing ? "同步中…" : "同步全部"}
                  </button>
                )}
                {connectable ? (
                  <button className="primary-button" onClick={() => reconnectAccount(account)} disabled={!connectorConfigured || syncing}>
                    {connected ? "重新授权" : `连接 ${platformLabel(platform)}`}
                  </button>
                ) : (
                  <button className="secondary-button" disabled>授权待接入</button>
                )}
              </div>
            </section>
          );
        })}
      </div>

      <section className="panel account-platform-summary">
        <div className="panel-header"><div><span className="section-kicker">REGISTRY</span><h2>可选平台</h2></div><span className="muted">{platforms.length} 个运行时平台</span></div>
        <div className="provider-pills">
          {platforms.map((item) => {
            const runtime = item.runtime || {};
            const connectorReady = runtime.account_connector_registered && runtime.account_connector?.configured !== false;
            return (
              <Badge key={item.platform} tone={connectorReady ? "success" : "neutral"}>
                {platformLabel(item.platform)} · {connectorReady ? "可连接" : runtime.account_connector_registered ? "连接配置待完成" : "Adapter Ready"}
              </Badge>
            );
          })}
        </div>
      </section>
      <JsonDetails title="平台运行时能力" data={platforms.map((item) => ({ platform: item.platform, runtime: item.runtime }))} />
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
          {provider === "github" ? (
            <select value={githubWorkflow} onChange={(event) => setGithubWorkflow(event.target.value)}>
              <option value="">选择 GitHub Workflow</option>
              <option value="render-launch02.yml">Legacy 批量生产 · short02-short10</option>
              <option value="os-github-bridge-test.yml">GitHub Bridge · 验证流程</option>
            </select>
          ) : null}
          <button
            className="primary-button"
            onClick={createTask}
            disabled={provider === "github" && !githubWorkflow}
          >
            创建任务
          </button>
        </div>
        {provider === "ai_gateway" && productionProviderRuntime("ai_gateway").configured === false ? (
          <div className="notice">
            AI Gateway 当前只走远程 HTTP 生产线；请先配置 {productionProviderRuntime("ai_gateway").missing_configuration?.join(", ") || "远程端点"}，不会回退到本地 GPU / 本地模型。
          </div>
        ) : null}
      </section>
      <section className="panel">
        <div className="panel-header"><div><span className="section-kicker">TASKS</span><h2>生产任务</h2></div><span className="muted">{productionTasks.length} 条</span></div>
        {productionTasks.length === 0 ? <EmptyState title="暂无生产任务" description="创建任务后会显示在这里。" /> : (
          <div className="table-wrap"><table><thead><tr><th>ID</th><th>类型</th><th>Provider</th><th>状态</th><th>执行</th><th></th></tr></thead><tbody>{productionTasks.map((task) => {
            const blocker = taskRunBlocker(task);
            return <tr key={task.id}><td>#{task.id}</td><td>{task.task_type || "—"}</td><td>{task.provider || "—"}</td><td><Badge tone={task.status === "completed" ? "success" : "neutral"}>{task.status || "created"}</Badge></td><td><Badge tone={blocker ? "neutral" : "success"}>{blocker ? "未就绪" : "可运行"}</Badge>{blocker ? <div className="muted" title={blocker}>{blocker}</div> : null}</td><td className="table-action"><button className="secondary-button" onClick={() => runTask(task)} disabled={Boolean(blocker)} title={blocker || "运行任务"}>运行</button></td></tr>;
          })}</tbody></table></div>
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
          <div className="table-wrap"><table><thead><tr><th>ID</th><th>平台</th><th>视频</th><th>状态</th><th></th></tr></thead><tbody>{tasks.map((task) => <tr key={task.id}><td>#{task.id}</td><td>{platformLabel(task.platform)}</td><td>{task.platform_video_id || task.video_id || "—"}</td><td><Badge tone={task.status === "published" ? "success" : task.status === "failed" ? "danger" : "neutral"}>{task.status}</Badge></td><td className="table-action">{canCollectTask(task) && <button className="secondary-button" onClick={() => collectTaskAnalytics(task)} disabled={accountReadiness[task.account_id]?.ready !== true}>采集 Analytics</button>}</td></tr>)}</tbody></table></div>
        )}
      </section>
    </>
  );

  const renderAnalytics = () => <DataCenter />;

  const renderPlatforms = () => (
    <>
      <div className="page-heading compact"><div><span className="eyebrow">PLATFORMS</span><h1>平台能力</h1><p>发布、账号连接、内容同步与 Analytics 都从运行时 Registry 发现。</p></div></div>
      <div className="platform-grid">
        {platforms.map((item) => {
          const capability = item.capabilities || {};
          const runtime = item.runtime || {};
          const name = String(item.platform || "").toLowerCase();
          return <section className="platform-card" key={item.platform}>
            <div className="platform-card-header"><div className="platform-logo">{platformMark(name)}</div><div><strong>{platformLabel(name)}</strong><span>{item.adapter}</span></div><Badge tone="success">ready</Badge></div>
            <div className="capability-row"><span>发布</span><Badge tone={capability.publish_supported ? "success" : "neutral"}>{capability.publish_supported ? "支持" : "未启用"}</Badge></div>
            <div className="capability-row"><span>账号连接</span><Badge tone={runtime.account_connector_registered ? "success" : "neutral"}>{runtime.account_connector_registered ? runtime.account_connector?.configured === false ? "待配置" : "已接入" : "待接入"}</Badge></div>
            <div className="capability-row"><span>内容同步</span><Badge tone={runtime.content_sync_registered ? "success" : "neutral"}>{runtime.content_sync_registered ? `已接入 · Active ${runtime.content_sync_active_limit || 10}` : "待接入"}</Badge></div>
            <div className="capability-row"><span>Analytics</span><Badge tone={runtime.analytics_sync_registered ? "success" : "neutral"}>{runtime.analytics_sync_registered ? "Collector 已接入" : capability.analytics_supported ? "能力已启用 · Collector 待接入" : "未启用"}</Badge></div>
            <div className="metric-tags">{(capability.metric_types || []).map((metric) => <span key={metric}>{metric}</span>)}</div>
          </section>;
        })}
      </div>
    </>
  );

  const renderSettings = () => (
    <>
      <div className="page-heading compact">
        <div><span className="eyebrow">SETTINGS</span><h1>系统设置</h1><p>配置 Remote Pay Guide OS 后端访问外部平台时使用的网络代理。</p></div>
      </div>

      <section className="panel settings-panel">
        <div className="panel-header">
          <div><span className="section-kicker">NETWORK</span><h2>代理配置</h2></div>
          <Badge tone={proxySettings.runtime_configured ? "success" : "neutral"}>{proxySettings.runtime_configured ? "代理已启用" : "当前未使用代理"}</Badge>
        </div>

        <div className="settings-form">
          <label className="setting-field">
            <span>代理模式</span>
            <select value={proxyMode} onChange={(event) => setProxyMode(event.target.value)}>
              <option value="manual">手动配置</option>
              <option value="system">跟随系统代理</option>
              <option value="disabled">不使用代理</option>
            </select>
          </label>

          {proxyMode === "manual" && (
            <label className="setting-field">
              <span>代理地址</span>
              <input
                value={proxyUrl}
                onChange={(event) => setProxyUrl(event.target.value)}
                placeholder="例如：http://127.0.0.1:7890"
              />
              <small>以后 VPN 或代理软件更换端口，直接修改这里即可，不需要改代码。</small>
            </label>
          )}

          <div className="settings-actions">
            <button className="primary-button" onClick={saveProxy} disabled={savingProxy || (proxyMode === "manual" && !proxyUrl.trim())}>
              {savingProxy ? "保存中…" : "保存并立即应用"}
            </button>
          </div>
        </div>

        {proxyMessage && <div className="notice">{proxyMessage}</div>}

        <div className="settings-status">
          <div><span>保存模式</span><strong>{proxySettings.mode || "system"}</strong></div>
          <div><span>当前代理</span><strong>{proxySettings.proxy_url || proxySettings.effective_proxy || "未配置"}</strong></div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header"><div><span className="section-kicker">NOTE</span><h2>使用方式</h2></div></div>
        <p className="muted">这里的代理只用于 OS 后端访问 Google、YouTube 以及未来接入的平台 API，不会改变你整个 Windows 的代理设置。保存后立即生效；下次启动 OS 会继续使用这里保存的配置。</p>
      </section>
    </>
  );

  const views = {
    overview: renderOverview,
    accounts: renderAccounts,
    production: renderProduction,
    publishing: renderPublishing,
    analytics: renderAnalytics,
    platforms: renderPlatforms,
    settings: renderSettings,
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block"><div className="brand-mark">R</div><div><strong>Remote Pay</strong><span>Guide OS</span></div></div>
        <nav>
          {NAV_ITEMS.map(([key, label, icon]) => (
            <button key={key} className={activeView === key ? "nav-item active" : "nav-item"} onClick={() => setActiveView(key)}><span className="nav-icon">{icon}</span>{label}</button>
          ))}
        </nav>
        <div className="sidebar-footer"><span className={system?.status === "running" ? "health-dot online" : "health-dot"} /><div><strong>{system?.status === "running" ? "Local OS Online" : "Local OS Offline"}</strong><span>localhost:8000</span></div></div>
      </aside>
      <main className="content-area">{views[activeView]()}</main>
      {showPlatformPicker && (
        <PlatformPicker platforms={platforms} onClose={() => setShowPlatformPicker(false)} onSelect={addPlatform} connectingPlatform={connectingPlatform} />
      )}
    </div>
  );
}

export default App;
