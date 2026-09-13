# Remote Pay Guide CI/CD Video Pipeline

## 0. Purpose

This document records the GitHub Actions layer of Remote Pay Guide Video Factory.

It describes:

```
GitHub Actions Render
        ↓
Artifact
        ↓
GitHub Pages
        ↓
VideoAsset
        ↓
Publish Center
        ↓
Official Platform Adapter
```

Production logic is documented in:

```
docs/VIDEO_PRODUCTION_PIPELINE.md
```

---

# 1. Render Workflow

Workflow:

```
.github/workflows/render-launch02.yml
```

Purpose:

Batch render short02-short10 content.

Runner:

```
ubuntu-latest
```

MoneyPrinterTurbo is provided through the workflow environment.

Required secret:

```
PEXELS_API_KEY
```

Artifact:

```
remote-pay-guide-short02-short10
```

---

# 2. Publish Workflow

Example:

```
.github/workflows/publish-existing-short04.yml
.github/workflows/publish-existing-short05.yml
```

Purpose:

Publish existing rendered assets without rerendering.

Flow:

```
Render artifact
        ↓
actions/download-artifact@v4
        ↓
public media staging
        ↓
GitHub Pages media URL
        ↓
VideoAsset.asset_url
        ↓
Publish Center
        ↓
Official Platform Adapter
```

---

# 3. Artifact Download Requirement

Publish workflows consume artifacts from successful render workflow runs.

Rules:

- `source_run_id` must be the complete GitHub Actions Run ID.
- The value comes from the successful render workflow run.
- Do not use workflow number, job ID, or shortened values.
- Artifact name and repository context must match.

When download fails:

```
Download existing rendered batch
```

check:

1. source render workflow Run ID
2. artifact name
3. repository context
4. artifact availability

---

# 4. Media Hosting

Rendered assets are staged into GitHub Pages media storage.

Example:

```
media/short04.mp4
media/short04.json
```

The OS records the public URL as:

```
VideoAsset.asset_url
```

The publishing runner does not upload the video file directly.

---

# 5. Formal OS Publishing

The current formal production path uses the existing Publish Center, Publish Registry, and official platform adapters. It does not depend on Postiz.

Historical workflows used:

```
POSTIZ_API_KEY
POSTIZ_API_BASE_URL
```

and called:

```
video-factory/postiz_publish.py
```

That path is historical / legacy / unavailable. Postiz is uninstalled and must not be restored or used as a fallback for formal OS publishing.

---

# 6. Historical Postiz Retry Behavior

The following records legacy behavior only; it is not the current formal OS publish contract. The historical Postiz publishing bridge was idempotent.

A publish workflow can be safely rerun after a partial platform failure.

The publish bridge keeps publish state and checks previously completed platforms.

When a publish workflow is executed again:

- Existing successful platforms are skipped.
- Failed or incomplete platforms are retried.
- The workflow does not blindly recreate all platform posts.

Example from the validated short04 production run:

```
SKIP short04:facebook already succeeded
SKIP short04:instagram already succeeded
SUCCESS short04:youtube
```

This means a platform authentication issue can be fixed first, then the same publish workflow can be rerun to complete missing platforms.

Recovery procedure:

1. Fix the platform authentication or API issue.
2. Re-run the same publish workflow.
3. Verify the previously failed platform completes.

Do not rerender the video.
Do not manually upload the media again.

---

# 7. Historical Validated Short04 Chain

This chain is retained as historical evidence and is not the current formal production dependency:

```
render-launch02.yml
        ↓
remote-pay-guide-short02-short10 artifact
        ↓
publish-existing-short04.yml
        ↓
media/short04.mp4
        ↓
GitHub Pages
        ↓
Postiz --media-url (legacy / unavailable)
        ↓
Social platforms
```

---

# 8. Maintenance Rule

Do not redesign CI/CD without checking:

1. Render workflow
2. Artifact contract
3. Media hosting step
4. Publish workflow
5. Platform retry behavior

Changes should preserve the current formal chain: GitHub Actions Render → Artifact → GitHub Pages → VideoAsset → Publish Center → Official Platform Adapter. Legacy Postiz evidence may remain documented, but Postiz must not be treated as an available dependency or fallback.
