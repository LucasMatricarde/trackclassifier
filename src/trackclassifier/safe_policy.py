from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .labels import Label

MIN_PRECISION = 0.97
MIN_OFFLINE_ELIGIBLE = 30
MIN_SHADOW_TOTAL = 100
AUDIT_WINDOW = 100


class AutomationState(StrEnum):
    MANUAL = "manual"
    SHADOW = "shadow"
    RELEASED = "released"
    SUSPENDED = "suspended"


@dataclass(frozen=True)
class ClassSafetyState:
    label: Label
    state: AutomationState
    threshold: float | None
    offline_precision: float | None
    offline_eligible: int
    shadow_correct: int
    shadow_total: int
    recent_precision: float | None
    recent_total: int


class SafetyPolicyStore:
    """Diario transacional da evidencia e dos movimentos automaticos.

    Toda consulta e filtrada por ``evidence_version``. Assim uma mudanca no
    extrator, nos pesos, no algoritmo ou na regra de seguranca invalida a
    evidencia sem apagar o historico auditavel das versoes anteriores.
    """

    def __init__(self, path: Path, evidence_version: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_version = evidence_version
        self._create_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _create_schema(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS class_evidence (
                    evidence_version TEXT NOT NULL,
                    label TEXT NOT NULL,
                    offline_correct INTEGER NOT NULL,
                    offline_eligible INTEGER NOT NULL,
                    threshold REAL NOT NULL,
                    PRIMARY KEY (evidence_version, label)
                );
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    evidence_version TEXT NOT NULL,
                    label TEXT NOT NULL,
                    phase TEXT NOT NULL CHECK (phase IN ('shadow', 'audit')),
                    correct INTEGER NOT NULL CHECK (correct IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS auto_moves (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL,
                    sha1 TEXT NOT NULL,
                    source TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    label TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    evidence_version TEXT NOT NULL,
                    probability REAL NOT NULL,
                    state TEXT NOT NULL,
                    human_label TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(batch_id, sha1)
                );
                CREATE INDEX IF NOT EXISTS auto_moves_pending
                    ON auto_moves(state, evidence_version);
                """
            )

    def record_offline(
        self, label: Label, *, correct: int, eligible: int, threshold: float
    ) -> None:
        if correct < 0 or eligible < 0 or correct > eligible:
            raise ValueError("Evidencia offline invalida")
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO class_evidence (
                    evidence_version, label, offline_correct, offline_eligible, threshold
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(evidence_version, label) DO UPDATE SET
                    offline_correct=excluded.offline_correct,
                    offline_eligible=excluded.offline_eligible,
                    threshold=excluded.threshold
                """,
                (self.evidence_version, label.value, correct, eligible, threshold),
            )

    def _record_observation(self, label: Label, phase: str, correct: bool) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO observations (evidence_version, label, phase, correct)
                VALUES (?, ?, ?, ?)
                """,
                (self.evidence_version, label.value, phase, int(correct)),
            )

    def record_shadow(self, label: Label, *, correct: bool) -> None:
        self._record_observation(label, "shadow", correct)

    def record_audit(self, label: Label, *, correct: bool) -> None:
        self._record_observation(label, "audit", correct)

    def state_for(self, label: Label) -> ClassSafetyState:
        with self._connect() as db:
            evidence = db.execute(
                """
                SELECT offline_correct, offline_eligible, threshold
                FROM class_evidence
                WHERE evidence_version = ? AND label = ?
                """,
                (self.evidence_version, label.value),
            ).fetchone()
            shadow = db.execute(
                """
                SELECT COALESCE(SUM(correct), 0) AS correct, COUNT(*) AS total
                FROM observations
                WHERE evidence_version = ? AND label = ? AND phase = 'shadow'
                """,
                (self.evidence_version, label.value),
            ).fetchone()
            audits = db.execute(
                """
                SELECT correct FROM observations
                WHERE evidence_version = ? AND label = ? AND phase = 'audit'
                ORDER BY id DESC LIMIT ?
                """,
                (self.evidence_version, label.value, AUDIT_WINDOW),
            ).fetchall()

        offline_eligible = int(evidence["offline_eligible"]) if evidence else 0
        offline_precision = (
            float(evidence["offline_correct"]) / offline_eligible
            if evidence and offline_eligible
            else None
        )
        threshold = float(evidence["threshold"]) if evidence else None
        shadow_correct = int(shadow["correct"])
        shadow_total = int(shadow["total"])
        recent_total = len(audits)
        recent_precision = (
            sum(int(row["correct"]) for row in audits) / recent_total
            if recent_total
            else None
        )

        offline_ok = (
            offline_eligible >= MIN_OFFLINE_ELIGIBLE
            and offline_precision is not None
            and offline_precision >= MIN_PRECISION
        )
        shadow_ok = (
            shadow_total >= MIN_SHADOW_TOTAL
            and shadow_correct / shadow_total >= MIN_PRECISION
        )
        suspended = (
            recent_total >= AUDIT_WINDOW
            and recent_precision is not None
            and recent_precision < MIN_PRECISION
        )
        if not offline_ok:
            state = AutomationState.MANUAL
        elif not shadow_ok:
            state = AutomationState.SHADOW
        elif suspended:
            state = AutomationState.SUSPENDED
        else:
            state = AutomationState.RELEASED

        return ClassSafetyState(
            label=label,
            state=state,
            threshold=threshold,
            offline_precision=offline_precision,
            offline_eligible=offline_eligible,
            shadow_correct=shadow_correct,
            shadow_total=shadow_total,
            recent_precision=recent_precision,
            recent_total=recent_total,
        )

    def is_eligible(self, label: Label, probability: float) -> bool:
        state = self.state_for(label)
        return (
            state.state is AutomationState.RELEASED
            and state.threshold is not None
            and probability >= state.threshold
        )

    def begin_move(
        self,
        *,
        batch_id: str,
        sha1: str,
        source: Path,
        destination: Path,
        label: Label,
        model_version: str,
        probability: float,
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT OR IGNORE INTO auto_moves (
                    batch_id, sha1, source, destination, label, model_version,
                    evidence_version, probability, state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'prepared')
                """,
                (
                    batch_id,
                    sha1,
                    str(source),
                    str(destination),
                    label.value,
                    model_version,
                    self.evidence_version,
                    probability,
                ),
            )

    def complete_move(self, batch_id: str, sha1: str, destination: Path) -> None:
        with self._connect() as db:
            db.execute(
                """
                UPDATE auto_moves SET state='pending_audit', destination=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE batch_id=? AND sha1=?
                """,
                (str(destination), batch_id, sha1),
            )

    def pending_auto_sha1s(self) -> set[str]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT sha1 FROM auto_moves WHERE state='pending_audit'"
            ).fetchall()
        return {str(row["sha1"]) for row in rows}

    def is_human_labeled(self, sha1: str) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT state FROM auto_moves WHERE sha1=? ORDER BY id DESC LIMIT 1",
                (sha1,),
            ).fetchone()
        return row is None or row["state"] in {"confirmed", "corrected"}

    def confirm_auto_label(self, sha1: str) -> None:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT label FROM auto_moves
                WHERE sha1=? AND state='pending_audit' ORDER BY id DESC LIMIT 1
                """,
                (sha1,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Auto-rotulo pendente nao encontrado: {sha1}")
            db.execute(
                """
                UPDATE auto_moves SET state='confirmed', human_label=label,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=(SELECT id FROM auto_moves WHERE sha1=? AND state='pending_audit'
                          ORDER BY id DESC LIMIT 1)
                """,
                (sha1,),
            )
        self.record_audit(Label(row["label"]), correct=True)

