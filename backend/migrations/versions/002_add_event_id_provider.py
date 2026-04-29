"""add event_id and event_provider to picks

Revision ID: 002
Revises: 001
Create Date: 2026-04-29

Pin a Pick to a specific external game (ESPN or Odds API) at submission
time. Resolution then becomes a direct lookup instead of fuzzy team-name
matching, eliminating the wrong-day match class of bugs.

Both columns are nullable so existing rows stay valid; the resolver keeps
the legacy matching path for picks without event_id until backfill or
attrition retires them.
"""
from alembic import op
import sqlalchemy as sa


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("picks", sa.Column("event_id", sa.String(), nullable=True))
    op.add_column("picks", sa.Column("event_provider", sa.String(), nullable=True))
    op.create_index("ix_picks_event_id", "picks", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_picks_event_id", table_name="picks")
    op.drop_column("picks", "event_provider")
    op.drop_column("picks", "event_id")
