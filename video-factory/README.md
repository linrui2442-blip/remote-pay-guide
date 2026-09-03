# Remote Pay Guide Video Factory — MoneyPrinterTurbo adapter

This directory contains the first production batch prepared for `harry0703/MoneyPrinterTurbo`.

## Why this path

We reuse MoneyPrinterTurbo for the expensive plumbing:

- stock-video retrieval (Pexels/Pixabay/Coverr)
- Edge TTS voiceover
- subtitles
- FFmpeg/MoviePy composition
- 9:16 output
- JSON/JSONL batch tasks
- task state and artifacts
- optional cross-posting

Remote Pay Guide remains responsible for the acquisition-specific content, visual rules, CTA, attribution metadata and winner selection.

## Launch batch

`tasks-launch01.jsonl` contains 10 ready-to-render tasks (`short01` through `short10` in source order).

`tasks-short01.jsonl` is the single-video quality-gate manifest used before scaling to the full batch.

Each task already provides both:

- `video_script`
- `video_terms`

Therefore the basic render path does **not** need an LLM to write the script or generate search terms. Pexels still requires a free API key. The selected Edge voice is `en-US-JennyNeural-Female`.

## Fastest proof: GitHub Actions

The repository contains `.github/workflows/render-short01.yml`.

It performs the proof render in GitHub Actions instead of requiring a local MoneyPrinterTurbo installation:

1. Add a repository Actions secret named `PEXELS_API_KEY`.
2. Open **Actions → Render short01 proof → Run workflow**.
3. The workflow clones a pinned MoneyPrinterTurbo revision, installs its locked environment, injects the Pexels key without printing it, renders `tasks-short01.jsonl`, and uploads a `short01-proof` artifact.
4. Download the artifact and review the MP4 against the quality gate below.

The workflow deliberately uses only one short. Do not spend compute on the full 10 until the visual quality is acceptable.

## Windows proof-of-render

1. Clone MoneyPrinterTurbo.
2. Install its documented dependencies / `uv` environment.
3. Copy `config.example.toml` to `config.toml` if the project has not done so automatically.
4. Add a Pexels API key under `pexels_api_keys`.
5. Copy `tasks-short01.jsonl` into the MoneyPrinterTurbo working directory (or pass its absolute path).
6. Run:

```bash
uv run python cli.py --batch-file ./tasks-short01.jsonl --stop-at video
```

After short01 passes the quality gate, render all ten with:

```bash
uv run python cli.py --batch-file ./tasks-launch01.jsonl --stop-at video
```

MoneyPrinterTurbo accepts JSON arrays or JSONL manifests and currently supports up to 100 tasks per batch.

## Current render defaults

- portrait: `9:16`
- stock source: `pexels`
- ordered material matching: enabled
- clip order: sequential
- clip duration: 5 seconds
- English Edge TTS: Jenny
- voice rate: 1.08
- burned subtitles: enabled
- English subtitle font for proof: `BeVietnamPro-Bold.ttf`
- background music: disabled for the first quality test

BGM stays off initially so we can judge narration, subtitle timing and visual relevance without masking problems.

## Quality gate for short01

Do not scale to all 10 until `short01` passes these checks:

1. Visuals look like real freelancer / remote-work footage, not crypto hype.
2. No random Bitcoin coins, price charts, supercars or trading screens.
3. The first 3 seconds communicate the client-payment problem immediately.
4. English narration sounds natural at 1.08x.
5. Subtitles are readable on a phone and do not cover platform UI zones.
6. Total duration is roughly 25–35 seconds.
7. The final CTA is clear: `Beginner guide in profile.`

## What upstream still needs changed for us

The first batch intentionally stays compatible with upstream MoneyPrinterTurbo. The next adapter layer will add:

- stable `content_id` in task/publish logs
- fixed Remote Pay Guide hook/CTA overlay template
- per-platform title/caption/hashtags supplied by our content engine
- platform post ID persistence
- Facebook Reels exposure in cross-post config
- retry-safe publishing log
- profile-link attribution rules

## Auto publishing

MoneyPrinterTurbo already has an Upload-Post integration and can trigger cross-posting after a successful render. Its example config currently exposes TikTok, Instagram and YouTube. Upstream task metadata already contains a Facebook Reels mapping, so Facebook support is a small integration change rather than a new publishing system.

Upload-Post is a third-party service and is not permanently free. If we later remove that monthly dependency, the replacement path is official platform APIs. YouTube and Meta can be integrated directly; TikTok Direct Post has an important approval constraint: unaudited clients are limited to private visibility, so public unattended TikTok publishing requires app approval/audit.

## Attribution rule

Do **not** pretend a static profile link can carry a different `src` for every short.

Default profile links should use channel-level sources:

- YouTube: `?src=yt_profile`
- TikTok: `?src=tt_profile`
- Instagram: `?src=ig_profile`
- Facebook: `?src=fb_profile`

The video-level key remains `content_id` and is joined to the platform's returned `post_id`. Creative performance is measured from native post analytics; GA4 measures the platform/profile traffic that reaches Remote Pay Guide. If a platform surface genuinely supports a clickable per-post link, then a per-video source such as `yt_short01` can be used there.
