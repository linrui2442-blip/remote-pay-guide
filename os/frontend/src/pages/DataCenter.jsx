import React, { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "../api";

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

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function formatSeconds(value) {
  const seconds = Number(value || 0);
  if (!Number.isFinite(seconds) || seconds <= 0) return "0 秒";
  if (seconds < 60) return `${Math.round(seconds)} 秒`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = Math.round(seconds % 60);
  if (hours > 0) return `${hours} 小时 ${minutes} 分`;
  return `${minutes} 分 ${remainder} 秒`;
}

function formatDuration(value) {
  if (value == null) return "—";
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) return "—";
  return `${seconds.toFixed(seconds >= 10 ? 1 : 2)} 秒`;
}

function formatPercent(value) {
  if (value == null) return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return `${number.toFixed(2)}%`;
}

function formatMoney(value) {
  const number = Number(value || 0);
  return number.toLocaleString(undefined, {
    minimumFractionDigits: number % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  });
}

function formatDate(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value).slice(0, 10);
  return parsed.toLocaleDateString();
}

function TrackingBadge({ state, pinned }) {
  if (pinned) return <span className="dc-badge dc-badge-pinned">持续跟踪</span>;
  if (state === "active") return <span className="dc-badge dc-badge-active">ACTIVE</span>;
  if (state === "historical") return <span className="dc-badge dc-badge-history">HISTORICAL</span>;
  if (state === "archived") return <span className="dc-badge">ARCHIVED</span>;
  return <span className="dc-badge">UNTRACKED</span>;
}

function MetricCard({ label, value, hint }) {
  return (
    <div className="dc-metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </div>
  );
}

