                                                                           # main.py - FastAPI app for uploading files and managing projects with PostgreSQL
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from pathlib import Path

app = FastAPI()

                                                                            # -----------------------------
                                                                            # Setup stuff (folders and DB)
                                                                            # -----------------------------

                                                                            # Figure out the folder where we’ll store uploaded files
BASE_DIR = Path(__file__).parent.resolve()
CASE_STUDY_DIR = BASE_DIR / "case_studies"
os.makedirs(CASE_STUDY_DIR, exist_ok=True)                                  # Make folder if it doesn’t exist

                                                                            # Connect to the database
def get_db_connection():
    try:
        return psycopg2.connect(
            dbname="projects_db",
            user="admin",
            password="securepassword",
            host="localhost",
            port=5432,
            cursor_factory=RealDictCursor
        )
    except psycopg2.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Couldn't connect to the database: {str(e)}"
        )

                                                                            # -----------------------------
                                                                            # The shapes of the data (models)
                                                                            # -----------------------------

class ProjectCreate(BaseModel):
    title: str
    description: str
    location: str
    start_date: date
    end_date: Optional[date] = None
    community_size: int
    hazard_types: List[str]
    implementing_org: str
    author: Optional[str] = None
    source: Optional[str] = None

class Project(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    community_size: Optional[int] = None
    hazard_types: Optional[List[str]] = None
    implementing_org: Optional[str] = None
    author: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[datetime] = None

class Outcome(BaseModel):
    project_id: int
    success_metrics: dict
    challenges: List[str]
    overall_success: bool
    key_factors: List[str]

                                                                            # -----------------------------
                                                                            # Setup DB tables when app starts
                                                                            # -----------------------------

@app.on_event("startup")
def init_db():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
                                                                            # Make sure the tables exist (create them if not)
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
            conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error setting up DB: {str(e)}"
        )
    finally:
        if conn:
            conn.close()

                                                                            # -----------------------------
                                                                            # Save new project to the database
                                                                            # -----------------------------

@app.post("/projects/", response_model=Project)
def create_project(project: ProjectCreate):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO projects (
                    title, description, location, 
                    start_date, end_date, community_size, 
                    hazard_types, implementing_org, author, source
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (
                project.title, project.description, project.location,
                project.start_date, project.end_date, project.community_size,
                project.hazard_types, project.implementing_org,
                project.author, project.source
            ))
            result = cur.fetchone()
            conn.commit()
            return result
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

                                                                            # -----------------------------
                                                                            # Show all the projects we have
                                                                            # -----------------------------

@app.get("/projects/", response_model=List[Project])
def list_projects():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    id,
                    COALESCE(title, '') as title,
                    description,
                    location,
                    start_date,
                    end_date,
                    COALESCE(community_size, 0) as community_size,
                    COALESCE(hazard_types, '{}') as hazard_types,
                    COALESCE(implementing_org, '') as implementing_org,
                    author,
                    source,
                    created_at
                FROM projects 
                ORDER BY created_at DESC
            """)
            projects = cur.fetchall()

            # Fill in any missing values
            for project in projects:
                if project['hazard_types'] is None:
                    project['hazard_types'] = []
                if project['community_size'] is None:
                    project['community_size'] = 0
                if project['implementing_org'] is None:
                    project['implementing_org'] = ""

            return projects
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Couldn't fetch projects: {str(e)}"
        )
    finally:
        conn.close()

                                                                            # -----------------------------
                                                                            # See files for a project
                                                                            # -----------------------------

@app.get("/projects/{project_id}/files/")
def list_project_files(project_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, filename, filetype, uploaded_at
                FROM files
                WHERE project_id = %s
                ORDER BY uploaded_at DESC
            """, (project_id,))
            return cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

                                                                            # -----------------------------
                                                                            # Download a file by ID
                                                                            # -----------------------------

