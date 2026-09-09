# Remote Pay Guide OS Loop Gap Audit

审计基线：当前 `main`。本文件只按真实 writer、reader、runtime、测试与外部 E2E 证据判断成熟度；synthetic fixture 不等同于真实外部 E2E。

## 1. Current Loop

Remote Pay Guide OS 的目标闭环：

```text
Content
→ Production
→ Video Asset
→ Publish
→ Platform Traffic
→ Landing / Intent
→ Referral Click
→ Conversion
→ AI Intelligence
→ Next Production Strategy
```

当前真实可达主链：

```text
YouTube Content
→ YouTube Analytics
→ Query V2 / Data Center
→ Intelligence feedback
→ strategy recommendation
→ explicit ProductionTask
→ explicit Production Runtime
→ VideoAsset
→ explicit Publish boundary
```

Landing Page / GA4 侧还存在一条已经实现、但尚未完成真实归因验收的链：

```text
Published content link
→ GitHub Pages landing page
→ GA4
→ binance_referral_click
```

---

## 2. Gap Matrix

| Stage | Current maturity | Real source / writer | Reader | Automation | Real E2E state | Main gap | Priority |
|---|---|---|---|---|---|---|---|
| Content Data | REAL E2E VERIFIED | YouTube Data API + local publish/task metadata | Data Center / tracking | Scheduled content sync | REAL VERIFIED | Broader provider reconciliation | P1 |
| Analytics | REAL E2E VERIFIED | YouTube Analytics API daily/aggregate rows + typed no-data | Query V2 / Data Center | Scheduled daily + backfill | REAL VERIFIED | Multi-provider coverage | P1 |
| Scheduler / Runtime Observability | CLOSED | SQLite runtime state/history | Accounts status/UI | Automatic | REAL TWO-PROCESS + CI VERIFIED | No current blocker | CLOSED |
| AI Intelligence | CODE + TEST VERIFIED | Query V2 + growth funnel | Intelligence UI/API | Explicit refresh | Synthetic/local verified | Needs more real business feedback | P1 |
| ProductionTask | CODE + TEST VERIFIED | Strategy/manual API | Production APIs/UI | Manual/explicit | Contract verified | No controlled automation yet | P1 |
| Production Runtime | CODE + TEST VERIFIED | GitHub / AI provider adapters | Runtime/results APIs | Polls submitted jobs | Synthetic lifecycle verified | Real unattended provider E2E limited | P1 |
| VideoAsset | CODE + TEST VERIFIED | Runtime result / remote reference | Asset + Publish | Created by sync/runtime | Contract verified | Provider durability parity | P1 |
| Publish | PARTIAL | Official YouTube adapter | Publish APIs/UI | Explicit | No canonical real new-upload closeout | Real external upload/status reconciliation | P0 |
| Landing Page | LIVE | GitHub Pages | Browser / GA4 | Public | Public page reachable | None for basic hosting | VERIFIED |
| GA4 Event Tracking | IMPLEMENTED | Browser `rpg:event` → GA4 | GA4 | Automatic | Code implemented; real per-content click attribution not yet closed | Real validation | P0 |
| Binance Referral Click | IMPLEMENTED | `binance_referral_click` in `app.js` | GA4 | Automatic on CTA click | REAL E2E attribution pending | Prove content identity in GA4 | P0 |
| Signed HMAC Intent Ingestion | LOCAL CONTRACT VERIFIED | `/attribution/intent` | Growth/Data Center | External relay optional | r32 local PASS | Public relay not currently required | P2 / OPTIONAL |
| Conversion Provider Boundary | CODE + TEST VERIFIED | `/attribution/conversion/{provider}` | Growth/Data Center | Provider callback required | No real provider | Binance registration attribution intentionally deferred | LATER |
| Feedback | CODE + TEST VERIFIED | Analytics + growth rows | Intelligence | Explicit | Synthetic/local | Needs real GA4 click import into OS | P0 |
| Next Strategy | CODE + TEST VERIFIED | Feedback snapshot | Strategy/task generator | Explicit | Synthetic/local | Needs real business signal before more automation | P1 |

---

## 3. Corrected Attribution Reality

Previous versions of this audit treated the first broken link as:

```text
Public Traffic → Trusted Intent Collector
```

That is no longer the correct immediate development framing.

The public GitHub Pages landing page already emits GA4 events, and the Binance CTA already emits:

```text
binance_referral_click
```

with attribution parameters derived from the landing URL, including `src` and `content_id` when present.

Therefore:

```text
Public collector deployment is NOT required before we can answer
"which content produced a Binance referral click?"
```

The immediate gap is evidence, not event creation:

```text
Known content
→ attributed landing URL
→ real public page session
→ real Binance CTA click
→ GA4 event
→ same content identity visible in GA4
```

Until that is observed with real data, status remains:

```text
Content → Binance Referral Click Attribution:
IMPLEMENTED, REAL E2E NOT YET VERIFIED
```

---

## 4. Attribution Link Compatibility Gap

Historical posting links commonly use:

```text
?src=short04
```

Current frontend code also supports explicit:

```text
?src=yt_short04&content_id=short04
```

