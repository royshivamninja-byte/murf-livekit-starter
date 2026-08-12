import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from memory import DEFAULT_DATABASE_PATH

ISSUE_TYPES = {"PAYMENT_REFUND", "ORDER_DISPUTE"}
URGENCY_LEVELS = {"LOW", "MEDIUM", "HIGH", "EMERGENCY"}
STATUSES = {"OPEN", "IN_PROGRESS", "RESOLVED"}

SENSITIVE_PATTERNS = (
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    re.compile(r"(?i)\b(?:otp|pin|cvv|password|passcode)\s*(?:is|:|=)?\s*\S+"),
    re.compile(
        r"(?i)\b(?:api|access|auth(?:entication)?)\s*[-_ ]?token\s*(?:is|:|=)?\s*\S+"
    ),
    re.compile(r"(?i)\bapi\s*[-_ ]?key\s*(?:is|:|=)?\s*\S+"),
    re.compile(r"(?i)\bbank\s+account(?:\s+number)?\s*(?:is|:|=)?\s*[\d -]{6,}"),
)


def sanitize_escalation_summary(value: str) -> str:
    """Remove obvious credentials and financial identifiers from human-help text."""
    sanitized = value.strip()
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return re.sub(r"\s+", " ", sanitized)


@dataclass(frozen=True)
class Escalation:
    id: int
    reference_id: str
    customer_name: str
    issue_type: str
    summary: str
    checked_information: str
    urgency: str
    language: str
    preferred_followup: str
    status: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class EscalationStore:
    """Persistent escalation records stored beside the existing caller memory."""

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
                CREATE TABLE IF NOT EXISTS escalations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference_id TEXT UNIQUE,
                    customer_id TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    issue_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    checked_information TEXT NOT NULL,
                    urgency TEXT NOT NULL,
                    language TEXT NOT NULL,
                    preferred_followup TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _from_row(row: sqlite3.Row | None) -> Escalation | None:
        if row is None:
            return None
        return Escalation(**{key: row[key] for key in Escalation.__dataclass_fields__})

    def get(self, reference_id: str) -> Escalation | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM escalations WHERE reference_id = ?",
                (reference_id.strip().upper(),),
            ).fetchone()
        return self._from_row(row)

    def list(self) -> list[Escalation]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM escalations ORDER BY created_at DESC"
            ).fetchall()
        return [self._from_row(row) for row in rows if row is not None]

    def create_or_update(
        self,
        *,
        customer_id: str,
        customer_name: str,
        issue_type: str,
        summary: str,
        checked_information: str,
        urgency: str,
        language: str,
        preferred_followup: str,
        consent_given: bool,
    ) -> tuple[Escalation, bool]:
        if not consent_given:
            raise PermissionError("Explicit permission is required")
        issue_type = issue_type.strip().upper()
        urgency = urgency.strip().upper()
        if issue_type not in ISSUE_TYPES:
            raise ValueError("Unsupported issue type")
        if urgency not in URGENCY_LEVELS:
            raise ValueError("Unsupported urgency")
        if not customer_name.strip():
            raise ValueError("Customer name is required")
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=30)).isoformat()
        safe_summary = sanitize_escalation_summary(summary)
        safe_checked = sanitize_escalation_summary(checked_information)
        with self._connect() as connection:
            duplicate = connection.execute(
                """
                SELECT * FROM escalations
                WHERE customer_id = ? AND issue_type = ?
                  AND status IN ('OPEN', 'IN_PROGRESS') AND updated_at >= ?
                ORDER BY updated_at DESC LIMIT 1
                """,
                (customer_id.strip(), issue_type, cutoff),
            ).fetchone()
            timestamp = now.isoformat()
            if duplicate is not None:
                combined_summary = sanitize_escalation_summary(
                    f"{duplicate['summary']} Latest update: {safe_summary}"
                )
                combined_checked = sanitize_escalation_summary(
                    f"{duplicate['checked_information']} Latest checks: {safe_checked}"
                )
                connection.execute(
                    """
                    UPDATE escalations SET summary = ?, checked_information = ?,
                        urgency = ?, language = ?, preferred_followup = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        combined_summary,
                        combined_checked,
                        urgency,
                        language.strip(),
                        preferred_followup.strip(),
                        timestamp,
                        duplicate["id"],
                    ),
                )
                connection.commit()
                return self.get(duplicate["reference_id"]), False

            cursor = connection.execute(
                """
                INSERT INTO escalations (
                    reference_id, customer_id, customer_name, issue_type, summary,
                    checked_information, urgency, language, preferred_followup,
                    status, created_at, updated_at
                ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
                """,
                (
                    customer_id.strip(),
                    sanitize_escalation_summary(customer_name),
                    issue_type,
                    safe_summary,
                    safe_checked,
                    urgency,
                    sanitize_escalation_summary(language),
                    sanitize_escalation_summary(preferred_followup),
                    timestamp,
                    timestamp,
                ),
            )
            reference_id = f"ESC-{now.year}-{cursor.lastrowid:03d}"
            connection.execute(
                "UPDATE escalations SET reference_id = ? WHERE id = ?",
                (reference_id, cursor.lastrowid),
            )
        return self.get(reference_id), True

    def update_status(self, reference_id: str, status: str) -> Escalation | None:
        status = status.strip().upper()
        if status not in STATUSES:
            raise ValueError("Unsupported status")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE escalations SET status = ?, updated_at = ? WHERE reference_id = ?",
                (
                    status,
                    datetime.now(timezone.utc).isoformat(),
                    reference_id.strip().upper(),
                ),
            )
        if cursor.rowcount == 0:
            return None
        return self.get(reference_id)