@app.get("/files/{file_id}/download/")
def download_file(file_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT filename, filepath
                FROM files
                WHERE id = %s
            """, (file_id,))
            file = cur.fetchone()

            if not file:
                raise HTTPException(status_code=404, detail="File not found")
            if not os.path.exists(file["filepath"]):
                raise HTTPException(status_code=404, detail="File not found on disk")

            return FileResponse(
                path=file["filepath"],
                filename=file["filename"],
                media_type="application/octet-stream"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

                                                                            # -----------------------------
                                                                            # Upload a single file to a project
                                                                            # -----------------------------

@app.post("/upload_case_study/")
async def upload_case_study(
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    project_id: Optional[int] = Form(None),
    file: UploadFile = File(...)
):
                                                                            # Either attach to a project or make a new one
    if project_id is None and (title is None or description is None):
        raise HTTPException(
            status_code=400,
            detail="Either project_id or title/description is needed"
        )

    if not file.filename or '/' in file.filename or '\\' in file.filename:
        raise HTTPException(status_code=400, detail="Bad filename")

    file_location = CASE_STUDY_DIR / file.filename

    try:
        with open(file_location, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if project_id is None:
                cur.execute("""
                    INSERT INTO projects (title, description, location)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (title, description, "unspecified"))
                project_id = cur.fetchone()["id"]
            else:
                cur.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="No such project")

            cur.execute("""
                INSERT INTO files (project_id, filename, filepath, filetype)
                VALUES (%s, %s, %s, %s)
            """, (
                project_id,
                file.filename,
                str(file_location),
                file.content_type
            ))

            conn.commit()
            return {
                "message": "File uploaded!",
                "project_id": project_id
            }
    except Exception as e:
        conn.rollback()
        if os.path.exists(file_location):
            os.remove(file_location)
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

                                                                            # -----------------------------
                                                                            # Upload more than one file
                                                                            # -----------------------------

@app.post("/upload_case_study_multiple/")
async def upload_case_study_multiple(
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    project_id: Optional[int] = Form(None),
    files: List[UploadFile] = File(...)
):
    if not files:
        raise HTTPException(status_code=400, detail="No files sent")

    if project_id is None and (title is None or description is None):
        raise HTTPException(
            status_code=400,
            detail="Need project_id or title+description"
        )

    conn = get_db_connection()
    project_id_val = project_id
    saved_files = []

    try:
        with conn.cursor() as cur:
            if project_id is None:
                cur.execute("""
                    INSERT INTO projects (title, description, location)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (title, description, "multiple_files"))
                project_id_val = cur.fetchone()["id"]
            else:
                cur.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="No such project")

            for file in files:
                if not file.filename or '/' in file.filename or '\\' in file.filename:
                    continue  # skip this one

                file_location = CASE_STUDY_DIR / file.filename

                try:
                    with open(file_location, "wb") as buffer:
                        content = await file.read()
                        buffer.write(content)
                    saved_files.append(file_location)

                    cur.execute("""
                        INSERT INTO files (
                            project_id, filename, filepath, filetype
                        )
                        VALUES (%s, %s, %s, %s)
                    """, (
                        project_id_val,
                        file.filename,
                        str(file_location),
                        file.content_type
                    ))
                except Exception:
                    continue

            conn.commit()
            return {
                "message": f"{len(saved_files)} files uploaded",
                "project_id": project_id_val
            }
    except Exception as e:
        conn.rollback()
        for file_path in saved_files:
            if os.path.exists(file_path):
                os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Something went wrong: {str(e)}")
    finally:
        conn.close()

                                                                            # -----------------------------
                                                                            # Delete a file (by ID)
                                                                            # -----------------------------

@app.delete("/files/{file_id}/")
async def delete_file(file_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT filepath FROM files WHERE id = %s
            """, (file_id,))
            file = cur.fetchone()

            if not file:
                raise HTTPException(status_code=404, detail="File not found")

            try:
                if os.path.exists(file["filepath"]):
                    os.remove(file["filepath"])
            except OSError as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Could not delete file: {str(e)}"
                )

            cur.execute("""
                DELETE FROM files WHERE id = %s
            """, (file_id,))

            conn.commit()
            return {"message": "File deleted"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
