import unittest
from unittest.mock import patch

from pipeline_progress import OperationTracker


class OperationTrackerTests(unittest.TestCase):
    def test_completed_operation_reports_steps_and_elapsed_time(self):
        tracker = OperationTracker()

        with patch("pipeline_progress.time.time", side_effect=[100.0, 100.4]):
            operation = tracker.start("operation-1", "chat")
            self.assertEqual(operation["status"], "running")

            tracker.begin_step("operation-1", "query_embedding", "Encoding")
            tracker.finish_step("operation-1", "query_embedding", "384 dimensions")
            completed = tracker.complete("operation-1")

        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["elapsed_ms"], 400)
        self.assertEqual(completed["steps"][0]["status"], "completed")
        self.assertEqual(completed["steps"][0]["detail"], "384 dimensions")
        self.assertNotIn("_started_at", completed["steps"][0])

    def test_failure_marks_the_running_step(self):
        tracker = OperationTracker()
        tracker.start("operation-2", "upload")
        tracker.begin_step("operation-2", "parsing", "Extracting")

        failed = tracker.fail("operation-2", "Unreadable PDF")

        self.assertIsNotNone(failed)
        self.assertEqual(failed["status"], "failed")
        parsing = next(step for step in failed["steps"] if step["id"] == "parsing")
        self.assertEqual(parsing["status"], "failed")
        self.assertEqual(parsing["detail"], "Unreadable PDF")


if __name__ == "__main__":
    unittest.main()
