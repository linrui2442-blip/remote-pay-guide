import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { transformWithOxc } from 'vite';
import * as api from '../src/api.js';

const page = fs.readFileSync(new URL('../src/pages/IntelligenceCenter.jsx', import.meta.url), 'utf8');
const calls = [];
const record = {id: 42, revision: 1, status: 'preview', plan: {content_id: 'directed-offline', topic: 'Read-only topic', hook: 'Check deposit history', novelty_status: 'PASS', generation_provider: 'llm'}};
const originalFetch = globalThis.fetch;
globalThis.fetch = async (url, options = {}) => {
  const body = options.body ? JSON.parse(options.body) : null;
  calls.push({url, method: options.method || 'GET', body});
  let payload;
  if (url.endsWith('/feedback/prepare')) payload = {snapshot: {id: 7, content_id: 'source'}};
  else if (url.endsWith('/content-plan')) payload = {plan: record, runtime: {runtime_ready: true}, policy: {decision: 'AUTO'}, effective: {autonomous_continuation_allowed: false, control_reason_codes: ['KILL_SWITCH_ACTIVE', 'AUTONOMY_DISABLED']}};
  else if (options.method === 'PATCH') { assert.deepEqual(Object.keys(body), ['hook']); payload = {...record, revision: 2, plan: {...record.plan, ...body, novelty_status: 'unverified'}}; }
  else if (url.endsWith('/policy/evaluate')) payload = {decision: 'REVIEW'};
  else if (url.endsWith('/policy/effective')) payload = {autonomous_continuation_allowed: false};
  else throw Error('UNEXPECTED_FETCH ' + url);
  return {ok: true, json: async () => payload};
};

try {
  // Compile the actual JSX with the already installed Vite transformer. Hook
  // harness retains real component event handlers, real API wrappers and fetch.
  const states = []; let cursor = 0;
  const useState = initial => { const i = cursor++; if (!(i in states)) states[i] = initial; return [states[i], value => {states[i] = typeof value === 'function' ? value(states[i]) : value;}]; };
  const React = {Fragment: 'fragment', createElement: (type, props, ...children) => ({type, props: props || {}, children: children.flat(Infinity)})};
  const stripped = page.replace(/^import .*;\r?\n/gm, '').replace('export const ', 'const ').replace('export default function ', 'function ');
  const compiled = await transformWithOxc(stripped, 'IntelligenceCenter.jsx', {jsx: {runtime: 'classic'}});
  const context = vm.createContext({React, useState, ...api, crypto: globalThis.crypto});
  const Component = vm.runInContext(compiled.code + '\nIntelligenceCenter;', context);
  let tree;
  const render = () => { cursor = 0; tree = Component({accounts: [{id: 1, platform: 'youtube'}]}); };
  const walk = node => !node || typeof node !== 'object' ? [] : [node, ...node.children.flatMap(walk)];
  const nodes = () => walk(tree);
  const text = node => typeof node === 'string' || typeof node === 'number' ? String(node) : node?.children?.map(text).join('') || '';
  const button = label => nodes().find(n => n.type === 'button' && text(n) === label);
  render();
  const dates = nodes().filter(n => n.type === 'input' && n.props.type === 'date');
  dates[0].props.onChange({target: {value: '2026-09-01'}}); dates[1].props.onChange({target: {value: '2026-09-20'}}); render();
  await button('Prepare strict snapshot').props.onClick(); render();
  const brief = nodes().find(n => n.props['aria-label'] === 'human_brief'); assert(brief);
  brief.props.onChange({target: {value: 'Help a freelancer verify payment.'}});
  nodes().find(n => n.type === 'input' && !n.props.type).props.onChange({target: {value: 'Freelancers'}}); render();
  assert.equal(button('Generate ContentPlan').props.disabled, false);
  await button('Generate ContentPlan').props.onClick(); render();
  const sent = calls.find(c => c.url.endsWith('/content-plan'));
  assert.equal(sent.body.human_brief, 'Help a freelancer verify payment.');
  assert.equal(sent.body.human_constraints.target_audience, 'Freelancers');
  assert.match(sent.body.request_id, /^[0-9a-f-]{36}$/);
  assert(text(tree).includes('directed-offline')); assert(text(tree).includes('Read-only topic'));
  assert(text(tree).includes('RAW POLICY: AUTO')); assert(text(tree).includes('EFFECTIVE AUTHORIZATION: NOT EXECUTABLE'));
  assert.equal(nodes().filter(n => n.type === 'textarea' && n.props.value === 'Read-only topic').length, 0);
  const hook = nodes().find(n => n.type === 'textarea' && n.props.value === 'Check deposit history'); assert(hook);
  hook.props.onChange({target: {value: 'A revised check'}}); render();
  assert.equal(button('Evaluate current revision policy').props.disabled, true);
  await hook.props.onBlur({target: {value: 'A revised check'}}); render();
  assert(text(tree).includes('UNEVALUATED / STALE'));
  assert(calls.some(c => c.url.endsWith('/content-plans/42') && c.method === 'PATCH'));
  await button('Evaluate current revision policy').props.onClick(); render();
  assert(text(tree).includes('RAW POLICY: REVIEW'));
  assert(!calls.some(c => /materialize|\/run|publish/.test(c.url)));
  assert(!nodes().some(n => n.type === 'button' && /Approve|Create ProductionTask/.test(text(n))));
  assert.equal(button('Generate ContentPlan').props.disabled, true);
  assert.doesNotMatch(page, /runProductionTask|runPublishTask|materialize_feedback_task|materializeContentPlan/);
  console.log('FRONTEND_BRIEF_CONSTRAINTS_BODY=PASS');
  console.log('FRONTEND_NESTED_RESPONSE_UNPACKED=PASS');
  console.log('FRONTEND_TOPIC_READONLY_VALID_EDIT=PASS');
  console.log('FRONTEND_RAW_EFFECTIVE_STALE_POLICY=PASS');
  console.log('FRONTEND_NO_AUTO_RUN=PASS');
  console.log('FRONTEND_NO_AUTO_PUBLISH=PASS');
  console.log('FRONTEND_CONTRACT=PASS');
} finally { globalThis.fetch = originalFetch; }
