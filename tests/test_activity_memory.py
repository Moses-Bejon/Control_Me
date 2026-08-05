import tempfile
import unittest
from datetime import datetime

from modules.activity_memory import ActivityMemory


class ActivityMemoryTests(unittest.TestCase):
    def test_completed_unsummarized_hours_excludes_active_and_saved_hours(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ActivityMemory(directory)
            completed_hour = datetime(2026, 7, 30, 12)
            active_hour = datetime(2026, 7, 30, 13)

            memory.append_observation(completed_hour.replace(minute=30), "Working")
            memory.append_observation(active_hour.replace(minute=5), "Still working")

            self.assertEqual(
                memory.completed_unsummarized_hours(datetime(2026, 7, 30, 13, 15)),
                [completed_hour],
            )

            observations = memory.read_hour(completed_hour)
            memory.save_summary(completed_hour, "Worked.", observations, 60)

            self.assertEqual(
                memory.completed_unsummarized_hours(datetime(2026, 7, 30, 13, 15)),
                [],
            )

    def test_summary_lookup_does_not_treat_a_later_hour_as_summarized(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ActivityMemory(directory)
            earlier_hour = datetime(2026, 7, 30, 12)
            later_hour = datetime(2026, 7, 30, 13)

            memory.append_observation(later_hour.replace(minute=10), "Working")
            memory.save_summary(later_hour, "Worked.", memory.read_hour(later_hour), 60)

            self.assertFalse(memory.has_summary(earlier_hour))
            self.assertTrue(memory.has_summary(later_hour))

    def test_summary_lookup_supports_the_final_hour_of_a_day(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ActivityMemory(directory)
            final_hour = datetime(2026, 7, 30, 23)

            memory.append_observation(final_hour.replace(minute=50), "Working")
            memory.save_summary(final_hour, "Worked.", memory.read_hour(final_hour), 60)

            self.assertTrue(memory.has_summary(final_hour))

    def test_summaries_for_date_returns_each_saved_summary_in_time_order(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ActivityMemory(directory)
            first_hour = datetime(2026, 7, 30, 9)
            second_hour = datetime(2026, 7, 30, 10)

            for hour, summary in ((second_hour, "Second."), (first_hour, "First.")):
                memory.append_observation(hour.replace(minute=30), summary)
                memory.save_summary(hour, summary, memory.read_hour(hour), 60)

            self.assertEqual(
                [summary for _, _, summary in memory.summaries_for_date(first_hour.date())],
                ["First.", "Second."],
            )


if __name__ == "__main__":
    unittest.main()
