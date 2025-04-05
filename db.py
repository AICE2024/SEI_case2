
"""
This file is all about connecting to our database and handling file uploads. 
It's like the bridge between our app and the database.

Main jobs:
1. Sets up where we'll keep uploaded files (in an 'upload' folder)
2. Creates the connection to our PostgreSQL database
3. Makes database results come back as easy-to-use dictionaries
4. Handles database connection errors nicely

Important stuff to know:
- It uses psycopg2 to talk to PostgreSQL
- The RealDictCursor makes database rows come as dicts (way easier to work with)
- If connection fails, it gives back a 500 error with details
- You gotta close connections when you're done with them!

Watch out for:
- The credentials are hardcoded (not great for real production)
- Make sure the 'upload' folder exists before saving files
- Database might get overwhelmed if too many connections stay open
- No retry logic if database is temporarily unavailable

Example usage:
Just call get_db_connection() when you need to talk to database,
and don't forget to close it after! Like:

conn = get_db_connection()
try:
    # do your database stuff here
finally:
    conn.close()  # SUPER important!
""" 


                                            # db.py - Database connection setup
import psycopg2
from psycopg2.extras import RealDictCursor  # For getting results as dictionaries
from fastapi import HTTPException
import os

                                            # Where we'll store uploaded files - creates path like "/app/upload"
CASE_STUDY_DIR = os.path.join(os.getcwd(), "upload")

                                            # Gets a connection to our PostgreSQL database
def get_db_connection():
    try:
        return psycopg2.connect(
            dbname="projects_db",           # Our database name
            user="admin",                   # Database username
            password="securepassword",      # Database password
            host="localhost",               # Database server location
            port=5432,                      # Default PostgreSQL port
            cursor_factory=RealDictCursor   # Makes results come as dicts
        )
    except psycopg2.Error as e:
                                            # If connection fails, return 500 error with details
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {str(e)}"
        )
    
# Note: Remember to close connections after using them!
# Good pattern: 
# conn = get_db_connection()
# try:
#    # use connection
# finally:
#    conn.close()