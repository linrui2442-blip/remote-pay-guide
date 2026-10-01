import React, { useState, useRef } from "react";
import { generateContentPlan, getDirectedRequestStatus, prepareStrictSnapshot, updateContentPlan, evaluateContentPlanPolicy, getContentPlanEffective, getContentPlan } from "../api";

const REQUEST_KEY = 'remote-pay-guide:directed-request:v1';
const canonical = value => JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);
function restoreRequest() {
  try {
    const raw = sessionStorage.getItem(REQUEST_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw);
    if (!saved.replay_token || ((!saved.payload || saved.fingerprint !== canonical(saved.payload))
      && !(saved.status === 'READY' && saved.payload === null && saved.prior_request))
      || !['READY', 'SUBMITTING', 'UNKNOWN_OR_RETRYABLE', 'UNKNOWN_REQUIRES_RECONCILIATION', 'COMPLETED'].includes(saved.status)
      || (saved.status === 'COMPLETED' && !saved.plan_id)) throw Error('Invalid saved request');
    return {...saved, status: ['SUBMITTING', 'UNKNOWN_OR_RETRYABLE'].includes(saved.status)
      ? 'UNKNOWN_REQUIRES_RECONCILIATION' : saved.status};
  } catch { return {status: 'STORAGE_BLOCKED'}; }
}

export const EDITABLE_PLAN_FIELDS = ['hook', 'script', 'cta', 'title', 'description', 'visual_direction', 'production_notes'];

