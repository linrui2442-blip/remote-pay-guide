import assert from 'node:assert/strict';
import fs from 'node:fs';

const api = fs.readFileSync(new URL('../src/api.js', import.meta.url), 'utf8');
const page = fs.readFileSync(new URL('../src/pages/IntelligenceCenter.jsx', import.meta.url), 'utf8');
for (const name of ['generateContentPlan', 'updateContentPlan', 'approveContentPlan', 'materializeContentPlan']) assert.match(api, new RegExp(`export function ${name}`));
for (const name of ['generateContentPlan', 'updateContentPlan', 'approveContentPlan', 'materializeContentPlan']) assert.match(page, new RegExp(name));
assert.match(page, /plan\.status !== 'approved'/);
assert.match(page, /novelty_status === 'BLOCK'/);
assert.match(page, /Task created but not executed/);
assert.doesNotMatch(page, /runProductionTask\s*\(/);
assert.doesNotMatch(page, /runPublishTask\s*\(/);
console.log('FRONTEND_CONTENT_PLAN_FLOW=PASS');
console.log('FRONTEND_NOVELTY_GUARD=PASS');
console.log('FRONTEND_HUMAN_APPROVAL=PASS');
console.log('FRONTEND_MATERIALIZATION_ONLY=PASS');
console.log('FRONTEND_NO_AUTO_RUN=PASS');
console.log('FRONTEND_NO_AUTO_PUBLISH=PASS');
console.log('FRONTEND_CONTRACT=PASS');
