import React, { useState } from "react";
import { getAccountIntelligence, materializeIntelligenceTask, refreshAccountIntelligence } from "../api";

export default function IntelligenceCenter({ accounts = [] }) {
  const [accountId, setAccountId] = useState(accounts[0]?.id || "");
  const [platform, setPlatform] = useState("youtube");
  const [snapshot, setSnapshot] = useState(null);
  const [task, setTask] = useState(null);
  const [busy, setBusy] = useState(false);
  const refresh = async () => { setBusy(true); try { await refreshAccountIntelligence(accountId, platform); setSnapshot(await getAccountIntelligence(accountId, platform)); } finally { setBusy(false); } };
  const materialize = async () => setTask(await materializeIntelligenceTask(snapshot?.id || snapshot?.snapshot_id));
  const top = Array.isArray(snapshot) ? snapshot[0] : snapshot;
  const strategy = top?.strategy || {};
  return <>
    <div className="page-heading compact"><div><span className="eyebrow">INTELLIGENCE</span><h1>AI 智能</h1><p>从真实反馈生成建议；只有你的明确操作才会创建生产任务。</p></div></div>
    <section className="panel"><div className="settings-form">
      <label className="setting-field"><span>账号</span><select value={accountId} onChange={e=>setAccountId(e.target.value)}>{accounts.map(a=><option key={a.id} value={a.id}>#{a.id} {a.name || a.platform}</option>)}</select></label>
      <label className="setting-field"><span>平台</span><select value={platform} onChange={e=>setPlatform(e.target.value)}><option value="youtube">YouTube</option><option value="instagram">Instagram</option><option value="facebook">Facebook</option></select></label>
      <button className="primary-button" disabled={!accountId || busy} onClick={refresh}>{busy ? "分析中…" : "Refresh Intelligence"}</button>
    </div></section>
    {top && <section className="panel"><div className="panel-header"><div><span className="section-kicker">TOP RECOMMENDATION</span><h2>{top.content_id || top.video_id || "Recommendation"}</h2></div></div>
      <p>Platform: {top.platform || platform} · Performance: {top.performance_score ?? 0} · Priority: {top.priority_score ?? 0}</p>
      <p>Landing/intent: {top.intent_events ?? 0} · Referral clicks: {top.referral_clicks ?? 0} · Conversions: {top.conversions ?? 0} · Value: {top.conversion_value ?? 0}</p>
      <h3>{strategy.objective || top.objective || "Strategy"}</h3><p>{strategy.topic_direction || top.topic_direction}</p><p>{strategy.reasoning_summary || top.reasoning_summary}</p>
      <details><summary>Why this recommendation</summary><pre>{JSON.stringify({successful_patterns:top.successful_patterns||[], weak_patterns:top.weak_patterns||[], recommendations:top.recommendations||[]}, null, 2)}</pre></details>
      <button className="secondary-button" onClick={materialize}>创建生产任务</button><p className="muted">只创建 ProductionTask；不会生产，也不会发布。</p>
    </section>}
    {task && <section className="panel"><h2>ProductionTask #{task.production_task?.id || task.id}</h2><pre>{JSON.stringify(task.production_task?.execution || task.execution || {}, null, 2)}</pre></section>}
  </>;
}
