import sqlite3
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path


class ActivityMemory:
    """Persists raw hourly observations and their one-sentence summaries."""

    def __init__(self, data_directory: str | Path) -> None:
        self.data_directory = Path(data_directory).expanduser()
        self.hours_directory = self.data_directory / "hours"
        self.database_path = self.data_directory / "activity_memory.db"
        self.hours_directory.mkdir(parents=True, exist_ok=True)
        self._create_database()

    def _create_database(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS hourly_summaries (
                    date TEXT NOT NULL,
                    hour_start TEXT NOT NULL,
                    hour_end TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    PRIMARY KEY (date, hour_start)
                )
                """
            )

    def hourly_file_path(self, hour: datetime) -> Path:
        hour_start = hour.replace(minute=0, second=0, microsecond=0)
        return self.hours_directory / f"{hour_start:%Y-%m-%d-%H}.txt"

    def append_observation(self, observed_at: datetime, description: str) -> None:
        path = self.hourly_file_path(observed_at)
        with path.open("a", encoding="utf-8") as activity_file:
            activity_file.write(f"{observed_at:%H:%M:%S} {description.strip()}\n")

    def read_hour(self, hour: datetime) -> str:
        path = self.hourly_file_path(hour)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    def has_summary(self, hour: datetime) -> bool:
        """Return whether ``hour`` already has a stored summary."""
        hour_start = hour.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        query = """
            SELECT 1 FROM hourly_summaries
            WHERE date = ? AND hour_start >= ?
        """
        parameters = [
            hour_start.date().isoformat(),
            hour_start.strftime("%H:%M:%S"),
        ]
        if hour_end.date() == hour_start.date():
            query += " AND hour_start < ?"
            parameters.append(hour_end.strftime("%H:%M:%S"))

        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(query, parameters).fetchone()
        return row is not None

    def completed_unsummarized_hours(self, now: datetime | None = None) -> list[datetime]:
        """Return recorded hours that ended before ``now`` and need a summary."""
        current_hour = (now or datetime.now()).replace(
            minute=0, second=0, microsecond=0
        )
        completed_hours = []

        for path in self.hours_directory.glob("*.txt"):
            try:
                hour = datetime.strptime(path.stem, "%Y-%m-%d-%H")
            except ValueError:
                traceback.print_exc()
                continue

            if hour < current_hour and not self.has_summary(hour):
                completed_hours.append(hour)

        return sorted(completed_hours)

    def summaries_for_date(
        self, on_date: date, exclude_hour: datetime | None = None
    ) -> list[tuple[str, str, str]]:
        """Return stored summaries for ``date``, ordered by their activity window."""
        excluded_start = None
        excluded_end = None
        if exclude_hour is not None:
            excluded_start = exclude_hour.replace(minute=0, second=0, microsecond=0)
            excluded_end = excluded_start + timedelta(hours=1)

        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT hour_start, hour_end, summary
                FROM hourly_summaries
                WHERE date = ?
                ORDER BY hour_start
                """,
                (on_date.isoformat(),),
            ).fetchall()

        summaries = []
        for hour_start, hour_end, summary in rows:
            if (
                excluded_start is not None
                and excluded_start.strftime("%H:%M:%S") <= hour_start < excluded_end.strftime("%H:%M:%S")
            ):
                continue
            summaries.append((hour_start, hour_end, summary))
        return summaries

    def summary_window(
        self, hour: datetime, observations: str, capture_interval_seconds: int
    ) -> tuple[datetime, datetime]:
        """Return the recorded activity window, constrained to ``hour``."""
        hour_start = hour.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        recorded_times = []

        for line in observations.splitlines():
            try:
                recorded_time = datetime.strptime(line[:8], "%H:%M:%S").time()
            except ValueError:
                traceback.print_exc()
                continue
            recorded_times.append(hour_start.replace(
                hour=recorded_time.hour,
                minute=recorded_time.minute,
                second=recorded_time.second,
            ))

        if not recorded_times:
            return hour_start, hour_end

        interval = timedelta(seconds=max(0, int(capture_interval_seconds)))
        return (
            max(hour_start, min(recorded_times) - interval),
            min(hour_end, max(recorded_times) + interval),
        )

    def save_summary(
        self,
        hour: datetime,
        summary: str,
        observations: str,
        capture_interval_seconds: int,
    ) -> None:
        activity_start, activity_end = self.summary_window(
            hour, observations, capture_interval_seconds
        )

        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO hourly_summaries (date, hour_start, hour_end, summary)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(date, hour_start) DO UPDATE SET
                    hour_end = excluded.hour_end,
                    summary = excluded.summary
                """,
                (
                    activity_start.date().isoformat(),
                    activity_start.strftime("%H:%M:%S"),
                    activity_end.strftime("%H:%M:%S"),
                    summary.strip(),
                ),
            )
