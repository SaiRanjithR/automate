"""policy rules and audit runs (zero-code policy hot-swap)

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policyrule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("rule_key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("scope", sa.String(), nullable=False, server_default="requirement"),
        sa.Column("when", sa.JSON(), nullable=True),
        sa.Column("flag_if", sa.JSON(), nullable=True),
        sa.Column("severity", sa.String(), nullable=False, server_default="medium"),
        sa.Column("message", sa.String(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_policyrule_rule_key", "policyrule", ["rule_key"], unique=True)
    op.create_table(
        "auditrun",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=True),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("rules_evaluated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_auditrun_project_id", "auditrun", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_auditrun_project_id", table_name="auditrun")
    op.drop_table("auditrun")
    op.drop_index("ix_policyrule_rule_key", table_name="policyrule")
    op.drop_table("policyrule")