export default function DataCenter() {
  const [accounts, setAccounts] = useState([]);
  const [platforms, setPlatforms] = useState([]);
  const [accountId, setAccountId] = useState("");
  const [platform, setPlatform] = useState("");
  const [scope, setScope] = useState("active");
  const [sortBy, setSortBy] = useState("views");
  const [query, setQuery] = useState({ summary: {}, rows: [], returned: 0, total_matching: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pinningKey, setPinningKey] = useState("");

  const loadReferenceData = async () => {
    const [accountRows, platformRows] = await Promise.all([
      apiGet("/accounts"),
      apiGet("/publish/platforms"),
    ]);
    setAccounts(accountRows || []);
    setPlatforms(platformRows || []);
  };

  const loadQuery = async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (accountId) params.set("account_id", accountId);
      if (platform) params.set("platform", platform);
      params.set("scope", scope);
      params.set("sort_by", sortBy);
      params.set("sort_direction", "desc");
      params.set("limit", "200");
      const result = await apiGet(`/data/query?${params.toString()}`);
      setQuery(result || { summary: {}, rows: [] });
    } catch (requestError) {
      setError(requestError.message || "数据中心读取失败");
      setQuery({ summary: {}, rows: [], returned: 0, total_matching: 0 });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReferenceData().catch((referenceError) => setError(referenceError.message));
  }, []);

  useEffect(() => {
    loadQuery();
  }, [accountId, platform, scope, sortBy]);

  const accountMap = useMemo(
    () => Object.fromEntries(accounts.map((account) => [String(account.id), account])),
    [accounts]
  );

  const reportPeriod = useMemo(() => {
    const periods = (query.rows || [])
      .filter((row) => row.period_start && row.period_end)
      .map((row) => `${row.period_start} → ${row.period_end}`);
    const unique = [...new Set(periods)];
    if (unique.length === 1) return unique[0];
    if (unique.length > 1) return "包含多个同步周期";
    return scope === "historical" ? "历史汇总" : "等待下一次 Analytics 同步记录周期";
  }, [query.rows, scope]);

  const summary = query.summary || {};

  const togglePin = async (row) => {
    if (row.account_id == null || !row.platform || !row.platform_video_id) return;
    const key = `${row.account_id}:${row.platform}:${row.platform_video_id}`;
    setPinningKey(key);
    setError("");
    try {
      await apiPost(
        `/data/tracking/account/${encodeURIComponent(row.account_id)}/pin/${encodeURIComponent(row.platform_video_id)}`,
        {
          platform: row.platform,
          pinned: !row.pinned,
          active_limit: 10,
        }
      );
      await loadQuery();
    } catch (pinError) {
      setError(pinError.message || "持续跟踪状态更新失败");
    } finally {
      setPinningKey("");
    }
  };

  return (
    <>
      <div className="page-heading compact dc-heading">
        <div>
          <span className="eyebrow">DATA CENTER</span>
          <h1>数据中心</h1>
          <p>默认观察每个绑定账号最新 10 条内容；旧内容退出主动同步后保留历史结果，不删除。</p>
        </div>
        <div className="dc-period">
          <span>当前数据周期</span>
          <strong>{reportPeriod}</strong>
        </div>
      </div>

      <section className="dc-filter-bar">
        <label>
          <span>平台</span>
          <select value={platform} onChange={(event) => setPlatform(event.target.value)}>
            <option value="">全部平台</option>
            {platforms.map((item) => (
              <option key={item.platform} value={String(item.platform || "").toLowerCase()}>
                {platformLabel(item.platform)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>账号</span>
          <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
            <option value="">全部账号</option>
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {platformLabel(account.platform)} · {account.account_name || `Account #${account.id}`}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>跟踪范围</span>
          <select value={scope} onChange={(event) => setScope(event.target.value)}>
            <option value="active">ACTIVE · 最新 10 条</option>
            <option value="historical">HISTORICAL · 历史结果</option>
            <option value="all">全部</option>
          </select>
        </label>
        <label>
          <span>排序</span>
          <select value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
            <option value="views">观看量</option>
            <option value="watch_time">总观看时长</option>
            <option value="average_view_percentage">平均观看比例</option>
            <option value="published_at">发布时间</option>
            <option value="referral_clicks">Referral Clicks</option>
            <option value="conversions">Conversions</option>
            <option value="conversion_value">Conversion Value</option>
          </select>
        </label>
        <button className="secondary-button dc-refresh" onClick={loadQuery} disabled={loading}>
          {loading ? "读取中…" : "刷新本地数据"}
        </button>
      </section>

      {error ? <div className="notice dc-error">{error}</div> : null}

      <div className="dc-metric-grid">
        <MetricCard label="总观看量" value={formatNumber(summary.total_views)} hint={`${summary.content_count || 0} 条内容`} />
        <MetricCard label="总观看时长" value={formatSeconds(summary.total_watch_time)} />
        <MetricCard
          label="平均观看比例"
          value={formatPercent(summary.average_view_percentage)}
          hint="按观看量加权；Shorts 循环可能超过 100%"
        />
        <MetricCard label="Referral Clicks" value={formatNumber(summary.referral_clicks)} hint="来自 OS 归因事件" />
        <MetricCard label="Conversions" value={formatNumber(summary.conversions)} />
        <MetricCard label="Conversion Value" value={formatMoney(summary.conversion_value)} />
      </div>

      <section className="panel dc-table-panel">
        <div className="panel-header dc-table-header">
          <div>
            <span className="section-kicker">CONTENT PERFORMANCE</span>
            <h2>内容表现</h2>
          </div>
          <span className="muted">
            显示 {query.returned || 0} / {query.total_matching || 0} 条
          </span>
        </div>

        {loading ? (
          <div className="dc-loading">正在读取本地 Data Center…</div>
        ) : (query.rows || []).length === 0 ? (
          <div className="dc-empty">
            <strong>当前范围还没有可展示的数据</strong>
            <span>先在“平台账号”同步内容和 Analytics；新版本会把最新 10 条建立为 ACTIVE 跟踪集。</span>
          </div>
        ) : (
          <div className="table-wrap dc-table-wrap">
            <table className="dc-table">
              <thead>
                <tr>
                  <th>内容</th>
                  <th>平台 / 账号</th>
                  <th>状态</th>
                  <th>观看</th>
                  <th>总观看时长</th>
                  <th>平均观看</th>
                  <th>平均观看比例</th>
                  <th>赞</th>
                  <th>评论数</th>
                  <th>分享</th>
                  <th>Referral</th>
                  <th>转化</th>
                  <th>转化价值</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {(query.rows || []).map((row) => {
                  const account = accountMap[String(row.account_id)] || {};
                  const pinKey = `${row.account_id}:${row.platform}:${row.platform_video_id}`;
                  return (
                    <tr key={`${row.account_id}-${row.platform}-${row.platform_video_id}`}>
                      <td className="dc-content-cell">
                        <strong title={row.title}>{row.title || row.platform_video_id || "—"}</strong>
                        <span>{row.platform_video_id || "—"}</span>
                        <small>{formatDate(row.published_at)}</small>
                      </td>
                      <td className="dc-platform-cell">
                        <strong>{platformLabel(row.platform)}</strong>
                        <span>{account.account_name || (row.account_id != null ? `Account #${row.account_id}` : "Legacy")}</span>
                      </td>
                      <td><TrackingBadge state={row.tracking_state} pinned={row.pinned} /></td>
                      <td className="dc-number">{formatNumber(row.views)}</td>
                      <td>{formatSeconds(row.watch_time)}</td>
                      <td>{formatDuration(row.average_view_duration)}</td>
                      <td className="dc-number">{formatPercent(row.average_view_percentage)}</td>
                      <td className="dc-number">{formatNumber(row.likes)}</td>
                      <td className="dc-number">{formatNumber(row.comments)}</td>
                      <td className="dc-number">{formatNumber(row.shares)}</td>
                      <td className="dc-number">{formatNumber(row.referral_clicks)}</td>
                      <td className="dc-number">{formatNumber(row.conversions)}</td>
                      <td className="dc-number">{formatMoney(row.conversion_value)}</td>
                      <td className="dc-action-cell">
                        {row.account_id != null && row.tracking_state !== "untracked" ? (
                          <button
                            className="dc-pin-button"
                            onClick={() => togglePin(row)}
                            disabled={pinningKey === pinKey}
                            title={row.pinned ? "取消持续跟踪" : "即使退出最新 10 条，也继续同步这条内容"}
                          >
                            {row.pinned ? "取消跟踪" : "持续跟踪"}
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

      <div className="dc-footnote">
        <strong>数据规则：</strong>
        ACTIVE 只同步最新 10 条 + 你手动持续跟踪的内容；HISTORICAL 不再频繁请求平台，但保留其最后表现和转化结果。评论这里只显示数量，不读取评论正文。
      </div>
    </>
  );
}
