-- Division 9A-revised — profile fields for registration flow.
-- Run via Alembic (see Claude Code prompt) so this stays versioned, not a
-- raw ad-hoc ALTER.

ALTER TABLE users ADD COLUMN IF NOT EXISTS account_number TEXT UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS nin TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS bvn TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_data_url TEXT; -- base64 photo, or NULL for initials fallback
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_freshly_registered BOOLEAN DEFAULT FALSE; -- drives the cold-start hint banner

-- Backfill account numbers for existing synthetic users (Division 3) so
-- the profile page works for the pre-populated SEES HACKS-style accounts too.
UPDATE users
SET account_number = LPAD((FLOOR(RANDOM() * 9999999999))::TEXT, 10, '0')
WHERE account_number IS NULL;