export default function IntelligenceCenter({ accounts = [] }) {
  const [request, setRequest] = useState(restoreRequest);
  const active = useRef(request);
  const inFlight = useRef(false);
  const persist = next => { sessionStorage.setItem(REQUEST_KEY, JSON.stringify(next)); active.current = next; setRequest(next); };
  const [accountId, setAccountId] = useState(accounts[0]?.id || "");
  const [platform, setPlatform] = useState("youtube");
  const [start, setStart] = useState(""); const [end, setEnd] = useState("");
  const [snapshot, setSnapshot] = useState(request?.payload ? {id: request.payload.snapshot_id} : null);
  const [brief, setBrief] = useState(request?.payload?.human_brief || ""); const [audience, setAudience] = useState(request?.payload?.human_constraints?.target_audience || "");
  const [plan, setPlan] = useState(null); const [runtime, setRuntime] = useState(null);
  const [policy, setPolicy] = useState(null); const [effective, setEffective] = useState(null);
  const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const clearContext = () => { setSnapshot(null); };
  const prepare = async () => {
    setBusy(true); setMessage("");
    try { const result = await prepareStrictSnapshot({ account_id: Number(accountId), platform, start_date: start, end_date: end }); setSnapshot(result.snapshot); }
    catch (e) { setMessage(e.message); } finally { setBusy(false); }
  };
  const generate = async () => {
    if (inFlight.current || ['COMPLETED', 'STORAGE_BLOCKED', 'UNKNOWN_REQUIRES_RECONCILIATION'].includes(active.current?.status)) return;
    inFlight.current = true; setBusy(true); setMessage("");
    try {
      if (!snapshot?.id || !brief.trim()) throw Error('Snapshot and brief required');
      const payload = {snapshot_id: snapshot.id, human_brief: brief.trim(), human_constraints: audience.trim() ? {target_audience: audience.trim(), locked_fields: ['target_audience']} : {}};
      const fingerprint = canonical(payload);
      if (active.current?.fingerprint && active.current.fingerprint !== fingerprint) throw Error('Input changed. Use New Creative Request explicitly.');
      const current = active.current ? {...active.current, payload, fingerprint} : {replay_token: crypto.randomUUID(), payload, fingerprint, status: 'READY'};
      persist({...current, status: 'SUBMITTING'});
      const created = await generateContentPlan(current.payload.snapshot_id, {request_id: current.replay_token, human_brief: current.payload.human_brief, human_constraints: current.payload.human_constraints, duplicate_risk_ack: Boolean(current.duplicate_risk_ack)});
      const {prior_request: _prior, ...completed} = current;
      persist({...completed, status: 'COMPLETED', plan_id: created.plan.id});
      setPlan(created.plan); setRuntime(created.runtime); setPolicy(created.policy); setEffective(created.effective);
      setMessage(created.policy_error || "ContentPlan saved. Stopped at PolicyDecision; no task created.");
    } catch (e) {
      if (active.current?.status === 'SUBMITTING') {
        const reconciliationRequired = /DIRECTED_RECONCILIATION_REQUIRED/.test(e.message);
        const riskAckRequired = /DIRECTED_DUPLICATE_RISK_ACK_REQUIRED/.test(e.message);
        try {
          if (reconciliationRequired && active.current.prior_request) persist(active.current.prior_request);
          else if (riskAckRequired) {
            const accepted = window.confirm('The original provider outcome remains unknown. A new request could duplicate content or cost. Confirm risk before submitting this same new request?');
            persist({...active.current, status: 'READY', duplicate_risk_ack: accepted});
          } else persist({...active.current, status: 'UNKNOWN_REQUIRES_RECONCILIATION'});
        } catch { /* Preserve the durable token when storage fails. */ }
      }
      setMessage(`${e.message}. No automatic retry.`);
    } finally { inFlight.current = false; setBusy(false); }
  };
  const newRequest = async () => {
    if (inFlight.current || active.current?.status === 'STORAGE_BLOCKED') return;
    inFlight.current = true; setBusy(true);
    try {
      let duplicateRiskAck = false;
      if (active.current?.replay_token && active.current?.payload?.snapshot_id) {
        const status = await getDirectedRequestStatus(active.current.payload.snapshot_id, active.current.replay_token);
        if (!status.can_create_new_request) {
          setMessage('Generation outcome unknown. Reconciliation is required before another request for this snapshot.');
          return;
        }
        if (status.requires_duplicate_risk_ack) {
          duplicateRiskAck = window.confirm('The original provider outcome remains unknown. A new request could duplicate content or cost. Start a separate creative request?');
          if (!duplicateRiskAck) return;
        }
      }
      const prior = active.current;
      const next = {replay_token: crypto.randomUUID(), payload: null, fingerprint: null, status: 'READY',
        duplicate_risk_ack: duplicateRiskAck, prior_request: prior};
      // Keep the prior identity in session storage until the new boundary succeeds.
      persist(next);
      setPlan(null); setRuntime(null); setPolicy(null); setEffective(null); setDirty(false); setBrief(''); setAudience('');
      setMessage('New creative request prepared; no generation has been sent.');
    } catch (e) { setMessage(e.message || 'Cannot establish a new request.'); }
    finally { inFlight.current = false; setBusy(false); }
  };
  const restorePlan = async () => {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true);
    try { setPlan(await getContentPlan(active.current.plan_id)); setPolicy(null); setEffective(null); }
    catch (e) { setMessage(e.message); } finally { inFlight.current = false; setBusy(false); }
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
      <p>Request state: {request?.status || (snapshot && brief.trim() ? 'READY' : 'DRAFT')}</p>
      {request?.status === 'UNKNOWN_REQUIRES_RECONCILIATION' && <p>Generation outcome unknown. This request cannot be retried automatically. Reconciliation is required before another request for this snapshot.</p>}
      <button disabled={busy || ['COMPLETED', 'STORAGE_BLOCKED', 'UNKNOWN_REQUIRES_RECONCILIATION'].includes(request?.status) || !snapshot || !brief.trim()} onClick={generate}>Generate ContentPlan</button>
      {request?.status === 'COMPLETED' && <button disabled={busy} onClick={restorePlan}>Restore completed plan</button>}
      <button disabled={busy || request?.status === 'STORAGE_BLOCKED'} onClick={newRequest}>New Creative Request</button>
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
