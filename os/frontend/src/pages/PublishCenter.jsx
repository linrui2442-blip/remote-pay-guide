import React, { useEffect, useMemo, useState } from "react";
import {
  collectPublishTaskAnalytics,
  createPublishTask,
  runPublishTask,
} from "../api";

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

export default function PublishCenter({
  assets = [],
  tasks = [],
  accounts = [],
  platforms = [],
  accountReadiness = {},
  onRefreshTasks,
  onRefreshAnalytics,
}) {
  const [platform, setPlatform] = useState("");
  const [accountId, setAccountId] = useState("");
  const [assetId, setAssetId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [privacyStatus, setPrivacyStatus] = useState("private");
  const [message, setMessage] = useState("");
  const [preparing, setPreparing] = useState(false);
  const [runningTaskId, setRunningTaskId] = useState(null);
  const [collectingTaskId, setCollectingTaskId] = useState(null);

  const platformMap = useMemo(
    () => Object.fromEntries(
      platforms.map((item) => [String(item.platform || "").toLowerCase(), item])
    ),
    [platforms]
  );

  const livePlatforms = useMemo(
    () => platforms.filter((item) => item.publish_ready === true),
    [platforms]
  );

  const readyAssets = useMemo(
    () => assets.filter((asset) => String(asset.status || "").toLowerCase() === "ready"),
    [assets]
  );

  const matchingAccounts = useMemo(
    () => accounts.filter(
      (account) => String(account.platform || "").toLowerCase() === platform
    ),
    [accounts, platform]
  );

  useEffect(() => {
    if (platform && platformMap[platform]?.publish_ready === true) return;
    const next = String(livePlatforms[0]?.platform || "").toLowerCase();
    setPlatform(next);
  }, [livePlatforms, platform, platformMap]);

  useEffect(() => {
    if (matchingAccounts.some((account) => String(account.id) === String(accountId))) return;
    setAccountId(matchingAccounts[0]?.id != null ? String(matchingAccounts[0].id) : "");
  }, [matchingAccounts, accountId]);

  useEffect(() => {
    if (readyAssets.some((asset) => asset.asset_id === assetId)) return;
    setAssetId(readyAssets[0]?.asset_id || "");
  }, [readyAssets, assetId]);

  const selectedPlatform = platformMap[platform] || {};
  const selectedAsset = readyAssets.find((asset) => asset.asset_id === assetId);
  const selectedAccount = matchingAccounts.find(
    (account) => String(account.id) === String(accountId)
  );

  const prepare = async () => {
    if (!platform || !accountId || !assetId) return;
    try {
      setPreparing(true);
      setMessage("正在校验资产、账号与平台执行能力；此步骤不会上传视频…");
      const result = await createPublishTask({
        asset_id: assetId,
        video_id: selectedAsset?.video_id || null,
        platform,
        account_id: Number(accountId),
        title: title.trim() || selectedAsset?.video_id || "Remote Pay Guide",
        description: description.trim(),
        tags: tags
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        privacy_status: privacyStatus,
        status: "pending",
      });
      const task = result.task || {};
      setMessage(
        result.created
          ? `发布任务 #${task.id} 已创建。当前只是 pending，不会自动上传；确认后再点击“立即发布”。`
          : `相同资产、账号和平台的发布任务 #${task.id} 已存在，未重复创建。`
      );
      await onRefreshTasks?.();
    } catch (error) {
      setMessage(error.message || "发布任务创建失败");
    } finally {
      setPreparing(false);
    }
  };

  const run = async (task) => {
    try {
      setRunningTaskId(task.id);
      setMessage(
        `正在执行发布任务 #${task.id}。这是显式发布操作，将调用 ${platformLabel(task.platform)} 实时接口…`
      );
      const result = await runPublishTask(task.id);
      const current = result.task || {};
      if (String(current.status || "").toLowerCase() === "published") {
        setMessage(
          `发布完成：任务 #${task.id}${current.platform_video_id ? ` · ${current.platform_video_id}` : ""}。`
        );
      } else {
        setMessage(
          `任务 #${task.id} 已执行，当前状态 ${current.status || "unknown"}${current.error_message ? `：${current.error_message}` : ""}。`
        );
      }
      await onRefreshTasks?.();
    } catch (error) {
      setMessage(error.message || "发布执行失败");
      await onRefreshTasks?.();
    } finally {
      setRunningTaskId(null);
    }
  };

  const collectAnalytics = async (task) => {
    try {
      setCollectingTaskId(task.id);
      setMessage(`正在采集发布任务 #${task.id} 的 ${platformLabel(task.platform)} Analytics…`);
      const result = await collectPublishTaskAnalytics(task.id);
      setMessage(
        `采集完成：${result.video_id || task.platform_video_id || "video"} · ${(result.views ?? 0).toLocaleString()} 次观看。`
      );
      await onRefreshAnalytics?.();
    } catch (error) {
      setMessage(error.message || "Analytics 采集失败");
    } finally {
      setCollectingTaskId(null);
    }
  };

  const canCollect = (task) => {
    const runtime = platformMap[String(task.platform || "").toLowerCase()]?.runtime || {};
    return String(task.status || "").toLowerCase() === "published" &&
      Boolean(task.platform_video_id) &&
      task.account_id != null &&
      Boolean(runtime.analytics_sync_registered);
  };

  return (
    <>
      <div className="page-heading compact">
        <div>
          <span className="eyebrow">PUBLISHING</span>
          <h1>发布中心</h1>
          <p>资产 → 发布任务 → 平台 Adapter。创建任务不会自动上传，只有点击“立即发布”才执行外部发布。</p>
        </div>
      </div>

      {message ? <div className="notice notice-page">{message}</div> : null}

      <section className="panel">
        <div className="panel-header">
          <div><span className="section-kicker">PLATFORM READINESS</span><h2>实时发布能力</h2></div>
          <span className="muted">{livePlatforms.length} 个平台已启用实时执行</span>
        </div>
        <div className="provider-pills">
          {platforms.map((item) => (
            <Badge key={item.platform} tone={item.publish_ready ? "success" : "neutral"}>
              {platformLabel(item.platform)} · {item.publish_ready
                ? `实时发布 · ${item.execution_mode || "live"}`
                : `已注册 · ${item.execution_mode || "未启用实时发布"}`}
            </Badge>
          ))}
        </div>
        {platforms.some((item) => item.publish_ready !== true) ? (
          <p className="muted">Facebook / Instagram / TikTok 等占位 Adapter 不会被 OS 当成实时发布能力，也不会误触模拟发布。</p>
        ) : null}
      </section>

      <section className="panel">
        <div className="panel-header">
          <div><span className="section-kicker">NEW PUBLISH TASK</span><h2>创建发布任务</h2></div>
          <Badge tone="neutral">只创建 · 不自动上传</Badge>
        </div>

        {livePlatforms.length === 0 ? (
          <EmptyState title="没有可执行的实时发布 Adapter" description="平台可以保持已注册，但只有明确声明 publish_ready 的 Adapter 才能创建实时发布任务。" />
        ) : (
          <>
            <div className="form-row">
              <select value={platform} onChange={(event) => setPlatform(event.target.value)}>
                {livePlatforms.map((item) => (
                  <option key={item.platform} value={String(item.platform || "").toLowerCase()}>
                    {platformLabel(item.platform)} · {item.execution_mode || "live"}
                  </option>
                ))}
              </select>
              <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
                <option value="">选择平台账号</option>
                {matchingAccounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.account_name || `Account #${account.id}`}
                  </option>
                ))}
              </select>
              <select value={assetId} onChange={(event) => setAssetId(event.target.value)}>
                <option value="">选择 Ready Video Asset</option>
                {readyAssets.map((asset) => (
                  <option key={asset.asset_id} value={asset.asset_id}>
                    {asset.video_id || asset.asset_id} · {asset.source_provider || "unknown"}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-row">
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="标题（留空则使用 video_id）"
              />
              <input
                value={tags}
                onChange={(event) => setTags(event.target.value)}
                placeholder="标签，用逗号分隔"
              />
              <select value={privacyStatus} onChange={(event) => setPrivacyStatus(event.target.value)}>
                <option value="private">Private</option>
                <option value="unlisted">Unlisted</option>
                <option value="public">Public</option>
              </select>
            </div>

            <div className="form-row">
              <input
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="描述（可选）"
              />
              <button
                className="primary-button"
                onClick={prepare}
                disabled={preparing || !selectedPlatform.publish_ready || !selectedAccount || !selectedAsset}
              >
                {preparing ? "校验中…" : "创建发布任务"}
              </button>
            </div>

            {!selectedAccount ? <div className="muted">当前平台还没有可选账号，请先在“平台账号”完成连接。</div> : null}
            {!selectedAsset ? <div className="muted">当前没有 status=ready 的 Video Asset；先从生产中心生成或登记资产。</div> : null}
          </>
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <div><span className="section-kicker">TASKS</span><h2>发布任务</h2></div>
          <span className="muted">{tasks.length} 条</span>
        </div>
        {tasks.length === 0 ? (
          <EmptyState title="暂无本地发布任务" description="选择 Ready Video Asset、平台和账号创建任务；创建后仍不会自动发布。" />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>ID</th><th>平台</th><th>资产 / 视频</th><th>账号</th><th>状态</th><th>执行能力</th><th></th></tr>
              </thead>
              <tbody>
                {tasks.map((task) => {
                  const status = String(task.status || "").toLowerCase();
                  const registration = platformMap[String(task.platform || "").toLowerCase()] || {};
                  const executable = registration.publish_ready === true && ["pending", "failed"].includes(status);
                  const running = runningTaskId === task.id;
                  const collecting = collectingTaskId === task.id;
                  const account = accounts.find((item) => String(item.id) === String(task.account_id));
                  return (
                    <tr key={task.id}>
                      <td>#{task.id}</td>
                      <td>{platformLabel(task.platform)}</td>
                      <td>{task.platform_video_id || task.video_id || task.asset_id || "—"}</td>
                      <td>{account?.account_name || (task.account_id != null ? `Account #${task.account_id}` : "—")}</td>
                      <td>
                        <Badge tone={status === "published" ? "success" : status === "failed" ? "danger" : status === "publishing" ? "info" : "neutral"}>
                          {task.status || "pending"}
                        </Badge>
                        {task.error_message ? <div className="muted">{task.error_message}</div> : null}
                      </td>
                      <td>
                        <Badge tone={registration.publish_ready ? "success" : "neutral"}>
                          {registration.publish_ready ? registration.execution_mode || "live" : "实时发布未启用"}
                        </Badge>
                      </td>
                      <td className="table-action">
                        {executable ? (
                          <button
                            className="primary-button"
                            onClick={() => run(task)}
                            disabled={running}
                            title="显式执行外部平台发布；不会由系统自动触发"
                          >
                            {running ? "发布中…" : status === "failed" ? "重试发布" : "立即发布"}
                          </button>
                        ) : null}
                        {canCollect(task) ? (
                          <button
                            className="secondary-button"
                            onClick={() => collectAnalytics(task)}
                            disabled={collecting || accountReadiness[task.account_id]?.ready !== true}
                            title={accountReadiness[task.account_id]?.ready === true ? "采集 Analytics" : "Analytics OAuth/Collector 尚未就绪"}
                          >
                            {collecting ? "采集中…" : "采集 Analytics"}
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
