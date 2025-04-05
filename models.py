"""
This file defines all the data shapes our app uses - like templates for what info we need.

It's basically saying:
- "Here's what a Project should look like"
- "Here's what an Outcome should contain"

Project stuff:
- ProjectCreate: What you need to make a new project (title, dates, location etc.)
- Project: Full project details including database ID and timestamps

Outcome stuff: 
- OutcomeBase: Basic success/challenge info all outcomes share
- OutcomeCreate: What to send when creating new outcome (plus project ID)
- Outcome: Full outcome details with ID and timestamp  
- OutcomeUpdate: What you can change in an existing outcome

Key things to know:
- Optional fields mean you don't HAVE to provide them
- Dates/times are handled properly
- Some fields are lists (like hazard_types)
- The success_metrics is a flexible dictionary

Why this matters:
- Makes sure people send us data in the right format
- Documents what fields we expect
- Helps FastAPI validate data automatically
- Keeps our data consistent

Note: If you change these models, you might need to update:
- Database tables
- API endpoints
- Frontend forms
"""

from pydantic import BaseModel
from typing import Dict, Optional, List
from datetime import date, datetime

                                                # This file defines the structure and shape of our data
                                                # These models help FastAPI validate and organize input/output

                                                # ----------------------------
                                                # Project Models
                                                # ----------------------------

                                                # Model used when creating a new project (input only)
class ProjectCreate(BaseModel):
    title: str                                  # Project title
    description: str                            # Description of what the project is about
    location: str                               # Where the project is/was implemented
    start_date: date                            # When the project started
    end_date: Optional[date] = None             # (Optional) When it ended, if at all
    community_size: int                         # Number of people/households affected or involved
    hazard_types: List[str]                     # What kinds of climate/disaster hazards are addressed
    implementing_org: str                       # Who led or organized the project
    author: Optional[str] = None                # (Optional) Who entered or provided this case
    source: Optional[str] = None                # (Optional) Where the info came from (URL, report, etc.)

                                                # Model used when returning project data (output)
class Project(BaseModel):
    id: int                                     # Unique ID of the project (from DB)
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
    created_at: Optional[datetime] = None       # When the record was added to the system

                                                # ----------------------------
                                                # Outcome Models
                                                # ----------------------------

                                                # Shared base model for all outcome-related classes
class OutcomeBase(BaseModel):
    success_metrics: dict                       # Dict of key metrics with their numeric values (e.g. {"water_saved": 1000})
    challenges: List[str]                       # List of challenges the project faced
    overall_success: bool                       # Whether the project was considered a success overall
    key_factors: List[str]                      # Key things that helped make the project work (or not)

                                                # Model for creating a new outcome (input only)
class OutcomeCreate(OutcomeBase):
    project_id: int                             # Link outcome to a specific project by its ID

                                                # Model for reading/returning outcome data (output)
class Outcome(OutcomeBase):
    id: int                                     # Unique ID of the outcome entry
    project_id: int                             # Which project this outcome is connected to
    created_at: datetime                        # When this outcome was recorded

                                                # Model for updating existing outcome data (input only)
                                                # All fields are optional so you can update just one part
class OutcomeUpdate(BaseModel):
    success_metrics: Optional[dict] = None
    challenges: Optional[List[str]] = None
    overall_success: Optional[bool] = None
    key_factors: Optional[List[str]] = None

