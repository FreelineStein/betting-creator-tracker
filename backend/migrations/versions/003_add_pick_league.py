"""add league column to picks and rename MLS sport to SOCCER

Revision ID: 003
Revises: 002
Create Date: 2026-05-01

Soccer was being forced into the MLS sport tag because the parser had no
way to distinguish leagues. Now sport=SOCCER is canonical for any soccer
pick and the specific competition (Premier League, Europa League, MLS,
etc.) lives on the new `league` column.

Existing MLS-tagged rows are migrated to sport=SOCCER, league=MLS so the
record stays intact — most of those picks really were MLS, the rest can
be hand-corrected via /admin tooling.
"""
from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("picks", sa.Column("league", sa.String(), nullable=True))
    # Existing MLS picks were really soccer-MLS — relabel them so the new
    # SOCCER multi-league enrichment path picks them up uniformly.
    op.execute(
        "UPDATE picks SET sport = 'SOCCER', league = 'MLS' WHERE sport = 'MLS'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE picks SET sport = 'MLS', league = NULL WHERE sport = 'SOCCER' AND league = 'MLS'"
    )
    op.drop_column("picks", "league")
