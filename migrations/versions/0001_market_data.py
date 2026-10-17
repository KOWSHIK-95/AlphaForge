"""Create the market data table."""

from alembic import op
import sqlalchemy as sa


revision = "0001_market_data"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_data",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=True),
        sa.Column("adj_close", sa.Float(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.CheckConstraint("open IS NULL OR open > 0", name="ck_market_data_open_positive"),
        sa.CheckConstraint("high IS NULL OR high > 0", name="ck_market_data_high_positive"),
        sa.CheckConstraint("low IS NULL OR low > 0", name="ck_market_data_low_positive"),
        sa.CheckConstraint("close IS NULL OR close > 0", name="ck_market_data_close_positive"),
        sa.CheckConstraint(
            "adj_close IS NULL OR adj_close > 0",
            name="ck_market_data_adj_close_positive",
        ),
        sa.CheckConstraint(
            "volume IS NULL OR volume >= 0",
            name="ck_market_data_volume_nonnegative",
        ),
        sa.PrimaryKeyConstraint("date", "ticker", name="pk_market_data"),
    )


def downgrade() -> None:
    op.drop_table("market_data")
