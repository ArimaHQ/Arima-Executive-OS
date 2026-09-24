"""Add the Laya orchestration task graph."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0028"
down_revision: str | None = "20260924_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_AUDIT_ENTITIES = (
    "project", "task", "company", "contact", "lead", "pipeline", "pipeline_stage",
    "deal", "crm_note", "crm_activity", "mailbox", "email_template", "email_draft",
    "sequence", "campaign", "automation", "data_feed_observation",
    "voice_authorization_diagnostic", "account", "withdrawal", "withdrawal_circuit_breaker",
    "document", "trade", "knowledge_source", "knowledge_document", "laya_task",
)
_STATUSES = (
    "discovered", "ready", "running", "blocked", "failed", "retry",
    "verifying", "passed", "completed", "rejected",
)
_FAILURE_CLASSES = (
    "transient", "data", "code", "dependency", "permission",
    "infrastructure", "architectural",
)


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN (" + ", ".join(repr(value) for value in values) + ")"


def upgrade() -> None:
    op.create_table(
        "laya_tasks",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(120), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("outputs", sa.JSON(), nullable=False),
        sa.Column("systems", sa.JSON(), nullable=False),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=False),
        sa.Column("tests", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("blockers", sa.JSON(), nullable=False),
        sa.Column("failure_class", sa.String(14), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("requires_human", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(_in("status", _STATUSES), name="laya_task_status"),
        sa.CheckConstraint(_in("failure_class", _FAILURE_CLASSES), name="laya_failure_class"),
        sa.CheckConstraint("attempts >= 0", name="laya_task_attempts_non_negative"),
        sa.CheckConstraint("max_attempts >= 1", name="laya_task_max_attempts_positive"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_laya_tasks_status_updated", "laya_tasks", ["status", "updated_at"])
    op.create_table(
        "laya_task_dependencies",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("depends_on_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("task_id <> depends_on_id", name="laya_task_dependency_not_self"),
        sa.ForeignKeyConstraint(["task_id"], ["laya_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["depends_on_id"], ["laya_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "depends_on_id"),
    )
    op.create_index(
        "ix_laya_task_dependencies_depends_on", "laya_task_dependencies", ["depends_on_id"]
    )
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_constraint("audit_entity", type_="check")
        batch.create_check_constraint("audit_entity", _in("entity", _AUDIT_ENTITIES))


def downgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_constraint("audit_entity", type_="check")
        batch.create_check_constraint("audit_entity", _in("entity", _AUDIT_ENTITIES[:-1]))
    op.drop_index("ix_laya_task_dependencies_depends_on", table_name="laya_task_dependencies")
    op.drop_table("laya_task_dependencies")
    op.drop_index("ix_laya_tasks_status_updated", table_name="laya_tasks")
    op.drop_table("laya_tasks")
