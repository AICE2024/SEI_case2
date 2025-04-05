
"""
This is the MAIN FILE that ties everything together - like the boss of our app!

What it does:
1. Creates the FastAPI app and connects all the parts (projects, files, outcomes)
2. Makes sure we have folders for storing files
3. Sets up the database tables when we start the app

Important stuff happening here:
- Combines all our routes (projects, files, outcomes) into one big app
- Creates a 'case_studies' folder if it doesn't exist
- Makes sure our database has all the right tables when we start
- Handles errors if something goes wrong during setup

Key things to know:
- The @app.on_event("startup") runs when the app starts
- We create 3 main tables: projects, outcomes, and files
- Files are linked to projects (they get deleted if project is deleted)
- All routes are organized under /projects, /files, /outcomes

Watch out for:
- If database setup fails, the app won't start properly
- The case_studies folder needs write permissions
- Changing table structures here affects the whole app
- Don't forget we're using ON DELETE CASCADE for related files/outcomes

Tip: If you add new models, remember to:
1. Add their tables here
2. Include their routers up top
3. Make sure folder paths are correct
"""



from fastapi import FastAPI, HTTPException
from endpoints import projects, files, outcomes
from models import ProjectCreate, Project, Outcome
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from pathlib import Path
from db import get_db_connection

app = FastAPI()

                                                                                # Add the different parts of the app
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(files.router, prefix="/files", tags=["files"])
app.include_router(outcomes.router, prefix="/outcomes", tags=["outcomes"])

                                                                                # Set up some folders
BASE_DIR = Path(__file__).parent.resolve()
CASE_STUDY_DIR = BASE_DIR / "case_studies"
os.makedirs(CASE_STUDY_DIR, exist_ok=True)

@app.on_event("startup")
def init_db():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
                                                                                # Create tables if they don't exist
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
                    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                    success_metrics JSONB,
                    challenges TEXT[],
                    overall_success BOOLEAN,
                    key_factors TEXT[],
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS files (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    filepath TEXT NOT NULL,
                    filetype TEXT,
                    uploaded_at TIMESTAMP DEFAULT NOW()
                );
            """)
            conn.commit()                                                       # Save changes
    except Exception as e:
        if conn:
            conn.rollback()                                                     # Undo changes if there's an error
        raise HTTPException(
            status_code=500,
            detail=f"Database initialization failed: {str(e)}"
        )
    finally:
        if conn:
            conn.close()                                                        # Close the connection
