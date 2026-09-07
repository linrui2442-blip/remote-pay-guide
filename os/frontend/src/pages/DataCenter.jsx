import React, { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost, getDataCenterQuery } from "../api";

const PLATFORM_LABELS = {
  youtube: "YouTube",
  facebook: "Facebook",
  instagram: "Instagram",
  tiktok: "TikTok",
};

const STRATEGY_LABELS = {
  scale_conversion_winner: "放大转化赢家",
  iterate_intent_winner: "优化 Referral 意图赢家",
  improve_intent_to_referral: "强化意图 → Referral",
  scale_traffic_winner: "放大流量赢家",
  revise_underperformer: "重做低表现内容",
  iterate: "控制变量迭代",
};

const TREND_METRICS = [
  ["views", "观看量"],
  ["watch_time", "观看时长"],
  ["likes", "赞"],
  ["comments", "评论数"],
  ["shares", "分享"],
];

function platformLabel(name) {
  const key = String(name || "").toLowerCase();
  if (PLATFORM_LABELS[key]) return PLATFORM_LABELS[key];
  return key ? key.charAt(0).toUpperCase() + key.slice(1) : "Unknown";
}

function strategyLabel(name) {
  const key = String(name || "").toLowerCase();
  return STRATEGY_LABELS[key] || key || "待分析";
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

function formatPeriod(start, end) {
  if (!start && !end) return "—";
  if (start === end) return start || end;
  return `${start || "?"} → ${end || "?"}`;
}

function formatSignedNumber(value) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const number = Number(value);
  if (number > 0) return `+${number.toLocaleString()}`;
  return number.toLocaleString();
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

function formatMetricValue(metric, value) {
  if (value == null || !Number.isFinite(Number(value))) return "Unavailable";
  return metric === "watch_time" ? formatSeconds(value) : formatNumber(value);
}

function ComparisonGrid({ comparison }) {
  const metrics = comparison?.metrics || {};
  return (
    <div className="dc-comparison-grid">
      {TREND_METRICS.map(([key, label]) => {
        const item = metrics[key] || {};
        return (
          <div className="dc-comparison-card" key={key}>
            <span>{label}</span>
            <strong>{formatMetricValue(key, item.current)}</strong>
            <small>上一周期 {formatMetricValue(key, item.previous)}</small>
            <small>
              变化 {formatSignedNumber(item.change)} · {item.change_percent == null ? "Unavailable" : formatPercent(item.change_percent)}
            </small>
          </div>
        );
      })}
    </div>
  );
}

function DailyTrend({ timeSeries, metric, onMetricChange }) {
  const points = timeSeries?.points || [];
  const values = points.map((point) => Number(point.metric_values?.[metric]));
  const finiteValues = values.filter(Number.isFinite);
  const maximum = Math.max(...finiteValues, 0);
  return (
    <section className="panel dc-v2-panel">
      <div className="panel-header dc-v2-header">
        <div><span className="section-kicker">DAILY TREND</span><h2>每日趋势</h2></div>
        <select value={metric} onChange={(event) => onMetricChange(event.target.value)}>
          {TREND_METRICS.map(([key, label]) => <option value={key} key={key}>{label}</option>)}
        </select>
      </div>
      {!timeSeries?.available ? (
        <div className="dc-trend-unavailable">当前周期缺少真实每日 Analytics 快照，无法生成可信趋势。</div>
      ) : (
        <div className="dc-trend" aria-label="Daily analytics trend">
          {points.map((point, index) => {
            const value = values[index];
            const height = Number.isFinite(value) && maximum > 0 ? Math.max(4, value / maximum * 100) : 0;
            return (
              <div className="dc-trend-column" key={point.date} title={`${point.date}: ${formatMetricValue(metric, value)}`}>
                <div className="dc-trend-track"><span style={{ height: `${height}%` }} /></div>
                <small>{point.date.slice(5)}</small>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

export default function DataCenter() {
  const [accounts, setAccounts] = useState([]);
  const [platforms, setPlatforms] = useState([]);
  const [accountId, setAccountId] = useState("");
  const [platform, setPlatform] = useState("");
  const [scope, setScope] = useState("active");
  const [sortBy, setSortBy] = useState("views");
  const [dateRange, setDateRange] = useState("28d");
  const [customStartDate, setCustomStartDate] = useState("");
  const [customEndDate, setCustomEndDate] = useState("");
  const [comparePreviousPeriod, setComparePreviousPeriod] = useState(false);
  const [trendMetric, setTrendMetric] = useState("views");
  const [query, setQuery] = useState({ summary: {}, rows: [], returned: 0, total_matching: 0 });
  const [accountMetrics, setAccountMetrics] = useState([]);
  const [intelligenceSnapshots, setIntelligenceSnapshots] = useState([]);
  const [loadingIntelligence, setLoadingIntelligence] = useState(false);
  const [materializingId, setMaterializingId] = useState(null);
  const [intelligenceMessage, setIntelligenceMessage] = useState("");
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

  const loadAccountMetrics = async () => {
    const params = new URLSearchParams();
    if (platform) params.set("platform", platform);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const path = accountId
      ? `/analytics/accounts/${encodeURIComponent(accountId)}/metrics/current${suffix}`
      : `/analytics/accounts/current${suffix}`;
    try {
      const snapshots = await apiGet(path);
      setAccountMetrics(snapshots || []);
    } catch (_) {
      setAccountMetrics([]);
    }
  };

  const loadIntelligence = async () => {
    if (!accounts.length) {
      setIntelligenceSnapshots([]);
      return;
    }

    setLoadingIntelligence(true);
    try {
      const targetAccounts = accounts.filter((account) => {
        if (accountId && String(account.id) !== String(accountId)) return false;
        if (platform && String(account.platform || "").toLowerCase() !== platform) return false;
        return true;
      });

      const batches = await Promise.all(
        targetAccounts.map(async (account) => {
          const params = new URLSearchParams();
          const accountPlatform = String(account.platform || "").toLowerCase();
          if (accountPlatform) params.set("platform", accountPlatform);
          params.set("limit", "100");
          try {
            return await apiGet(
              `/intelligence/feedback/account/${encodeURIComponent(account.id)}?${params.toString()}`
            );
          } catch (_) {
            return [];
          }
        })
      );

      const snapshots = batches
        .flat()
        .sort((a, b) => Number(b.priority_score || 0) - Number(a.priority_score || 0));
      setIntelligenceSnapshots(snapshots);
    } finally {
      setLoadingIntelligence(false);
    }
  };

  const loadQuery = async () => {
    setLoading(true);
    setError("");
    try {
      const useV2 = scope === "active";
      if (useV2 && dateRange === "custom" && (!customStartDate || !customEndDate)) {
        setLoading(false);
        return;
      }
      const result = await getDataCenterQuery({
        account_id: accountId,
        platform,
        scope,
        sort_by: sortBy,
        sort_direction: "desc",
        limit: 200,
        ...(useV2 ? {
          date_range: dateRange,
          start_date: dateRange === "custom" ? customStartDate : undefined,
          end_date: dateRange === "custom" ? customEndDate : undefined,
          compare_previous_period: comparePreviousPeriod && dateRange !== "lifetime",
          interval: "daily",
        } : {}),
      });
      setQuery(result || { summary: {}, rows: [] });
      await loadAccountMetrics();
    } catch (requestError) {
      setError(requestError.message || "数据中心读取失败");
      setQuery({ summary: {}, rows: [], returned: 0, total_matching: 0 });
      setAccountMetrics([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReferenceData().catch((referenceError) => setError(referenceError.message));
  }, []);

  useEffect(() => {
    loadQuery();
  }, [accountId, platform, scope, sortBy, dateRange, customStartDate, customEndDate, comparePreviousPeriod]);

  useEffect(() => {
    loadIntelligence();
  }, [accounts, accountId, platform]);

  const accountMap = useMemo(
    () => Object.fromEntries(accounts.map((account) => [String(account.id), account])),
    [accounts]
  );

  const reportPeriod = useMemo(() => {
    if (query.period) {
      return query.period.date_range === "lifetime"
        ? "Lifetime"
        : formatPeriod(query.period.start_date, query.period.end_date);
    }
    const periods = (query.rows || [])
      .filter((row) => row.period_start && row.period_end)
      .map((row) => `${row.period_start} → ${row.period_end}`);
    const unique = [...new Set(periods)];
    if (unique.length === 1) return unique[0];
    if (unique.length > 1) return "包含多个同步周期";
    return scope === "historical" ? "历史汇总" : "等待下一次 Analytics 同步记录周期";
  }, [query.period, query.rows, scope]);

  const summary = query.summary || {};
  const v2Enabled = scope === "active";

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

  const materializeStrategy = async (snapshot) => {
    setMaterializingId(snapshot.id);
    setIntelligenceMessage("");
    try {
      const result = await apiPost(
        `/intelligence/feedback/${encodeURIComponent(snapshot.id)}/materialize`,
        {}
      );
      const task = result.production_task || {};
      setIntelligenceMessage(
        result.created
          ? `已创建生产任务 #${task.id}，当前状态为 created；不会自动运行或发布。`
          : `生产任务 #${task.id} 已存在，未重复创建。`
      );
    } catch (materializeError) {
      setIntelligenceMessage(materializeError.message || "生产任务创建失败");
    } finally {
      setMaterializingId(null);
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
            <option value="archived">ARCHIVED · 已归档</option>
            <option value="all">全部</option>
          </select>
        </label>
        <label>
          <span>排序</span>
          <select value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
            <option value="views">观看量</option>
            <option value="watch_time">总观看时长</option>
            <option value="average_view_percentage">平均观看比例</option>
            <option value="likes">赞</option>
            <option value="comments">评论数</option>
            <option value="shares">分享</option>
            <option value="published_at">发布时间</option>
            <option value="referral_clicks">Referral Clicks</option>
            <option value="conversions">Conversions</option>
            <option value="conversion_value">Conversion Value</option>
          </select>
        </label>
        <label>
          <span>时间范围</span>
          <select
            value={dateRange}
            onChange={(event) => {
              const nextRange = event.target.value;
              setDateRange(nextRange);
              if (nextRange === "lifetime") setComparePreviousPeriod(false);
            }}
            disabled={!v2Enabled}
          >
            <option value="7d">7D</option>
            <option value="28d">28D</option>
            <option value="90d">90D</option>
            <option value="lifetime">Lifetime</option>
            <option value="custom">Custom</option>
          </select>
        </label>
        {v2Enabled && dateRange === "custom" ? (
          <>
            <label><span>开始日期</span><input type="date" value={customStartDate} onChange={(event) => setCustomStartDate(event.target.value)} /></label>
            <label><span>结束日期</span><input type="date" value={customEndDate} onChange={(event) => setCustomEndDate(event.target.value)} /></label>
          </>
        ) : null}
        <label className="dc-compare-toggle">
          <input
            type="checkbox"
            checked={comparePreviousPeriod}
            onChange={(event) => setComparePreviousPeriod(event.target.checked)}
            disabled={!v2Enabled || dateRange === "lifetime"}
          />
          <span>Compare previous period</span>
        </label>
        <button className="secondary-button dc-refresh" onClick={loadQuery} disabled={loading}>
          {loading ? "读取中…" : "刷新本地数据"}
        </button>
      </section>

      {!v2Enabled ? (
        <div className="notice dc-v2-notice">
          Historical / Archived / All 当前保留 Query V1 行为；Backend 第一阶段尚不支持可信的历史时间过滤，因此时间范围和周期比较已禁用。
        </div>
      ) : dateRange === "custom" && (!customStartDate || !customEndDate) ? (
        <div className="notice dc-v2-notice">请选择 Custom 的开始日期和结束日期；周期以 Backend 返回结果为准。</div>
      ) : null}

      {error ? <div className="notice dc-error">{error}</div> : null}

      <div className="dc-metric-grid">
        <MetricCard label="总观看量" value={formatNumber(summary.total_views)} hint={`${summary.content_count || 0} 条内容`} />
        <MetricCard label="总观看时长" value={formatSeconds(summary.total_watch_time)} />
        <MetricCard
          label="平均观看比例"
          value={formatPercent(summary.average_view_percentage)}
          hint="按观看量加权；Shorts 循环可能超过 100%"
        />
        <MetricCard label="赞" value={formatNumber(summary.likes)} />
        <MetricCard label="评论数" value={formatNumber(summary.comments)} hint="仅数量，不读取评论正文" />
        <MetricCard label="分享" value={formatNumber(summary.shares)} />
        <MetricCard label="Referral Clicks" value={formatNumber(summary.referral_clicks)} hint="来自 OS 归因事件" />
        <MetricCard label="Conversions" value={formatNumber(summary.conversions)} />
        <MetricCard label="Conversion Value" value={formatMoney(summary.conversion_value)} />
      </div>

      {v2Enabled && query.query_version === "v2" ? (
        <>
          {comparePreviousPeriod ? (
            <section className="panel dc-v2-panel">
              <div className="panel-header dc-v2-header">
                <div>
                  <span className="section-kicker">PERIOD COMPARISON</span>
                  <h2>上一周期对比</h2>
                </div>
                <span className="muted">{formatPeriod(query.comparison?.period?.start_date, query.comparison?.period?.end_date)}</span>
              </div>
              {query.comparison ? <ComparisonGrid comparison={query.comparison} /> : <div className="dc-trend-unavailable">Comparison unavailable</div>}
            </section>
          ) : null}

          <DailyTrend timeSeries={query.time_series} metric={trendMetric} onMetricChange={setTrendMetric} />

          <div className="dc-semantics-note">
            周期汇总优先使用精确窗口的最新快照；没有精确窗口时只汇总去重后的真实单日快照。每日趋势只使用真实单日 Analytics 快照，不会把多日汇总平均拆分或插值。
          </div>
        </>
      ) : null}

      <section className="panel dc-table-panel">
        <div className="panel-header dc-table-header">
          <div>
            <span className="section-kicker">AI INTELLIGENCE</span>
            <h2>下一轮生产策略</h2>
          </div>
          <span className="muted">
            {loadingIntelligence ? "读取中…" : `${intelligenceSnapshots.length} 条最新策略`}
          </span>
        </div>

        {intelligenceMessage ? <div className="notice">{intelligenceMessage}</div> : null}

        {loadingIntelligence ? (
          <div className="dc-loading">正在读取 Intelligence 策略快照…</div>
        ) : intelligenceSnapshots.length === 0 ? (
          <div className="dc-empty">
            <strong>还没有 Intelligence 策略快照</strong>
            <span>在“平台账号”执行“同步全部”后，Analytics 会自动进入 Data Center，再生成下一轮策略建议；不会自动生产或发布。</span>
          </div>
        ) : (
          <div className="table-wrap dc-table-wrap">
            <table className="dc-table">
              <thead>
                <tr>
                  <th>内容</th>
                  <th>平台 / 账号</th>
                  <th>策略</th>
                  <th>评分</th>
                  <th>业务信号</th>
                  <th>建议</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {intelligenceSnapshots.map((snapshot) => {
                  const account = accountMap[String(snapshot.account_id)] || {};
                  const feedback = snapshot.feedback || {};
                  const strategy = snapshot.strategy || {};
                  const recommendation = feedback.recommendations?.[0] || strategy.objective || "—";
                  return (
                    <tr key={`intelligence-${snapshot.id}`}>
                      <td className="dc-content-cell">
                        <strong>{snapshot.content_id || snapshot.platform_video_id || "—"}</strong>
                        <span>{snapshot.platform_video_id || "—"}</span>
                      </td>
                      <td className="dc-platform-cell">
                        <strong>{platformLabel(snapshot.platform)}</strong>
                        <span>{account.account_name || `Account #${snapshot.account_id}`}</span>
                      </td>
                      <td>
                        <strong>{strategyLabel(snapshot.strategy_type)}</strong>
                        <div className="muted">{strategy.reasoning_summary || "基于当前 Data Center 信号"}</div>
                      </td>
                      <td className="dc-number">{formatNumber(snapshot.performance_score)}</td>
                      <td>
                        <div>Intent {formatNumber(feedback.intent_events)}</div>
                        <div>Referral {formatNumber(feedback.referral_clicks)}</div>
                        <div>Conversion {formatNumber(feedback.conversions)}</div>
                        <div>Value {formatMoney(feedback.conversion_value)}</div>
                      </td>
                      <td title={recommendation}>{recommendation}</td>
                      <td className="dc-action-cell">
                        <button
                          className="secondary-button"
                          onClick={() => materializeStrategy(snapshot)}
                          disabled={materializingId === snapshot.id}
                          title="只创建 ProductionTask，不自动运行、不发布"
                        >
                          {materializingId === snapshot.id ? "创建中…" : "创建下一轮生产任务"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel dc-table-panel">
        <div className="panel-header dc-table-header">
          <div>
            <span className="section-kicker">ACCOUNT / CHANNEL PERFORMANCE</span>
            <h2>账号级 Analytics</h2>
          </div>
          <span className="muted">{accountMetrics.length} 个最新账号快照</span>
        </div>

        {accountMetrics.length === 0 ? (
          <div className="dc-empty">
            <strong>当前筛选范围还没有账号级 Analytics</strong>
            <span>在“平台账号”点击“同步全部”后，支持账号级 Analytics 的平台会在这里留下最新快照。</span>
          </div>
        ) : (
          <div className="table-wrap dc-table-wrap">
            <table className="dc-table">
              <thead>
                <tr>
                  <th>平台 / 账号</th>
                  <th>周期</th>
                  <th>观看</th>
                  <th>总观看时长</th>
                  <th>平均观看</th>
                  <th>平均观看比例</th>
                  <th>赞</th>
                  <th>评论数</th>
                  <th>分享</th>
                  <th>订阅净增</th>
                </tr>
              </thead>
              <tbody>
                {accountMetrics.map((snapshot) => {
                  const metrics = snapshot.metrics || {};
                  const account = accountMap[String(snapshot.account_id)] || {};
                  const hasSubscribers = metrics.subscribers_gained != null || metrics.subscribers_lost != null;
                  const subscriberNet = hasSubscribers
                    ? Number(metrics.subscribers_gained || 0) - Number(metrics.subscribers_lost || 0)
                    : null;
                  return (
                    <tr key={`${snapshot.account_id}-${snapshot.platform}-${snapshot.id}`}>
                      <td className="dc-platform-cell">
                        <strong>{platformLabel(snapshot.platform)}</strong>
                        <span>{account.account_name || `Account #${snapshot.account_id}`}</span>
                      </td>
                      <td>{formatPeriod(snapshot.period_start, snapshot.period_end)}</td>
                      <td className="dc-number">{formatNumber(metrics.views)}</td>
                      <td>{formatSeconds(metrics.watch_time)}</td>
                      <td>{formatDuration(metrics.average_view_duration)}</td>
                      <td className="dc-number">{formatPercent(metrics.average_view_percentage ?? metrics.retention)}</td>
                      <td className="dc-number">{formatNumber(metrics.likes)}</td>
                      <td className="dc-number">{formatNumber(metrics.comments)}</td>
                      <td className="dc-number">{formatNumber(metrics.shares)}</td>
                      <td className="dc-number">{formatSignedNumber(subscriberNet)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

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
            <span>先在“平台账号”执行“同步全部”；新版本会把最新 10 条建立为 ACTIVE 跟踪集。</span>
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
        ACTIVE 只同步最新 10 条 + 你手动持续跟踪的内容；HISTORICAL 不再频繁请求平台，但保留其最后表现和转化结果。评论这里只显示数量，不读取评论正文。Intelligence 同步只生成策略快照，只有点击“创建下一轮生产任务”才会创建任务，而且不会自动运行或发布。
      </div>
    </>
  );
}
