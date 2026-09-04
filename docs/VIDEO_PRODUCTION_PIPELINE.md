# Remote Pay Guide Video Production Pipeline

## 0. Purpose

This document is the production SOP for Remote Pay Guide Video Factory.

Video Factory is not a manual editing workflow. It is a batch content production system:

```
Content Task
    ↓
Video Generation
    ↓
Post Processing
    ↓
Publishing
    ↓
Attribution Validation
```

The core production object is not the MP4 file. It is the `content_id`.

`content_id` connects:

```
Task
 ↓
Video asset
 ↓
Publishing metadata
 ↓
Traffic attribution
```

---

# 1. Content Preparation

Video production starts from JSONL task manifests inside `video-factory/`:

- `tasks-launch01.jsonl`
- `tasks-launch02.jsonl`
- `tasks-short01.jsonl`

These files define production tasks, not output files or publishing records.

Each task provides rendering inputs including:

- `video_subject`
- `video_script`
- `video_terms`

Metadata JSON files provide additional content-level information.

Example:

```
video-factory/launch02-meta.json
```

Metadata enriches production tasks. It does not replace JSONL task definitions.

---

# 2. Rendering Pipeline

The batch renderer is:

```
video-factory/render_batch.py
```

Input:

```
Task JSONL
+
Metadata JSON
```

Required runtime arguments include:

- `--mpt-root`
- `--tasks`
- `--meta`
- `--output`
- `--polisher`
- `--font`

Flow:

```
JSONL task
    ↓
render_batch.py
    ↓
MoneyPrinterTurbo adapter flow
    ↓
Rendered video
    ↓
polish_short.py
```

The rendered source video is expected as:

```
final-1.mp4
```

---

# 3. MoneyPrinterTurbo Role

Remote Pay Guide uses MoneyPrinterTurbo as the rendering engine.

It provides:

- stock video retrieval
- voice generation
- subtitle generation
- FFmpeg/MoviePy composition
- final video rendering

Remote Pay Guide controls content tasks, hooks, CTA, and attribution metadata.

---

# 4. Post Processing Pipeline

After rendering:

```
Rendered video
      ↓
polish_short.py
      ↓
polished-{content_id}.mp4
```

The final polished asset is stored under the content output directory.

---

# 5. Publishing Pipeline

The validated short04 publishing architecture is:

```
Polished MP4
      ↓
GitHub Pages public media
      ↓
Postiz
      ↓
YouTube Shorts
Instagram Reels
Facebook Reels
```

Important:

Postiz uses a public media URL.

The publishing flow does not upload the MP4 file to Postiz from the runner.

The media URL is passed through `--media-url`.

---

# 6. Short04 Validation Case

short04 is the first validated production chain.

The actual GitHub Actions workflow chain:

## Render

Workflow:

```
.github/workflows/render-launch02.yml
```

Purpose:

Render short02-short10 batch content.

Runner:

```
ubuntu-latest
```

Task input:

```
video-factory/tasks-launch02.jsonl
```

Metadata:

```
video-factory/launch02-meta.json
```

Artifact:

```
remote-pay-guide-short02-short10
```

---

## Publish

Workflow:

```
.github/workflows/publish-existing-short04.yml
```

Purpose:

Publish an existing rendered short04 asset.

The workflow:

1. Downloads the existing render artifact.
2. Extracts short04 polished video.
3. Creates public media files:

```
media/short04.mp4
media/short04.json
```

4. Commits media files to main branch.
5. Uses GitHub Pages as public media hosting.
6. Passes the public URL to Postiz.

Public media URL:

```
https://linrui2442-blip.github.io/remote-pay-guide/media/short04.mp4
```

Publish runner:

```
[self-hosted, windows, x64]
```

Postiz receives:

```
--media-url
```

and does not require downloading the video asset to the publishing runner.

---

# 7. Future Production SOP

For short05+:

```
1. Create content task

        ↓

2. Add task to JSONL manifest

        ↓

3. Prepare metadata

        ↓

4. Run batch render

        ↓

5. Execute polish step

        ↓

6. Stage public media asset

        ↓

7. Publish through Postiz using media URL

        ↓

8. Validate GA4 attribution
```

---

# 8. Current Known Limitations

Current areas requiring further validation:

- fully unattended batch publishing flow
- complete content_id to native platform post_id attribution chain
- retry and publishing recovery behavior

Unverified functions must not be treated as completed.

---

# 9. Operational Rule

Future maintenance rules:

Do not:

- redesign Video Factory without understanding the existing pipeline
- replace validated production workflows unnecessarily
- remove the short04 validated chain

Any modification should follow:

```
Understand existing pipeline
        ↓
Identify actual bottleneck
        ↓
Make minimum change
        ↓
Validate production flow
```
