"""add flagged_for_review column to sources

Revision ID: 004
Revises: 003
Create Date: 2026-05-12

User-flagged review queue. When a submission's extracted picks don't match
the post (parlay split into singles, wrong line, wrong odds, etc.), the
user clicks a "Picks don't look right?" affordance on the success panel
and we flip this bit. Admin sweeps the queue and corrects via reprocess +
surgical updates.
"""
from alembic import op
import sqlalchemy as sa


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column(
            "flagged_for_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("sources", "flagged_for_review")
