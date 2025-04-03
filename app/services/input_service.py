from datetime import datetime
from typing import Tuple, List
from fastapi import HTTPException

def parse_inputs(date_string: str, participants: str) -> Tuple[datetime, List[str]]:
    """
    Parse and validate inputs from the API request
    
    Args:
        date_string: String in format "Y-m-d H:M"
        participants: Comma-separated list of participant UUIDs
    
    Returns:
        Tuple of (parsed_datetime, list_of_participants)
    
    Raises:
        HTTPException: If date format is invalid
    """
    # Parse date string
    date_time = datetime.now()
    if date_string:
        try:
            date_time = datetime.strptime(date_string, "%Y-%m-%d %H:%M")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD HH:MM")
    
    # Parse participants
    participant_list = []
    if participants and participants.strip():
        participant_list = participants.split(",")
    
    return date_time, participant_list