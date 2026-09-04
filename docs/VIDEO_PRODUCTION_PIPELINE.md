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
 ↓
Performance analysis
```

---

# 1. Content Preparation

## Task Sources

Video production starts from JSONL task manifests inside `video-factory/`:

- `tasks-launch01.jsonl`
- `tasks-launch02.jsonl`
- `tasks-short01.jsonl`

These files are production inputs, not output files or publishing records.

Each task provides the content information required by the rendering pipeline, including:

- `video_subject`
- `video_script`
- `video_terms`

The current workflow does not require an LLM step to create scripts or search terms during rendering because those fields already exist in the task manifests.

---

# 2. Rendering Pipeline

## Entry Point

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

Command arguments include:

- `--tasks`
- `--meta`
- `--output`
- `--polisher`
- `--font`
- `--mpt-root`

## Flow

```
JSONL task
    ↓
render_batch.py
    ↓
MoneyPrinterTurbo adapter flow
    ↓
Rendered video
```

`render_batch.py`:

- reads task records from JSONL
- reads metadata records
- matches tasks with metadata using content order
- runs MoneyPrinterTurbo rendering
- locates generated task output
- sends the rendered video into post processing
- writes production metadata

The rendered source video from MoneyPrinterTurbo is expected as:

```
final-1.mp4
```

---

# 3. MoneyPrinterTurbo Role

Remote Pay Guide uses MoneyPrinterTurbo as the rendering engine.

It provides the production plumbing:

- stock video retrieval
- Edge TTS voice generation
- subtitle generation
- FFmpeg/MoviePy composition
- 9:16 video output
- batch task execution

Remote Pay Guide controls:

- acquisition content
- hooks
- CTA
- attribution metadata
- content selection

MoneyPrinterTurbo is called through the project pipeline rather than requiring manual editing.

---

# 4. Post Processing Pipeline

After rendering:

```
Rendered video
      ↓
polish_short.py
      ↓
Final polished video
```

The batch pipeline calls the polisher after MoneyPrinterTurbo completes.

Output naming:

```
polished-{content_id}.mp4
```

The final asset is stored under the content output directory.

The pipeline also copies subtitle output when available:

```
{content_id}.srt
```

---

# 5. Publishing Pipeline

Publishing uses the generated polished video asset.

Current flow:

```
Polished MP4
      ↓
Public media hosting
      ↓
Postiz
      ↓
Social platforms
```

Current publishing platforms:

- YouTube Shorts
- Instagram Reels
- Facebook Reels

Publishing automation is handled through Postiz-related workflow components.

Publishing records should keep:

- video asset
- caption
- platform
- metadata
- tracking information

---

# 6. Short04 Validation Case

short04 is the current production pipeline validation asset.

It validated the full chain:

```
Production task
      ↓
Render
      ↓
Polish
      ↓
Public media workflow
      ↓
Postiz publishing
      ↓
Attribution validation
```

short04 is not a separate production method. It is the first validated example of the standard pipeline.

Future content should reuse this workflow.

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

6. Prepare public media asset

        ↓

7. Publish through Postiz

        ↓

8. Validate GA4 attribution
```

---

# 8. Current Known Limitations

Current areas requiring further validation:

- fully unattended batch publishing flow
- complete media hosting automation
- complete content_id to native platform post_id attribution chain
- retry and publishing recovery behavior

Unverified functions must not be treated as completed.

---

# 9. Operational Rule

Future maintenance rules:

Do not:

- redesign Video Factory without understanding the existing pipeline
- replace the production chain unnecessarily
- remove validated short04 workflow

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
