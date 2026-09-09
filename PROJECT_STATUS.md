# Remote Pay Guide Project Status

> This root status file is a concise project index. For the current OS development state and next-step plan, use `docs/PROJECT_STATUS.md` as the canonical status document.

## Legacy Pipeline

- short01-short10 production pipeline: completed and preserved.
- Legacy GitHub production / Postiz compatibility assets remain in the repository for historical compatibility.
- Formal Remote Pay Guide OS publishing must not be redesigned around Postiz.

## Remote Pay Guide OS

Remote Pay Guide OS is an AI-driven content production and growth operations control system.

Core loop:

```text
Data Feedback
→ AI Intelligence
→ Production Task
→ Production Execution
→ Video Asset
→ Publish
→ Traffic / Intent / Conversion
→ Data Feedback
```

Current real-platform focus is YouTube-first.

## Completed / Verified Foundation

- GitHub Production compatibility preserved
- AI Gateway remote-production architecture preserved
- Video Asset layer implemented
- Publish Center architecture implemented
- YouTube OAuth real verified
- YouTube metadata/content sync real verified
- YouTube Analytics real historical E2E verified
- Scheduled Daily Analytics real unattended E2E verified
- Query V2 / Data Center verified
- Active tracking policy and historical retention implemented
- Scheduler cross-process claim / lease / crash recovery / heartbeat verified
- Operational runtime history and health-event persistence implemented
- Test Database Isolation mainline + CI verified
- Growth / intent / conversion storage exists inside the existing Data Center
- Provider-neutral signed HMAC attribution ingestion contract locally verified
- GitHub Pages landing page live
- GA4 browser integration implemented
- `binance_referral_click` browser event already implemented

## Current Attribution Reality

The current landing page already tracks:

```text
src
content_id
page_view
payment_type_select
payer_type_select
exchange_status_select
new_to_exchange_identified
binance_referral_click
```

Therefore the current project does **not** need to add another Binance-click tracking implementation before continuing.

The real next proof is:

```text
known content
→ attributed public GitHub Pages URL
→ real public session
→ Binance CTA click
→ GA4 binance_referral_click
→ same content identity confirmed
```

Historical campaign links such as:

```text
?src=short04
```

must remain compatible. New canonical links should include explicit content identity, for example:

```text
?src=yt_short04&content_id=short04
```

## Current Next Development Stage

### 1. GA4 Content → Binance Referral Click Attribution Closeout

- preserve legacy link compatibility;
- standardize new `src + content_id` links;
- add attribution regression tests;
- perform real GitHub Pages → GA4 click validation;
- do not claim REAL E2E until GA4 evidence is observed.

### 2. GA4 → OS Data Center Ingestion

After the real click attribution is verified, connect GA4 reporting into the existing Data Center so the OS can compare content using landing visits, Binance referral clicks and click-through rate alongside YouTube Analytics.

Do not create a second Analytics store or Query Engine.

### 3. Run the system and accumulate real data

Prefer real operational evidence before adding more infrastructure or platforms.

## Deferred / Later

- Binance registration/conversion attribution
- public Vercel/Cloudflare/HMAC relay unless a real requirement justifies it
- real external AI video provider E2E
- full Facebook / Instagram / TikTok live provider parity
- fully automatic ProductionTask / Publish loop

## Runtime Data Safety

Source code and runtime state are separate lifecycle objects.

```text
Source code:
Git repository

Runtime state:
os/database/os.db
```

The production runtime database must never be used as a test database or replaced by a fresh checkout.

See:

```text
docs/PROJECT_STATUS.md
docs/RUNTIME_DATA_POLICY.md
docs/OS_LOOP_GAP_AUDIT.md
docs/REMOTE_PAY_GUIDE_OS_BLUEPRINT.md
```
