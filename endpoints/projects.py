"""
 This module handles all the project stuff - creating, listing, deleting projects,
 and also dealing with files that belong to projects.

 Main things it does:
 1. Lets you make new projects with all their details
 2. See list of all existing projects
 3. Upload files to projects (one or many at once)
 4. Delete whole projects including their files

 Important notes:
 - Files get stored in 'uploads' folder on server
 - When deleting project, it cleans up all its files too
 - The confirm=True thing is there so you don't delete by accident
 - Some error handling but might need more for real use
 Watch out for:
 - Don't forget to close db connections!
 - Big files might cause problems, need size limits maybe
 - File names with weird characters could break things
"""


from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from fastapi.responses import FileResponse
from models import Project, ProjectCreate
from db import get_db_connection
from typing import List, Optional
import os
from pathlib import Path

router = APIRouter()

                                                                    # make uploads folder if not exists, so we don’t get errors later when saving files
CASE_STUDY_DIR = Path("uploads")
CASE_STUDY_DIR.mkdir(exist_ok=True)

                                                                    # ---------------------------------------------
                                                                    # List all projects (newest ones show up first)
                                                                    # ---------------------------------------------
@router.get("/", response_model=List[Project])
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
            
                                                                    # fix any nulls so the frontend doesn’t freak out
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
            detail=f"Oops, error getting projects: {str(e)}"
        )
    finally:
        conn.close()

                                                                    # ---------------------------------------------
                                                                    # Create a new project
                                                                    # ---------------------------------------------
@router.post("/", response_model=Project)
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

                                                                    # ---------------------------------------------
                                                                    # Upload a single file to an existing or new project
                                                                    # ---------------------------------------------
@router.post("/upload/")
async def upload_case_study(
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    project_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
):
                                                                    # Must have either an existing project OR enough info to create a new one
    if project_id is None and (title is None or description is None):
        raise HTTPException(
            status_code=400,
            detail="Need either project_id OR title+description"
        )

                                                                    # simple check to make sure filename is okay
    if not file.filename or '/' in file.filename or '\\' in file.filename:
        raise HTTPException(status_code=400, detail="Bad filename")

    file_location = CASE_STUDY_DIR / file.filename
    
                                                                    # try saving the file to disk
    try:
        with open(file_location, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Couldn't save file: {str(e)}")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
                                                                    # If no project, make a new one with basic info
            if project_id is None:
                cur.execute("""
                    INSERT INTO projects (title, description, location)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (title, description, "unspecified"))
                project_id = cur.fetchone()["id"]
            else:
                                                                    # double-check the project actually exists
                cur.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="No project found")

                                                                    # Save file info in the database
            cur.execute("""
                INSERT INTO files (project_id, filename, filepath, filetype)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (
                project_id,
                file.filename,
                str(file_location),
                file.content_type
            ))
            
            conn.commit()
            return {
                "message": "File uploaded!",
                "project_id": project_id,
                "file_id": cur.fetchone()["id"]
            }
    except Exception as e:
        conn.rollback()
        if os.path.exists(file_location):
            os.remove(file_location)                                # cleanup if DB insert fails
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

                                                                    # ---------------------------------------------
                                                                    # Upload multiple files to one project
                                                                    # ---------------------------------------------
@router.post("/upload-multiple/")
async def upload_case_study_multiple(
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    project_id: Optional[int] = Form(None),
    files: List[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    if project_id is None and (title is None or description is None):
        raise HTTPException(
            status_code=400,
            detail="Need project_id OR title+description"
        )

    conn = get_db_connection()
    project_id_val = project_id
    saved_files = []
    file_ids = []
    
    try:
        with conn.cursor() as cur:
                                                                    # create new project if needed
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
                    raise HTTPException(status_code=404, detail="Project missing")

                                                                    # loop through all uploaded files
            for file in files:
                if not file.filename or '/' in file.filename or '\\' in file.filename:
                    continue                                        # skip weird filenames
                
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
                        RETURNING id
                    """, (
                        project_id_val,
                        file.filename,
                        str(file_location),
                        file.content_type
                    ))
                    file_ids.append(cur.fetchone()["id"])
                except Exception:
                    continue                                        # if one file fails, we keep going

            conn.commit()
            return {
                "message": f"Uploaded {len(saved_files)} files",
                "project_id": project_id_val,
                "file_ids": file_ids
            }
    except Exception as e:
        conn.rollback()
                                                                    # clean up any saved files if something goes wrong
        for file_path in saved_files:
            if os.path.exists(file_path):
                os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Upload messed up: {str(e)}")
    finally:
        conn.close()

                                                                    # ---------------------------------------------
                                                                    # Delete a project and all its files (if confirm=True)
                                                                    # ---------------------------------------------
@router.delete("/{project_id}/")
async def delete_project(project_id: int, confirm: bool = False):
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Gotta confirm=True to delete"
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
                                                                    # get file paths before we delete anything
            cur.execute("""
                SELECT id, filepath FROM files WHERE project_id = %s
            """, (project_id,))
            files = cur.fetchall()
            
                                                                    # try to remove the actual files from disk
            deleted_files = []
            for file in files:
                try:
                    if os.path.exists(file["filepath"]):
                        os.remove(file["filepath"])
                        deleted_files.append(file["id"])
                except OSError as e:
                    print(f"Whoops, couldn't delete file {file['id']}: {str(e)}")
            
                                                                    # remove file records from db
            if files:
                cur.execute("""
                    DELETE FROM files WHERE project_id = %s
                """, (project_id,))
            
                                                                    # now delete the project
            cur.execute("""
                DELETE FROM projects WHERE id = %s
                RETURNING id
            """, (project_id,))
            
            deleted_project = cur.fetchone()
            if not deleted_project:
                raise HTTPException(status_code=404, detail="No project found")
            
            conn.commit()
            
            return {
                "message": "Deleted project and files",
                "project_id": project_id,
                "files_deleted": len(deleted_files)
            }
            
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting: {str(e)}"
        )
    finally:
        conn.close()