New canonical links should use explicit `content_id`, while old links must remain valid.

Required compatibility behavior:

- preserve all existing published URLs;
- do not require republishing old videos;
- if a legacy `src` unambiguously maps to a known content ID, recover it safely;
- do not invent a content ID from ambiguous sources;
- test that `binance_referral_click` carries stable attribution fields.

---

## 5. HMAC Attribution Boundary Status

The existing provider-neutral signed attribution boundary remains useful:

```text
/attribution/intent
/attribution/conversion/{provider}
signed redirect/link
```

Its local contract covers HMAC verification, dedupe, identifier validation, privacy limits, canonical intent/conversion persistence, and provider-neutral adapter boundaries.

It should be preserved, but it is not the next mandatory deployment target.

A Vercel/Cloudflare/public relay becomes relevant only if later requirements need one of the following:

- raw server-side event capture independent of GA4;
- trusted first-party session-level event storage;
- a conversion provider callback that must reach the OS through a public endpoint;
- richer attribution data not available from GA4 reporting.

Do not deploy external infrastructure just to duplicate an already-existing GA4 click event.

---

## 6. Binance Conversion Scope

Two separate questions must not be mixed:

```text
A. Did this content generate a Binance referral-link click?
B. Did the user later register / convert on Binance?
```

Current project scope:

- A: current priority, pending real GA4 E2E validation.
- B: intentionally deferred until enough real traffic exists to justify the integration.

Therefore Binance registration conversion is NOT a current blocking gap.

Do not claim Binance registration E2E until a real provider/API/callback or equivalent verified source is connected.

---

## 7. Current Autonomous Loop Status

| Node | Status | Evidence |
|---|---|---|
| observe YouTube content | AUTOMATIC | scheduler/content sync |
| observe YouTube analytics | AUTOMATIC | scheduled daily + backfill |
| analyze | MANUAL / EXPLICIT | feedback refresh |
| decide strategy | MANUAL / EXPLICIT | deterministic recommendation |
| create ProductionTask | MANUAL / EXPLICIT | materialize endpoint |
| produce | MANUAL / EXPLICIT | runtime/provider boundary |
| publish | MANUAL / EXPLICIT | publish run |
| observe platform traffic | AUTOMATIC | YouTube Analytics |
| observe landing page events | AUTOMATIC IN GA4 | browser GA4 integration |
| observe Binance referral click | AUTOMATIC IN GA4 | CTA emits event |
| import GA4 business signals into OS | MISSING | no GA4 reporting connector in canonical OS path yet |
| observe Binance registration conversion | DEFERRED | no real provider source |
| learn from real referral clicks | PARTIAL | blocked by GA4 → OS ingestion |
| create next task automatically | MISSING BY DESIGN | controlled/manual safety gate retained |

---

# PRIORITY GAPS

## P0 — Current

1. **GA4 Content → Binance Referral Click real attribution validation**
   - normalize new attribution links to explicit `src + content_id`;
   - preserve legacy `?src=shortXX` compatibility;
   - add regression tests;
   - perform real GitHub Pages → GA4 click validation;
   - do not reimplement the existing click event.

2. **GA4 → OS Data Center ingestion**
   - connect GA4 reporting/property auth to the existing Data Center;
   - import landing visits and Binance referral clicks by content/source/time;
   - preserve one Data Center, one Query Engine, one growth model;
   - expose unavailable when data is absent; do not fabricate zeros.

3. **Publish real external closeout**
   - only with explicit user authorization;
   - one controlled YouTube private upload is sufficient for canonical real E2E proof;
   - verify `platform_video_id`, URL, state persistence and observation linkage.

## P1

- More real-data-driven Intelligence evaluation.
- Controlled feedback → ProductionTask materialization after enough real traffic exists.
- Production Runtime real external provider E2E/retry/result linkage.
- Provider content/status reconciliation.
- Multi-provider publish/analytics parity after YouTube-first loop is stable.

## Later / Optional

- Binance registration conversion attribution.
- Public HMAC relay/collector when real requirements justify it.
- Full autonomous ProductionTask / Publish behavior.
- Additional platform expansion.

---

# RECOMMENDED NEXT IMPLEMENTATION STAGE

**Stage:** GA4 Content → Binance Referral Click Attribution Closeout

**Why:** The click event and public landing page already exist. The shortest path to real business evidence is to validate and normalize attribution rather than deploy another collector.

**Input:** published content identity, attributed GitHub Pages URL, real public visit, Binance CTA click.

**Output:** a GA4 `binance_referral_click` event that can be unambiguously tied back to the content item.

**Acceptance criteria:**

```text
one known content item
→ real landing URL
→ real public session
→ Binance CTA click
→ GA4 event observed
→ source/content identity confirmed
→ no duplicate/fabricated attribution
```

**Then:** build GA4 → OS Data Center reporting ingestion so Intelligence can consume real click data.

**What NOT to build now:**

- another `binance_referral_click` implementation;
- a mandatory Vercel/Cloudflare collector;
- Binance registration conversion integration;
- second Analytics storage;
- second Query Engine;
- another Scheduler;
- automatic ProductionTask or automatic Publish before real business feedback exists.
