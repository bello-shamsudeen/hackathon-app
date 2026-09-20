"""profile fields for the registration flow

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-08

Division 9A — adds the columns the consumer-facing registration + profile
screens need (account number, NIN, BVN, avatar, cold-start flag) and
backfills account numbers for the pre-existing Division 3 synthetic users so
the profile page works for the demo accounts too.

Mirrors backend_additions/migrations/002_profile_fields.sql, kept versioned
here rather than run as a raw ad-hoc ALTER.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS account_number TEXT UNIQUE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS nin TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS bvn TEXT")
    # base64 photo data URL, or NULL for the initials fallback
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_data_url TEXT")
    # drives the cold-start hint banner on the consumer Home screen
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_freshly_registered BOOLEAN DEFAULT FALSE")

    # Backfill account numbers for the existing synthetic users (Division 3) so
    # the profile page works for the pre-populated SEES HACK-style accounts too.
    op.execute(
        """
        UPDATE users
        SET account_number = LPAD((FLOOR(RANDOM() * 9999999999))::TEXT, 10, '0')
        WHERE account_number IS NULL
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_freshly_registered")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS avatar_data_url")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS bvn")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS nin")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS account_number")
