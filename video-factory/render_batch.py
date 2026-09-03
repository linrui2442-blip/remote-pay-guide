from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _run_stream(command: list[str], *, cwd: Path, log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            log.write(line)
        return proc.wait()


def _task_dirs(root: Path) -> set[Path]:
    if not root.exists():
        return set()
    return {p.resolve() for p in root.iterdir() if p.is_dir()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mpt-root", required=True)
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--meta", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--polisher", required=True)
    parser.add_argument("--font", required=True)
    args = parser.parse_args()

    repo_root = Path.cwd().resolve()
    mpt_root = Path(args.mpt_root).resolve()
    tasks_path = Path(args.tasks).resolve()
    meta_path = Path(args.meta).resolve()
    output_root = Path(args.output).resolve()
    polisher = Path(args.polisher).resolve()
    font_path = Path(args.font).resolve()

    task_records = [
        json.loads(line)
        for line in tasks_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    meta_records = json.loads(meta_path.read_text(encoding="utf-8"))
    if len(task_records) != len(meta_records):
        raise SystemExit(
            f"Task/meta count mismatch: {len(task_records)} tasks vs {len(meta_records)} metadata records"
        )

    output_root.mkdir(parents=True, exist_ok=True)
    mpt_tasks_root = mpt_root / "storage" / "tasks"
    summary: list[dict] = []
    failures = 0

    for index, (task, meta) in enumerate(zip(task_records, meta_records), start=1):
        content_id = str(meta["content_id"])
        hook = str(meta["hook"])
        target = output_root / content_id
        target.mkdir(parents=True, exist_ok=True)
        print(f"\n===== {content_id} ({index}/{len(task_records)}) =====")

        before = _task_dirs(mpt_tasks_root)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8", dir=str(mpt_root)
        ) as handle:
            handle.write(json.dumps(task, ensure_ascii=False) + "\n")
            single_manifest = Path(handle.name)

        log_path = target / "render.log"
        try:
            return_code = _run_stream(
                [
                    "uv",
                    "run",
                    "python",
                    "cli.py",
                    "--batch-file",
                    str(single_manifest),
                    "--stop-at",
                    "video",
                ],
                cwd=mpt_root,
                log_path=log_path,
            )
        finally:
            single_manifest.unlink(missing_ok=True)

        after = _task_dirs(mpt_tasks_root)
        created = sorted(after - before, key=lambda p: p.stat().st_mtime)
        if return_code != 0 or not created:
            failures += 1
            summary.append(
                {
                    "content_id": content_id,
                    "status": "failed",
                    "return_code": return_code,
                    "error": "MoneyPrinterTurbo failed or produced no task directory",
                }
            )
            print(f"FAILED: {content_id}", file=sys.stderr)
            continue

        task_dir = created[-1]
        final_video = task_dir / "final-1.mp4"
        subtitle = task_dir / "subtitle.srt"
        if not final_video.exists():
            failures += 1
            summary.append(
                {
                    "content_id": content_id,
                    "status": "failed",
                    "task_id": task_dir.name,
                    "error": "Rendered task has no final-1.mp4",
                }
            )
            print(f"FAILED: {content_id} has no final-1.mp4", file=sys.stderr)
            continue

        polished = target / f"polished-{content_id}.mp4"
        polish_command = [
            "uv",
            "run",
            "--project",
            str(mpt_root),
            "python",
            str(polisher),
            "--input",
            str(final_video),
            "--output",
            str(polished),
            "--font",
            str(font_path),
            "--hook",
            hook,
        ]
        polish_code = _run_stream(
            polish_command,
            cwd=repo_root,
            log_path=target / "polish.log",
        )
        if polish_code != 0 or not polished.exists():
            failures += 1
            summary.append(
                {
                    "content_id": content_id,
                    "status": "failed",
                    "task_id": task_dir.name,
                    "error": "Polish step failed",
                }
            )
            print(f"FAILED: polish step for {content_id}", file=sys.stderr)
            continue

        if subtitle.exists():
            shutil.copy2(subtitle, target / f"{content_id}.srt")

        record = {
            "content_id": content_id,
            "status": "succeeded",
            "task_id": task_dir.name,
            "hook": hook,
            "video_subject": task.get("video_subject"),
            "video_script": task.get("video_script"),
            "video_terms": task.get("video_terms"),
            "output": polished.name,
        }
        (target / "metadata.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summary.append(record)
        print(f"SUCCESS: {content_id} -> {polished}")

    batch_summary = {
        "total": len(task_records),
        "succeeded": sum(1 for item in summary if item["status"] == "succeeded"),
        "failed": failures,
        "items": summary,
    }
    (output_root / "batch-summary.json").write_text(
        json.dumps(batch_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(batch_summary, ensure_ascii=False, indent=2))

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
