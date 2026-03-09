"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # creators
    op.create_table(
        "creators",
        sa.Column("creator_id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column(
            "tier",
            sa.Enum("tracked", "public", name="creatortier"),
            nullable=False,
        ),
        sa.Column("platforms", sa.JSON(), nullable=True),
        sa.Column("tracking_active", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("creator_id"),
    )

    # sources
    op.create_table(
        "sources",
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("creator_id", sa.String(), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("instagram", "twitter", "youtube", "tiktok", "reddit", name="platform"),
            nullable=False,
        ),
        sa.Column(
            "post_type",
            sa.Enum(
                "reel", "tweet", "comment", "reddit_post",
                "reddit_comment", "youtube_video", "tiktok_video",
                name="posttype",
            ),
            nullable=False,
        ),
        sa.Column("post_url", sa.String(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column(
            "extraction_status",
            sa.Enum("pending", "success", "failed", "needs_review", name="extractionstatus"),
            nullable=False,
        ),
        sa.Column("extraction_attempts", sa.JSON(), nullable=True),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.creator_id"]),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index("ix_sources_creator_id", "sources", ["creator_id"])
    op.create_index("ix_sources_post_url", "sources", ["post_url"])

    # picks
    op.create_table(
        "picks",
        sa.Column("pick_id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("creator_id", sa.String(), nullable=False),
        sa.Column("sport", sa.String(), nullable=True),
        sa.Column("event", sa.String(), nullable=True),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "pick_type",
            sa.Enum("spread", "moneyline", "over_under", "prop", "parlay", name="picktype"),
            nullable=True,
        ),
        sa.Column("pick_detail", sa.JSON(), nullable=True),
        sa.Column("odds", sa.String(), nullable=True),
        sa.Column("units", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "won", "lost", "push", "void", name="pickstatus"),
            nullable=False,
        ),
        sa.Column(
            "logged_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("outcome_resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "extraction_method",
            sa.Enum("caption", "subtitles", "whisper", "ocr", "llm", "manual", name="extractionmethod"),
            nullable=True,
        ),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("raw_text", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.creator_id"]),
        sa.ForeignKeyConstraint(["source_id"], ["sources.source_id"]),
        sa.PrimaryKeyConstraint("pick_id"),
    )
    op.create_index("ix_picks_creator_id", "picks", ["creator_id"])
    op.create_index("ix_picks_status", "picks", ["status"])
    op.create_index("ix_picks_event_date", "picks", ["event_date"])

    # creator_records
    op.create_table(
        "creator_records",
        sa.Column("creator_id", sa.String(), nullable=False),
        sa.Column("total_picks", sa.Integer(), nullable=True),
        sa.Column("wins", sa.Integer(), nullable=True),
        sa.Column("losses", sa.Integer(), nullable=True),
        sa.Column("pushes", sa.Integer(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("roi", sa.Float(), nullable=True),
        sa.Column("accuracy_by_sport", sa.JSON(), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.creator_id"]),
        sa.PrimaryKeyConstraint("creator_id"),
    )


def downgrade() -> None:
    op.drop_table("creator_records")
    op.drop_index("ix_picks_event_date", table_name="picks")
    op.drop_index("ix_picks_status", table_name="picks")
    op.drop_index("ix_picks_creator_id", table_name="picks")
    op.drop_table("picks")
    op.drop_index("ix_sources_post_url", table_name="sources")
    op.drop_index("ix_sources_creator_id", table_name="sources")
    op.drop_table("sources")
    op.drop_table("creators")

    # Drop custom enum types
    op.execute("DROP TYPE IF EXISTS extractionmethod")
    op.execute("DROP TYPE IF EXISTS pickstatus")
    op.execute("DROP TYPE IF EXISTS picktype")
    op.execute("DROP TYPE IF EXISTS extractionstatus")
    op.execute("DROP TYPE IF EXISTS posttype")
    op.execute("DROP TYPE IF EXISTS platform")
    op.execute("DROP TYPE IF EXISTS creatortier")
