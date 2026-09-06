from pathlib import Path
import re


APP = Path('os/frontend/src/App.jsx')
text = APP.read_text(encoding='utf-8')
original = text


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one match, found {count}')
    text = text.replace(old, new, 1)


def regex_once(pattern, replacement, label):
    global text
    text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one match, found {count}')


replace_once('  beginYouTubeOAuth,\n', '  beginPlatformOAuth,\n', 'generic OAuth import')
replace_once('  collectAccountAnalytics,\n', '', 'remove account analytics import')
replace_once('  getYouTubeOAuthStatus,\n', '', 'remove YouTube status import')
replace_once('  syncAccount,\n', '  syncAccountAll,\n', 'unified sync import')
replace_once('\nconst PLATFORM_CONNECTORS = { youtube: "google_oauth" };\n', '\n', 'remove frontend connector map')

replace_once(
'''            const capability = item.capabilities || {};
            const connector = PLATFORM_CONNECTORS[name];
            const connecting = connectingPlatform === name;
            return (
              <button
                key={name}
                className={`platform-choice ${connector ? "connectable" : ""}`}
                onClick={() => connector && onSelect(name)}
                disabled={!connector || connecting}
              >
                <span className="platform-choice-logo">{platformMark(name)}</span>
                <span className="platform-choice-body">
                  <strong>{platformLabel(name)}</strong>
                  <small>
                    {connector
                      ? "点击后直接进入授权"
                      : capability.publish_supported
                        ? "发布适配器已存在 · 账号授权待接入"
                        : "当前未启用连接"}
                  </small>
                </span>
                <span className="platform-choice-state">
                  {connecting ? "正在打开…" : connector ? "连接" : "待接入"}
                </span>
              </button>
            );''',
'''            const capability = item.capabilities || {};
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
            );''',
'platform picker runtime connector',
)

replace_once('  const [youtubeOAuthStatus, setYouTubeOAuthStatus] = useState(null);\n', '', 'remove YouTube OAuth state')
replace_once('  const [collectingAnalyticsAccountId, setCollectingAnalyticsAccountId] = useState(null);\n', '', 'remove split analytics sync state')

regex_once(
    r'''  const refreshAccounts = \(\) => \{.*?\n  \};\n\n  const refreshProxy''',
'''  const refreshAccounts = () => {
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

  const refreshProxy''',
    'generic account readiness',
)

replace_once(
'''    getYouTubeOAuthStatus()
      .then(setYouTubeOAuthStatus)
      .catch((error) => setYouTubeOAuthStatus({ configured: false, reason: error.message }));
''',
'',
'remove dedicated YouTube status refresh',
)

regex_once(
    r'''  const connectYouTube = async \(accountId\) => \{.*?\n  const syncPlatformAccount = async \(account\) => \{''',
'''  const runtimeForPlatform = (platformName) => {
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

  const syncFullPlatformAccount = async (account) => {''',
    'generic connector and unified sync boundary',
)

regex_once(
    r'''  const syncFullPlatformAccount = async \(account\) => \{.*?\n  const saveProxy = async \(\) => \{''',
'''  const syncFullPlatformAccount = async (account) => {
    const platform = String(account.platform || "").toLowerCase();
    try {
      setSyncingAccountId(account.id);
      setOAuthMessage(`正在同步 ${platformLabel(platform)}：内容 → 账号 Analytics → ACTIVE 内容 Analytics…`);
      const result = await syncAccountAll(account.id);
      const content = result.results?.find((item) => item.operation === "content_sync")?.result;
      const analytics = result.results?.find((item) => item.operation === "analytics_sync")?.result;
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

  const saveProxy = async () => {''',
    'replace split sync functions',
)

replace_once(
'''  const collectTaskAnalytics = (task) => {
    setAnalyticsMessage(`正在采集发布任务 #${task.id} 的 YouTube 数据…`);
    collectPublishTaskAnalytics(task.id)
      .then((result) => {
        setAnalyticsMessage(`采集完成：${result.video_id || task.platform_video_id}，${result.views ?? 0} 次观看。`);
        refreshAnalytics();
      })
      .catch((error) => setAnalyticsMessage(error.message));
  };

  const canCollectTask = (task) =>
    String(task.platform || "").toLowerCase() === "youtube" &&
    String(task.status || "").toLowerCase() === "published" &&
    Boolean(task.platform_video_id) &&
    task.account_id != null;
''',
'''  const collectTaskAnalytics = (task) => {
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
''',
'generic publish analytics action',
)

replace_once(
'  const readyAccounts = accounts.filter((account) => accountReadiness[account.id]?.ready === true).length;\n',
'''  const readyAccounts = accounts.filter(
    (account) => String(account.status || "").toLowerCase() === "connected" || accountReadiness[account.id]?.ready === true
  ).length;
''',
'generic connected account count',
)

replace_once(
'''            <div><span>YouTube OAuth</span><Badge tone={youtubeOAuthStatus?.configured ? "success" : "warning"}>{youtubeOAuthStatus?.configured ? "已配置" : "待配置"}</Badge></div>''',
'''            <div><span>账号连接器</span><strong>{platforms.filter((item) => item.runtime?.account_connector_registered).length}</strong></div>''',
'generic overview connector count',
)

regex_once(
    r'''  const renderAccounts = \(\) => \(.*?\n  const renderProduction = \(\) => \(''',
'''  const renderAccounts = () => (
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

  const renderProduction = () => (''',
    'registry-driven account screen',
)

regex_once(
    r'''  const renderPlatforms = \(\) => \(.*?\n  const renderSettings = \(\) => \(''',
'''  const renderPlatforms = () => (
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

  const renderSettings = () => (''',
    'runtime platform capabilities screen',
)

for forbidden in [
    'PLATFORM_CONNECTORS',
    'beginYouTubeOAuth',
    'platform === "youtube"',
    'String(task.platform || "").toLowerCase() === "youtube"',
    'syncAccountAnalytics',
    'syncPlatformAccount',
]:
    if forbidden in text:
        raise RuntimeError(f'provider-specific frontend branch remains: {forbidden}')

if text == original:
    raise RuntimeError('frontend migration made no changes')

APP.write_text(text, encoding='utf-8')
print('R16 provider-neutral frontend migration applied')
