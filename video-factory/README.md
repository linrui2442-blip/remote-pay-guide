# Remote Pay Guide Video Factory — MoneyPrinterTurbo adapter

This directory contains the Remote Pay Guide video production system.

The system reuses `harry0703/MoneyPrinterTurbo` for rendering infrastructure while Remote Pay Guide controls acquisition content, visual rules, CTA, attribution metadata and content selection.

## Why this path

MoneyPrinterTurbo provides:

- stock-video retrieval (Pexels/Pixabay/Coverr)
- Edge TTS voiceover
- subtitles
- FFmpeg/MoviePy composition
- 9:16 output
- JSON/JSONL batch tasks
- task state and artifacts

Remote Pay Guide provides:

- content_id
- scripts
- video terms
- acquisition hooks
- CTA rules
- attribution metadata

## Launch batch

`tasks-launch01.jsonl` contains the initial batch (`short01` through `short10`).

`tasks-short01.jsonl` is the single-video quality gate manifest used before scaling.

Tasks provide:

- `video_script`
- `video_terms`

The render path does not require an LLM to generate scripts or search terms.

## Rendering flow

Production flow:

```
Content Task JSONL
        ↓
render_batch.py
        ↓
MoneyPrinterTurbo adapter
        ↓
Rendered video
        ↓
polish_short.py
        ↓
Polished video asset
```

## Proof workflow

`.github/workflows/render-short01.yml` is a proof render workflow.

It validates:

- MoneyPrinterTurbo environment
- task format
- rendering quality
- polishing step

It is not the production batch runner.

Production batches use `render_batch.py`.

## Current render defaults

- portrait: `9:16`
- stock source: `pexels`
- ordered material matching: enabled
- clip order: sequential
- clip duration: 5 seconds
- English Edge TTS: Jenny
- voice rate: 1.08
- burned subtitles: enabled
- English subtitle font: `BeVietnamPro-Bold.ttf`
- background music: disabled for first quality tests

## Quality gate

Before scaling:

1. Visuals must look like real freelancer / remote-work footage.
2. Avoid crypto hype visuals.
3. First 3 seconds must communicate the payment problem.
4. Narration must sound natural.
5. Subtitles must be readable on mobile.
6. Duration target: 25–35 seconds.
7. CTA should be clear.

## Auto publishing

Current Remote Pay Guide publishing flow:

```
Polished video
        ↓
postiz_publish.py
        ↓
Postiz Public API
        ↓
Facebook
Instagram
YouTube
```

The current production workflow does not use MoneyPrinterTurbo Upload-Post cross-posting.

Earlier Upload-Post experiments are historical only and are not the active publishing path.

### Publishing schedule

- A non-empty `--schedule-at` value is treated as a manual choice, normalized to UTC, stored as `schedule_source: manual`, and never replaced by automatic scheduling.
- If the argument is blank, an existing stored schedule is reused so retries remain idempotent.
- If neither exists, the publisher reserves a randomized time in UTC windows that overlap high-activity hours for freelancers and digital nomads in the Philippines, India, Vietnam, Indonesia, Nigeria, Pakistan, and Brazil.
- Automatically scheduled videos share the local publish-state directory, use a cross-process lock, avoid occupied minutes, and receive randomized 47–173 minute spacing instead of a fixed batch cadence.

## Media delivery

Publishing supports:

- public media URL delivery
- Postiz media upload fallback

The production validation path uses public media hosting:

```
GitHub Pages media URL
        ↓
Postiz
        ↓
Social platforms
```

## Attribution rule

The primary tracking key is:

```
content_id
```

It connects:

```
Task
 ↓
Video asset
 ↓
Post
 ↓
Traffic attribution
```

Video-level performance is joined through platform post IDs and GA4 traffic attribution.

Current active platforms:

- YouTube
- Instagram
- Facebook

TikTok is not part of the current publishing workflow.

## Future production rule

For new videos:

1. Create content task.
2. Add JSONL entry.
3. Run batch render.
4. Run polishing step.
5. Prepare publishing metadata.
6. Publish through Postiz.
7. Validate attribution with GA4.
