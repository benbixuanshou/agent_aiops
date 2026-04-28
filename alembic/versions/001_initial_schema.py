"""Initial schema — sessions, messages, tool_cache, long_term_memory.

Revision ID: 001
Revises: None
Create Date: 2026-04-28
"""

revision = "001"
down_revision = None


def upgrade():
    op = __import__("alembic.op", fromlist=["op"]).op
    op.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id VARCHAR(64) PRIMARY KEY,
            created_at DOUBLE NOT NULL,
            updated_at DOUBLE NOT NULL
        ) ENGINE=InnoDB
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(64) NOT NULL,
            role VARCHAR(16) NOT NULL,
            content TEXT NOT NULL,
            created_at DOUBLE NOT NULL,
            INDEX idx_session (session_id)
        ) ENGINE=InnoDB
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS tool_cache (
            cache_key VARCHAR(128) PRIMARY KEY,
            result TEXT NOT NULL,
            created_at DOUBLE NOT NULL,
            ttl INT DEFAULT 300
        ) ENGINE=InnoDB
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS long_term_memory (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            query TEXT NOT NULL,
            finding TEXT NOT NULL,
            created_at DOUBLE NOT NULL
        ) ENGINE=InnoDB
    """)


def downgrade():
    op = __import__("alembic.op", fromlist=["op"]).op
    op.execute("DROP TABLE IF EXISTS long_term_memory")
    op.execute("DROP TABLE IF EXISTS tool_cache")
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS sessions")
