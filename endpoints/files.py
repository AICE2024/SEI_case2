from fastapi import APIRouter, HTTPException, File, UploadFile, Form            # Import FastAPI tools for file handling
from fastapi.responses import FileResponse                                      # Import response utility for serving files
import os                                                                       # Import OS utilities for file handling
from typing import Optional, List                                               # Import optional types and list for input validation
from pathlib import Path                                                        # For handling file paths in a clean way
from db import get_db_connection                                                # Import the database connection function
from db import CASE_STUDY_DIR                                                   # Import the directory where files will be stored

                                                                                # Ensure the 'uploads' folder exists, create it if it doesn't
CASE_STUDY_DIR = Path("uploads").resolve()                                      # Get the full path of the 'uploads' folder
CASE_STUDY_DIR.mkdir(exist_ok=True)                                             # Create the folder if it doesn't exist yet

router = APIRouter()                                                            # Initialize the router to define API endpoints

                                                                                # This endpoint returns a list of all files for a given project
@router.get("/projects/{project_id}/files/")
def list_project_files(project_id: int):
    conn = get_db_connection()                                                  # Get the connection to the database
    try:
        with conn.cursor() as cur:
                                                                                # SQL query to fetch all files for the specified project, ordered by upload date
            cur.execute("""
                SELECT id, filename, filetype, uploaded_at
                FROM files
                WHERE project_id = %s
                ORDER BY uploaded_at DESC
            """, (project_id,))
            return cur.fetchall()                                               # Return the list of files for the project
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))                     # Return error if something goes wrong
    finally:
        conn.close()                                                            # Always close the database connection when done

                                                                                # This endpoint allows downloading a file by its ID
@router.get("/{file_id}/download/")
def download_file(file_id: int):
    conn = get_db_connection()                                                  # Get the connection to the database
    try:
        with conn.cursor() as cur:
                                                                                # SQL query to fetch the file's name and location based on its ID
            cur.execute("""
                SELECT filename, filepath
                FROM files
                WHERE id = %s
            """, (file_id,))
            file = cur.fetchone()                                               # Fetch the file information
            
            if not file:
                raise HTTPException(status_code=404, detail="File not found")   # Return error if file doesn't exist
                
            if not os.path.exists(file["filepath"]):
                raise HTTPException(status_code=404, detail="File not found")   # Check if file is on server
                
            return FileResponse(
                path=file["filepath"],                                          # Serve the file from its path
                filename=file["filename"],                                      # Provide the original filename
                media_type="application/octet-stream"                           # Return the file as a binary stream
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))                     # Return error if something goes wrong
    finally:
        conn.close()                                                            # Always close the connection to the database

                                                                                # This endpoint allows uploading a single file, and can create a new project if needed
