
"""
This here module handles all the outcome tracking stuff for projects. Its like
keeping score of how projects are doing and what results they getting.

Main things it do:
1. Lets you add new outcomes to projects (like project results)
2. Get the latest outcome for a project
3. Update existing outcomes if things change
4. Delete outcomes if you dont need them no more

How it works:
- Stores outcomes in database connected to projects
- Uses json for the success metrics thingy
- Has some basic error checking but could maybe use more
- Theres some duplicate code in create that should maybe be fixed

Important notes:
- Dont forget to close db connections after using!
- The success_metrics gets converted to json string automatically
- When updating, you can just send the fields you wanna change
- Theres two ways to create outcomes for some reason (need to check why)

Watch out for:
- If project dont exist, it will error out
- The json stuff might break if you send bad data
- No auth checks so anyone can modify outcomes right now
"""



from fastapi import APIRouter, HTTPException                        # Import FastAPI utilities for routing and error handling
from models import Outcome, OutcomeCreate, OutcomeUpdate            # Import data models used for responses and requests
from db import get_db_connection                                    # Import the function to get the database connection
from datetime import datetime                                       # Import datetime for handling timestamps
from typing import List                                             # Import typing to work with lists
import json                                                         # Import json to handle data in JSON format

router = APIRouter()                                                # Initialize the router to define API endpoints

                                                                    # Endpoint to create a new outcome for a project
@router.post("/", response_model=OutcomeCreate)
def create_outcome(outcome: OutcomeCreate):
    conn = get_db_connection()                                      # Get the connection to the database
    try:
                                                                    # Open a cursor (a way to interact with the database)
        with conn.cursor() as cur:
                                                                    # SQL query to insert a new outcome for the project into the database
            cur.execute("""
                INSERT INTO outcomes (success_metrics, challenges, overall_success, key_factors, project_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *  # Return all data of the inserted row
            """, (
                json.dumps(outcome.success_metrics),                # Convert success_metrics to JSON
                outcome.challenges,                                 # Challenges faced in the project
                outcome.overall_success,                            # Whether the project was overall successful or not
                outcome.key_factors,                                # Key factors that influenced the outcome
                outcome.project_id                                  # Reference to the project ID
            ))
            result = cur.fetchone()                                 # Fetch the result of the insert query (i.e., the new outcome)
            conn.commit()                                           # Commit the transaction to save the changes in the database
            return result                                           # Return the inserted outcome

    except Exception as e:
        conn.rollback()                                             # If something goes wrong, roll back the transaction
        raise HTTPException(status_code=400, detail=str(e))         # Return an error with status 400
    finally:
        conn.close()                                                # Always close the connection to the database when done

                                                                    # Endpoint to get the most recent outcome for a given project by its ID
@router.get("/project/{project_id}", response_model=Outcome)
def get_project_outcome(project_id: int):
    conn = get_db_connection()                                      # Get the connection to the database
    try:
        with conn.cursor() as cur:
                                                                    # SQL query to get the most recent outcome for a specific project
            cur.execute("""
                SELECT id, project_id, success_metrics, challenges, 
                       overall_success, key_factors, created_at
                FROM outcomes
                WHERE project_id = %s
                ORDER BY created_at DESC  # Order outcomes by creation date, descending
                LIMIT 1  # Get only the most recent outcome
            """, (project_id,))                                     # Pass the project ID to the query
            outcome = cur.fetchone()                                # Fetch the outcome
            if not outcome:
                raise HTTPException(
                    status_code=404,
                    detail="No outcomes found for this project"
                )                                                   # If no outcome found, return a 404 error
            return Outcome(**outcome)                               # Return the outcome as an Outcome object

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))         # If an error occurs, return a 500 error
    finally:
        conn.close()                                                # Close the database connection

                                                                    # Endpoint to update an existing outcome by its ID
@router.put("/{outcome_id}", response_model=Outcome)
def update_outcome(outcome_id: int, outcome: OutcomeUpdate):
    conn = get_db_connection()                                      # Get the connection to the database
    try:
        with conn.cursor() as cur:
                                                                    # SQL query to update the outcome based on its ID
            cur.execute("""
                UPDATE outcomes SET
                    success_metrics = COALESCE(%s, success_metrics),  # Update success_metrics if provided, else keep existing
                    challenges = COALESCE(%s, challenges),  # Same for challenges
                    overall_success = COALESCE(%s, overall_success),  # Same for overall_success
                    key_factors = COALESCE(%s, key_factors)  # Same for key_factors
                WHERE id = %s  # Only update the outcome with the specified ID
                RETURNING id, project_id, success_metrics, challenges, 
                          overall_success, key_factors, created_at
            """, (
                outcome.success_metrics,                            # New success_metrics
                outcome.challenges,                                 # New challenges
                outcome.overall_success,                            # New overall_success
                outcome.key_factors,                                # New key_factors
                outcome_id                                          # The outcome ID to update
            ))
            result = cur.fetchone()                                 # Fetch the updated outcome
            if not result:
                raise HTTPException(status_code=404, detail="Outcome not found")  # If no outcome found, return error
            conn.commit()                                           # Commit the update to the database
            return Outcome(**result)                                # Return the updated outcome

    except Exception as e:
        conn.rollback()                                             # Roll back if something goes wrong
        raise HTTPException(status_code=400, detail=str(e))         # Return error if something goes wrong
    finally:
        conn.close()                                                # Always close the database connection

                                                                    # Endpoint to delete an outcome by its ID
@router.delete("/{outcome_id}", response_model=dict)
def delete_outcome(outcome_id: int):
    conn = get_db_connection()                                      # Get the connection to the database
    try:
        with conn.cursor() as cur:
                                                                    # SQL query to delete the outcome by its ID
            cur.execute("DELETE FROM outcomes WHERE id = %s RETURNING id", (outcome_id,))
            deleted_outcome = cur.fetchone()                        # Get the deleted outcome (if it exists)
            if not deleted_outcome:
                raise HTTPException(status_code=404, detail="Outcome not found")  # Return error if outcome doesn't exist
            conn.commit()                                           # Commit the delete operation
            return {"message": "Outcome deleted successfully"}      # Return success message

    except Exception as e:
        conn.rollback()                                             # Roll back if something goes wrong
        raise HTTPException(status_code=500, detail=str(e))         # Return error if something goes wrong
    finally:
        conn.close()                                                # Close the connection when done
