import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from memory import DEFAULT_DATABASE_PATH

FAILURE_TYPES = (
    "USER_HANGUP",
    "USER_DECLINED",
    "INCOMPLETE_ENQUIRY",
    "TOOL_FAILURE",
    "API_ERROR",
    "NO_RESPONSE",
    "OTHER",
    "HANDOFF_FAILURE",
)
TRACK_OUTCOMES = ("PRODUCT_ENQUIRY", "ORDER_REQUEST", "ORDER_COMPLETED")


@dataclass(frozen=True)
class AnalyticsFilter:
    date_from: date | None = None
    date_to: date | None = None
    language: str = ""
    channel: str = ""
    outcome: str = ""


class CallAnalyticsStore:
    """Call-level analytics stored beside the existing caller-memory tables."""

    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT UNIQUE NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    duration_seconds INTEGER,
                    channel TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'Unknown',
                    outcome TEXT,
                    failure_type TEXT,
                    track_outcome TEXT,
                    latency_ms INTEGER,
                    specialist_used INTEGER NOT NULL DEFAULT 0,
                    handoff_count INTEGER NOT NULL DEFAULT 0,
                    handoff_success INTEGER,
                    specialist_name TEXT
                )
                """
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(calls)").fetchall()
            }
            migrations = {
                "specialist_used": "INTEGER NOT NULL DEFAULT 0",
                "handoff_count": "INTEGER NOT NULL DEFAULT 0",
                "handoff_success": "INTEGER",
                "specialist_name": "TEXT",
            }
            for column, definition in migrations.items():
                if column not in columns:
                    connection.execute(
                        f"ALTER TABLE calls ADD COLUMN {column} {definition}"
                    )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_calls_started_at ON calls(started_at)"
            )

    def start_call(self, call_id: str, started_at: datetime, channel: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO calls (call_id, started_at, channel)
                VALUES (?, ?, ?)
                ON CONFLICT(call_id) DO NOTHING
                """,
                (call_id, started_at.isoformat(), channel),
            )

    def finish_call(
        self,
        *,
        call_id: str,
        ended_at: datetime,
        duration_seconds: int,
        language: str,
        outcome: str,
        failure_type: str | None,
        track_outcome: str | None,
        latency_ms: int | None,
        specialist_used: bool,
        handoff_count: int,
        handoff_success: bool | None,
        specialist_name: str | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE calls SET ended_at = ?, duration_seconds = ?, language = ?,
                    outcome = ?, failure_type = ?, track_outcome = ?, latency_ms = ?,
                    specialist_used = ?, handoff_count = ?, handoff_success = ?,
                    specialist_name = ?
                WHERE call_id = ?
                """,
                (
                    ended_at.isoformat(),
                    duration_seconds,
                    language,
                    outcome,
                    failure_type,
                    track_outcome,
                    latency_ms,
                    int(specialist_used),
                    handoff_count,
                    None if handoff_success is None else int(handoff_success),
                    specialist_name,
                    call_id,
                ),
            )

    @staticmethod
    def _where(filters: AnalyticsFilter) -> tuple[str, list[str]]:
        clauses = ["ended_at IS NOT NULL"]
        values: list[str] = []
        if filters.date_from:
            clauses.append("date(started_at) >= ?")
            values.append(filters.date_from.isoformat())
        if filters.date_to:
            clauses.append("date(started_at) <= ?")
            values.append(filters.date_to.isoformat())
        if filters.language:
            clauses.append("language = ?")
            values.append(filters.language)
        if filters.channel:
            clauses.append("channel = ?")
            values.append(filters.channel)
        if filters.outcome:
            clauses.append("outcome = ?")
            values.append(filters.outcome)
        return " AND ".join(clauses), values

    def summary(self, filters: AnalyticsFilter) -> dict[str, int | float]:
        where, values = self._where(filters)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) total_calls,
                    SUM(CASE WHEN outcome = 'SUCCESS' THEN 1 ELSE 0 END) successful_calls,
                    SUM(CASE WHEN outcome = 'FAILED' THEN 1 ELSE 0 END) failed_calls,
                    COALESCE(ROUND(AVG(latency_ms)), 0) average_latency_ms
                FROM calls WHERE {where}
                """,
                values,
            ).fetchone()
        total = int(row["total_calls"])
        successful = int(row["successful_calls"] or 0)
        return {
            "total_calls": total,
            "successful_calls": successful,
            "failed_calls": int(row["failed_calls"] or 0),
            "success_rate": round(successful / total * 100, 1) if total else 0.0,
            "average_latency_ms": int(row["average_latency_ms"]),
        }

    def list_calls(self, filters: AnalyticsFilter, limit: int = 100) -> list[dict]:
        where, values = self._where(filters)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT call_id, started_at, ended_at, duration_seconds, channel,
                       language, outcome, failure_type, track_outcome, latency_ms,
                       specialist_used, handoff_count, handoff_success, specialist_name
                FROM calls WHERE {where} ORDER BY started_at DESC LIMIT ?
                """,
                [*values, min(max(limit, 1), 500)],
            ).fetchall()
        return [dict(row) for row in rows]

    def trends(self, filters: AnalyticsFilter) -> list[dict]:
        where, values = self._where(filters)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT date(started_at) date, COUNT(*) total_calls,
                    SUM(CASE WHEN outcome = 'SUCCESS' THEN 1 ELSE 0 END) successful_calls,
                    SUM(CASE WHEN outcome = 'FAILED' THEN 1 ELSE 0 END) failed_calls
                FROM calls WHERE {where} GROUP BY date(started_at) ORDER BY date(started_at)
                """,
                values,
            ).fetchall()
        return [dict(row) for row in rows]

    def failures(self, filters: AnalyticsFilter) -> dict[str, int]:
        where, values = self._where(filters)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT failure_type, COUNT(*) count FROM calls
                WHERE {where} AND outcome = 'FAILED'
                GROUP BY failure_type
                """,
                values,
            ).fetchall()
        counts = dict.fromkeys(FAILURE_TYPES, 0)
        for row in rows:
            counts[row["failure_type"] or "OTHER"] = row["count"]
        return counts


class CallTracker:
    """Collect real LiveKit events for one call and persist one final record."""

    def __init__(
        self,
        store: CallAnalyticsStore,
        *,
        call_id: str,
        channel: str,
        started_at: datetime | None = None,
    ) -> None:
        self.store = store
        self.call_id = call_id
        self.started_at = started_at or datetime.now(timezone.utc)
        self.language = "Unknown"
        self.track_outcome: str | None = None
        self.latencies: list[int] = []
        self.last_user_completed_at: float | None = None
        self.error_seen = False
        self.failure_type: str | None = None
        self.user_turns = 0
        self.specialist_used = False
        self.handoff_count = 0
        self.handoff_success: bool | None = None
        self.specialist_name: str | None = None
        self._finished = False
        self._lock = threading.Lock()
        store.start_call(call_id, self.started_at, channel)

    def record_user_turn(self, *, language: str | None, completed_at: float) -> None:
        if language:
            code = str(language).casefold()
            self.language = "Hindi" if code.startswith("hi") else "English"
        self.user_turns += 1
        self.last_user_completed_at = completed_at

    def record_agent_speaking(self, *, started_at: float) -> None:
        if self.last_user_completed_at is None:
            return
        latency = round((started_at - self.last_user_completed_at) * 1000)
        if latency >= 0:
            self.latencies.append(latency)
        self.last_user_completed_at = None

    def mark_success(self, track_outcome: str) -> None:
        if track_outcome in TRACK_OUTCOMES:
            self.track_outcome = track_outcome

    def mark_error(self) -> None:
        self.error_seen = True

    def mark_failure(self, failure_type: str) -> None:
        if failure_type in FAILURE_TYPES:
            self.failure_type = failure_type

    def record_handoff(self, specialist_name: str, *, success: bool) -> None:
        self.handoff_count += 1
        self.handoff_success = success
        if success:
            self.specialist_used = True
            self.specialist_name = specialist_name
        else:
            self.mark_failure("HANDOFF_FAILURE")

    def finish(
        self,
        *,
        failure_type: str | None = None,
        ended_at: datetime | None = None,
    ) -> None:
        with self._lock:
            if self._finished:
                return
            self._finished = True
        ended_at = ended_at or datetime.now(timezone.utc)
        successful = self.track_outcome is not None
        if not successful:
            failure_type = (
                failure_type
                or self.failure_type
                or (
                    "API_ERROR"
                    if self.error_seen
                    else "NO_RESPONSE"
                    if self.user_turns == 0
                    else "INCOMPLETE_ENQUIRY"
                )
            )
        self.store.finish_call(
            call_id=self.call_id,
            ended_at=ended_at,
            duration_seconds=max(
                0, round((ended_at - self.started_at).total_seconds())
            ),
            language=self.language,
            outcome="SUCCESS" if successful else "FAILED",
            failure_type=None if successful else failure_type,
            track_outcome=self.track_outcome,
            latency_ms=(
                round(sum(self.latencies) / len(self.latencies))
                if self.latencies
                else None
            ),
            specialist_used=self.specialist_used,
            handoff_count=self.handoff_count,
            handoff_success=self.handoff_success,
            specialist_name=self.specialist_name,
        )
