import psycopg2
from psycopg2.extras import RealDictCursor
import os

                                                                # Configuration for PostgreSQL database
DB_NAME = "projects_db"
DB_USER = "admin"
DB_PASSWORD = "securepassword"
DB_HOST = "localhost"
DB_PORT = 5432

                                                                # Directory to store uploaded case study files
CASE_STUDY_DIR = "SEI_case2/case_studies"
os.makedirs(CASE_STUDY_DIR, exist_ok=True)

def get_db_connection():
    """
    Returns a connection object to the PostgreSQL database.
    """
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        cursor_factory=RealDictCursor
    )

def init_db():
    """
    Initializes the database by creating necessary tables.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    location TEXT,
                    start_date DATE,
                    end_date DATE,
                    community_size INTEGER,
                    hazard_types TEXT[],
                    implementing_org TEXT,
                    author TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS outcomes (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER REFERENCES projects(id),
                    success_metrics JSONB,
                    challenges TEXT[],
                    overall_success BOOLEAN,
                    key_factors TEXT[],
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS files (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER REFERENCES projects(id),
                    filename TEXT NOT NULL,
                    filepath TEXT NOT NULL,
                    filetype TEXT,
                    uploaded_at TIMESTAMP DEFAULT NOW()
                );
            """)
            conn.commit()
    finally:
        conn.close()
