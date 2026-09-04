# Remote Pay Guide CI/CD Video Pipeline

## 0. Purpose

This document records the GitHub Actions layer of Remote Pay Guide Video Factory.

It describes:

```
GitHub Actions
        ↓
Render workflow
        ↓
Artifact
        ↓
Media hosting
        ↓
Publish workflow
        ↓
Postiz
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
Postiz --media-url
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

Postiz receives the public URL through:

```
--media-url
```

The publishing runner does not upload the video file directly.

---

# 5. Postiz Publishing

Publishing uses:

```
POSTIZ_API_KEY
POSTIZ_API_BASE_URL
```

The bridge calls:

```
video-factory/postiz_publish.py
```

---

# 6. Platform-level Retry Behavior

The Postiz publishing bridge is idempotent.

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

# 7. Validated Short04 Chain

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
Postiz --media-url
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

Changes should preserve the validated production chain.