@router.post("/upload/")
async def upload_case_study(
    title: Optional[str] = Form(None),                                          # Title of the project, optional
    description: Optional[str] = Form(None),                                    # Description of the project, optional
    project_id: Optional[int] = Form(None),                                     # Project ID, optional
    file: UploadFile = File(...),                                               # The file to be uploaded, required
):
                                                                                # Check if either project_id or title+description is provided
    if project_id is None and (title is None or description is None):
        raise HTTPException(
            status_code=400,
            detail="Need project_id OR title+description"                       # Error if neither are provided
        )

                                                                                # Check if the filename is valid (no slashes, no empty names)
    if not file.filename or '/' in file.filename or '\\' in file.filename:
        raise HTTPException(status_code=400, detail="Bad filename")

    file_location = CASE_STUDY_DIR / file.filename                              # Define the file's path in the 'uploads' directory
    
    try:
                                                                                # Save the file to the server
        with open(file_location, "wb") as buffer:
            content = await file.read()                                         # Read the file content
            buffer.write(content)                                               # Write the content to the file
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")  # Error if file can't be saved

    conn = get_db_connection()                                                  # Get the connection to the database
    try:
        with conn.cursor() as cur:
                                                                                # If no project_id, create a new project in the database
            if project_id is None:
                cur.execute("""
                    INSERT INTO projects (title, description, location)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (title, description, "unspecified"))
                project_id = cur.fetchone()["id"]                               # Get the new project ID
            else:
                cur.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
                if not cur.fetchone():                                          # Check if the project exists
                    raise HTTPException(status_code=404, detail="Project not found")

                                                                                # Insert the file's details into the database
            cur.execute("""
                INSERT INTO files (project_id, filename, filepath, filetype)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (
                project_id,
                file.filename,
                str(file_location),
                file.content_type                                               # Store file type (MIME type)
            ))
            
            conn.commit()                                                       # Commit the transaction to save changes
            return {
                "message": "File uploaded!",                                    # Success message
                "project_id": project_id,
                "file_id": cur.fetchone()["id"]                                 # Return the file ID
            }
    except Exception as e:
        conn.rollback()                                                         # Rollback if something goes wrong
        if os.path.exists(file_location):                                       # Remove file if it was saved
            os.remove(file_location)
        raise HTTPException(status_code=400, detail=str(e))                     # Return error
    finally:
        conn.close()                                                            # Always close the database connection

                                                                                # This endpoint allows uploading multiple files at once
@router.post("/upload-multiple/")
async def upload_case_study_multiple(
    title: Optional[str] = Form(None),                                          # Title of the project, optional
    description: Optional[str] = Form(None),                                    # Description of the project, optional
    project_id: Optional[int] = Form(None),                                     # Project ID, optional
    files: List[UploadFile] = File(...),                                        # List of files to upload, required
):
    if not files:                                                               # If no files are provided
        raise HTTPException(status_code=400, detail="No files")

                                                                                # Check if either project_id or title+description is provided
    if project_id is None and (title is None or description is None):
        raise HTTPException(
            status_code=400,
            detail="Need project_id OR title+description"
        )

    conn = get_db_connection()                                                  # Get the connection to the database
    project_id_val = project_id
    saved_files = []                                                            # List to track successfully saved files
    file_ids = []                                                               # List to track the IDs of successfully uploaded files
    
    try:
        with conn.cursor() as cur:
                                                                                # If no project_id, create a new project in the database
            if project_id is None:
                cur.execute("""
                    INSERT INTO projects (title, description, location)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (title, description, "multiple_files"))
                project_id_val = cur.fetchone()["id"]                           # Get the new project ID
            else:
                cur.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
                if not cur.fetchone():                                          # Check if the project exists
                    raise HTTPException(status_code=404, detail="Project not found")

                                                                                # Iterate through the list of files and upload each one
            for file in files:
                if not file.filename or '/' in file.filename or '\\' in file.filename:
                    continue                                                    # Skip invalid filenames
                    
                file_location = CASE_STUDY_DIR / file.filename                  # Define the file's path
                
                try:
                                                                                # Save the file to the server
                    with open(file_location, "wb") as buffer:
                        content = await file.read()                             # Read the file content
                        buffer.write(content)                                   # Write the content to the file
                    saved_files.append(file_location)                           # Track the saved file
                    
                                                                                # Insert the file details into the database
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
                    file_ids.append(cur.fetchone()["id"])                       # Track the file ID
                except Exception:
                    continue                                                    # Skip files that fail to upload

            conn.commit()                                                       # Commit the transaction to save changes
            return {
                "message": f"{len(saved_files)} files uploaded ok",             # Success message
                "project_id": project_id_val,
                "file_ids": file_ids                                            # Return the IDs of the uploaded files
            }
    except Exception as e:
        conn.rollback()                                                         # Rollback if something goes wrong
                                                                                # Remove any files that were successfully saved before the error
        for file_path in saved_files:
            if os.path.exists(file_path):
                os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")  # Return error
    finally:
        conn.close()                                                            # Always close the database connection
