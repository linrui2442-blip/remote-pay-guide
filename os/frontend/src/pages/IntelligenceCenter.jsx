import React, { useState } from "react";
import { approveContentPlan, generateContentPlan, getAccountIntelligence, materializeContentPlan, refreshAccountIntelligence, updateContentPlan } from "../api";

export default function IntelligenceCenter({ accounts = [] }) {
  const [accountId, setAccountId] = useState(accounts[0]?.id || "");
  const [platform, setPlatform] = useState("youtube");
  const [snapshot, setSnapshot] = useState(null);
  const [task, setTask] = useState(null); const [plan, setPlan] = useState(null); const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = async () => { setBusy(true); try { await refreshAccountIntelligence(accountId, platform); setSnapshot(await getAccountIntelligence(accountId, platform)); } finally { setBusy(false); } };
  const generate = async () => { setBusy(true); try { const created = await generateContentPlan(top?.id || top?.snapshot_id || snapshot?.id); setPlan(created); setMessage("ContentPlan ready for review."); } finally { setBusy(false); } };
  const edit = async (field, value) => { const updated = await updateContentPlan(plan.id, { [field]: value }); setPlan(updated); setMessage(`Revision ${updated.revision} saved.`); };
  const approve = async () => { try { const approved = await approveContentPlan(plan.id); setPlan(approved); setMessage(`Approved revision ${approved.approved_revision}.`); } catch (error) { setMessage(error.message); } };
  const materialize = async () => { try { const created = await materializeContentPlan(plan.id); setTask(created); setMessage("Task created but not executed."); } catch (error) { setMessage(error.message); } };
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
      <button className="secondary-button" onClick={generate} disabled={busy}>Generate ContentPlan</button>
    </section>}
    {plan && <section className="panel"><div className="panel-header"><div><span className="section-kicker">CONTENT PLAN · REVISION {plan.revision}</span><h2>Preview / Edit</h2></div><span className={`status-pill ${String(plan.plan?.novelty_status || 'unverified').toLowerCase()}`}>{plan.plan?.novelty_status || 'UNVERIFIED'}</span></div>
      {['topic','hook','script','cta','title','description','visual_direction'].map((field) => <label className="setting-field" key={field}><span>{field}</span><textarea value={plan.plan?.[field] || ''} onChange={e=>setPlan({...plan,plan:{...plan.plan,[field]:e.target.value}})} onBlur={e=>edit(field,e.target.value)} /></label>)}
      <pre>{JSON.stringify(plan.plan?.production_spec || {}, null, 2)}</pre>
      {plan.plan?.novelty_status === 'BLOCK' && <p role="alert">Blocked: this plan cannot be approved.</p>}
      {plan.plan?.novelty_status === 'WARN' && <p role="alert">Warning: review novelty evidence before approving.</p>}
      <button className="secondary-button" onClick={approve} disabled={plan.plan?.novelty_status === 'BLOCK' || plan.status === 'approved' || plan.status === 'materialized'}>Approve</button>
      <button className="primary-button" onClick={materialize} disabled={plan.status !== 'approved'}>Create ProductionTask</button><p className="muted">Task created but not executed.</p>{message && <p role="status">{message}</p>}
    </section>}
    {task && <section className="panel"><h2>ProductionTask #{task.production_task?.id || task.id}</h2><pre>{JSON.stringify(task.production_task?.execution || task.execution || {}, null, 2)}</pre></section>}
  </>;
}
