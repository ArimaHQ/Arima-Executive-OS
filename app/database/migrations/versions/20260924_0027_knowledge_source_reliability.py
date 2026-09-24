"""Add knowledge-source reliability metadata and knowledge audit entities."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0027"
down_revision: str | None = "20260824_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_AUDIT_ENTITIES = (
    "project", "task", "company", "contact", "lead", "pipeline", "pipeline_stage",
    "deal", "crm_note", "crm_activity", "mailbox", "email_template", "email_draft",
    "sequence", "campaign", "automation", "data_feed_observation",
    "voice_authorization_diagnostic", "account", "withdrawal", "withdrawal_circuit_breaker",
    "document", "trade", "knowledge_source", "knowledge_document",
)
_RELIABILITY = ("official", "primary", "established", "user_provided", "unverified")


def _audit_constraint(entities: Sequence[str]) -> str:
    return "entity IN (" + ", ".join(repr(item) for item in entities) + ")"


def upgrade() -> None:
    with op.batch_alter_table("knowledge_sources") as batch:
        batch.add_column(
            sa.Column(
                "reliability",
                sa.String(13),
                server_default="unverified",
                nullable=False,
            )
        )
        batch.add_column(sa.Column("authority", sa.String(300), nullable=True))
        batch.create_check_constraint(
            "knowledge_source_reliability",
            "reliability IN (" + ", ".join(repr(item) for item in _RELIABILITY) + ")",
        )
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_constraint("audit_entity", type_="check")
        batch.create_check_constraint("audit_entity", _audit_constraint(_AUDIT_ENTITIES))


def downgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_constraint("audit_entity", type_="check")
        batch.create_check_constraint("audit_entity", _audit_constraint(_AUDIT_ENTITIES[:-2]))
    with op.batch_alter_table("knowledge_sources") as batch:
        batch.drop_constraint("knowledge_source_reliability", type_="check")
        batch.drop_column("authority")
        batch.drop_column("reliability")
