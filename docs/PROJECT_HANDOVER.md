# Remote Pay Guide Project Handover

## 1. Purpose

This document is the operational handover entry point for Remote Pay Guide Video Factory.

A new developer or AI agent should read this document together with:

- `docs/PROJECT_STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/VIDEO_PRODUCTION_PIPELINE.md`
- `docs/CI_CD_VIDEO_PIPELINE.md`
- `docs/RUN_HISTORY.md`
- `docs/TROUBLESHOOTING.md`

before making changes.

The project is a production pipeline, not a manual video editing workflow.

---

# 2. Current Production Status

Validated production assets:

## short04

Status:

```
Published ✅
```

Validated chain:

```
Render
↓
Artifact
↓
GitHub Pages media
↓
Postiz
↓
Facebook
Instagram
YouTube
```

## short05

Status:

```
Published ✅
```

Validated:

```
Render ✅
Artifact ✅
Media URL ✅
Postiz ✅
Facebook ✅
Instagram ✅
YouTube ✅
```

Current phase:

```
Ready for short06-short10 production
```

---

# 3. Production Pipeline

The production chain is:

```
Content Task
↓
JSONL task definition
↓
render-launch02.yml
↓
render_batch.py
↓
MoneyPrinterTurbo
↓
polish_short.py
↓
GitHub Artifact
↓
publish-existing-shortXX.yml
↓
GitHub Pages media URL
↓
Postiz API
↓
Social platforms
```

The core production object is the content asset, not the mp4 file alone.

---

# 4. GitHub Actions

## Render

Workflow:

```
.github/workflows/render-launch02.yml
```

Purpose:

Generate the short02-short10 batch.

Artifact:

```
remote-pay-guide-short02-short10
```

Do not rerender existing validated assets unless required.

## Publish

Example workflows:

```
.github/workflows/publish-existing-short04.yml
.github/workflows/publish-existing-short05.yml
```

Purpose:

Publish existing rendered assets without generating videos again.

---

# 5. Publish Recovery Rule

The publish bridge is idempotent.

When a publish workflow is rerun:

- Successful platforms are skipped.
- Failed platforms are retried.

Example from short04 validation:

```
SKIP short04:facebook already succeeded
SKIP short04:instagram already succeeded
SUCCESS short04:youtube
```

Recovery process:

```
Fix platform authentication/API issue
↓
Run the same publish workflow again
↓
Missing platform is published
```

Do not:

- rerender the video
- upload media manually
- recreate all posts manually

---

# 6. Known Operational Issues

## Artifact Not Found

Check:

1. source render workflow run ID
2. artifact name
3. repository context
4. artifact availability

Do not modify workflow architecture before checking the artifact contract.

## YouTube Authentication

If Facebook and Instagram succeed but YouTube fails:

```
Postiz
↓
Reconnect YouTube OAuth
↓
Run publish workflow again
```

The publish bridge will retry only the missing platform.

---

# 7. Maintenance Rules

Do not:

- redesign Video Factory
- replace the validated publishing chain
- remove existing workflows
- change publishing logic without validation

Before any modification:

```
Understand current pipeline
↓
Identify exact failure point
↓
Make minimum change
↓
Validate with production flow
```

---

# 8. Next Task

Continue production with:

```
short06
short07
short08
short09
short10
```

Follow the existing validated short04/short05 process.
