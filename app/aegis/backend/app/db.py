"""
Shared Postgres connection helper — same plain psycopg2 pattern app/main.py
uses for /health, so routers don't introduce a second, inconsistent way of
talking to the database (e.g. a SQLAlchemy session). SQLAlchemy is used only
by Alembic (migrations/env.py) to apply schema, never at request time.
"""
import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://aegis:aegis_dev_pw@localhost:5432/aegis")


def get_connection():
    return psycopg2.connect(DATABASE_URL)
