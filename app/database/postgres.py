import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Optional

from app.config import settings

_connection_pool: Optional[pool.ThreadedConnectionPool] = None


def get_pool() -> pool.ThreadedConnectionPool:
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            dbname=settings.DATABASE_NAME,
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD,
        )
    return _connection_pool


@contextmanager
def get_db_connection():
    pool_obj = get_pool()
    conn = pool_obj.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool_obj.putconn(conn)


@contextmanager
def get_db_cursor(auto_commit: bool = False):
    pool_obj = get_pool()
    conn = pool_obj.getconn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        yield cur
        if auto_commit:
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        pool_obj.putconn(conn)


def init_db():
    """Create all required tables."""
    with get_db_cursor(auto_commit=True) as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                full_name VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                filename VARCHAR(500) NOT NULL,
                filepath TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                page_count INTEGER DEFAULT 0,
                status VARCHAR(50) DEFAULT 'pending',
                pinecone_ids TEXT[] DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                items JSONB NOT NULL DEFAULT '[]',
                total_amount DECIMAL(10, 2) DEFAULT 0.00,
                status VARCHAR(50) DEFAULT 'pending',
                special_instructions TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_history_user_id
            ON chat_history(user_id);
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_user_id
            ON orders(user_id);
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_user_id
            ON documents(user_id);
        """)


def close_pool():
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
