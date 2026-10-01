import React, { useState } from "react";
import { generateContentPlan, prepareStrictSnapshot, updateContentPlan, evaluateContentPlanPolicy, getContentPlanEffective } from "../api";

export const EDITABLE_PLAN_FIELDS = ['hook', 'script', 'cta', 'title', 'description', 'visual_direction', 'production_notes'];

export default function IntelligenceCenter({ accounts = [] }) {
  const [accountId, setAccountId] = useState(accounts[0]?.id || "");
  const [platform, setPlatform] = useState("youtube");
  const [start, setStart] = useState(""); const [end, setEnd] = useState("");
  const [snapshot, setSnapshot] = useState(null);
  const [brief, setBrief] = useState(""); const [audience, setAudience] = useState("");
  const [plan, setPlan] = useState(null); const [runtime, setRuntime] = useState(null);
  const [policy, setPolicy] = useState(null); const [effective, setEffective] = useState(null);
  const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  // Uncertain generation outcomes never trigger an automatic paid retry.
  const [attempted, setAttempted] = useState(false);
  const clearContext = () => { setSnapshot(null); };
  const prepare = async () => {
    setBusy(true); setMessage("");
    try { const result = await prepareStrictSnapshot({ account_id: Number(accountId), platform, start_date: start, end_date: end }); setSnapshot(result.snapshot); }
    catch (e) { setMessage(e.message); } finally { setBusy(false); }
  };
  const generate = async () => {
    setBusy(true); setAttempted(true); setMessage("");
    try {
      const created = await generateContentPlan(snapshot.id, { request_id: crypto.randomUUID(), human_brief: brief, human_constraints: audience ? {target_audience: audience, locked_fields: ['target_audience']} : {} });
      setPlan(created.plan); setRuntime(created.runtime); setPolicy(created.policy); setEffective(created.effective);
      setMessage(created.policy_error || "ContentPlan saved. Stopped at PolicyDecision; no task created.");
    } catch (e) { setMessage(`${e.message}. No automatic retry: inspect existing plans before a new request.`); }
    finally { setBusy(false); }
  };
  const edit = async (field, value) => {
    setBusy(true); setPolicy(null); setEffective(null);
    try { const updated = await updateContentPlan(plan.id, { [field]: value }); setPlan(updated); setDirty(false); setMessage("Revision saved. Policy reevaluation required."); }
    catch (e) { setMessage(e.message); } finally { setBusy(false); }
  };
  const evaluate = async () => {
    setBusy(true); setPolicy(null); setEffective(null);
    try { setPolicy(await evaluateContentPlanPolicy(plan.id)); setEffective(await getContentPlanEffective(plan.id)); }
    catch (e) { setMessage(e.message); } finally { setBusy(false); }
  };
  return <>
    <div className="page-heading compact"><h1>AI 智能 · Directed Content</h1><p>Strict snapshot → ContentPlan → G3。此页面不批准、不创建任务、不执行生产或发布。</p></div>
    <section className="panel"><div className="settings-form">
      <label>账号<select value={accountId} onChange={e => { setAccountId(e.target.value); clearContext(); }}>{accounts.map(a => <option key={a.id} value={a.id}>#{a.id} {a.name || a.platform}</option>)}</select></label>
      <label>平台<select value={platform} onChange={e => { setPlatform(e.target.value); clearContext(); }}><option value="youtube">YouTube</option><option value="instagram">Instagram</option><option value="facebook">Facebook</option></select></label>
      <label>Window start<input type="date" value={start} onChange={e => { setStart(e.target.value); clearContext(); }} /></label>
      <label>Window end<input type="date" value={end} onChange={e => { setEnd(e.target.value); clearContext(); }} /></label>
      <button disabled={busy || !accountId || !start || !end} onClick={prepare}>Prepare strict snapshot</button>
      {snapshot && <p>Snapshot #{snapshot.id} · {snapshot.content_id}</p>}
      <label>你想创作什么内容？<textarea aria-label="human_brief" value={brief} onChange={e => setBrief(e.target.value)} /></label>
      <label>目标受众（可选）<input value={audience} onChange={e => setAudience(e.target.value)} /></label>
      <button disabled={busy || attempted || !snapshot || !brief.trim()} onClick={generate}>Generate ContentPlan</button>
    </div></section>
    {plan && <section className="panel"><h2>Preview / Edit · Revision {plan.revision}</h2>
      <p>Content ID: {plan.plan.content_id}</p><p>Topic (read-only): {plan.plan.topic}</p>
      {EDITABLE_PLAN_FIELDS.map(field => <label className="setting-field" key={field}>{field}<textarea disabled={busy} value={plan.plan[field] || ''} onChange={e => { setDirty(true); setPolicy(null); setEffective(null); setPlan({...plan, plan: {...plan.plan, [field]: e.target.value}}); }} onBlur={e => edit(field, e.target.value)} /></label>)}
      <p>Novelty: {plan.plan.novelty_status}</p>
      <button disabled={busy || dirty} onClick={evaluate}>Evaluate current revision policy</button>
      <p>RAW POLICY: {policy?.decision || 'UNEVALUATED / STALE'}</p>
      <p>EFFECTIVE AUTHORIZATION: {effective?.autonomous_continuation_allowed ? 'Allowed by controls; this page does not execute' : 'NOT EXECUTABLE'}</p>
      <p>{effective?.control_reason_codes?.join(', ')}</p>
      <p>Provider: {plan.plan.generation_provider} · Runtime ready: {String(runtime?.runtime_ready ?? 'replay')}</p>
    </section>}
    {message && <p role="status">{message}</p>}
  </>;
}
