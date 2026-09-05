from __future__ import annotations

import importlib.util
import json
import random
import unittest
from datetime import datetime, timezone
from itertools import pairwise
from pathlib import Path
from tempfile import TemporaryDirectory

MODULE_PATH = Path(__file__).parents[1] / "video-factory" / "postiz_publish.py"
SPEC = importlib.util.spec_from_file_location("postiz_publish", MODULE_PATH)
assert SPEC and SPEC.loader
postiz_publish = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(postiz_publish)


class ScheduleTests(unittest.TestCase):
    def test_manual_schedule_wins_and_keeps_exact_instant(self) -> None:
        actual = postiz_publish.normalize_schedule(
            "2026-09-06T20:17:31+08:00",
            "2026-09-06T15:00:00Z",
        )
        self.assertEqual(actual, "2026-09-06T12:17:31.000Z")

    def test_existing_schedule_is_never_replaced_by_automatic_logic(self) -> None:
        actual = postiz_publish.normalize_schedule("", "2026-09-06T14:23:00Z")
        self.assertEqual(actual, "2026-09-06T14:23:00.000Z")

    def test_manual_schedule_requires_timezone(self) -> None:
        with self.assertRaisesRegex(SystemExit, "timezone"):
            postiz_publish.normalize_schedule("2026-09-06T20:17:31", None)

    def test_auto_batch_is_staggered_randomized_and_in_target_windows(self) -> None:
        now = datetime(2026, 9, 5, 2, 0, tzinfo=timezone.utc)
        rng = random.Random(20260905)
        with TemporaryDirectory() as temp:
            state_dir = Path(temp)
            values = []
            for index in range(6):
                value = postiz_publish.allocate_auto_schedule(
                    state_dir, now=now, rng=rng
                )
                values.append(value)
                (state_dir / f"short{index + 20}.json").write_text(
                    json.dumps(
                        {
                            "content_id": f"short{index + 20}",
                            "scheduled_at": value,
                            "schedule_source": "auto",
                        }
                    ),
                    encoding="utf-8",
                )

            parsed = [postiz_publish.parse_schedule(value) for value in values]
            minutes = [value.strftime("%Y-%m-%dT%H:%M") for value in parsed]
            gaps = [
                int((later - earlier).total_seconds() // 60)
                for earlier, later in pairwise(parsed)
            ]

            self.assertEqual(len(minutes), len(set(minutes)))
            self.assertTrue(all(postiz_publish.is_auto_window(value) for value in parsed))
            self.assertTrue(all(gap >= postiz_publish.AUTO_MIN_GAP_MINUTES for gap in gaps))
            self.assertGreater(len(set(gaps)), 1)

    def test_manual_reservation_blocks_same_minute_without_being_changed(self) -> None:
        now = datetime(2026, 9, 5, 12, 40, tzinfo=timezone.utc)
        with TemporaryDirectory() as temp:
            state_dir = Path(temp)
            manual = "2026-09-05T13:17:00.000Z"
            (state_dir / "short08.json").write_text(
                json.dumps(
                    {
                        "content_id": "short08",
                        "scheduled_at": manual,
                        "schedule_source": "manual",
                    }
                ),
                encoding="utf-8",
            )
            automatic = postiz_publish.allocate_auto_schedule(
                state_dir, now=now, rng=random.Random(4)
            )

            self.assertNotEqual(automatic[:16], manual[:16])
            saved = json.loads((state_dir / "short08.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["scheduled_at"], manual)
            self.assertEqual(saved["schedule_source"], "manual")


if __name__ == "__main__":
    unittest.main()
