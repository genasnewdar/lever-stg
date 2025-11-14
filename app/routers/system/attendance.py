import logging
import math
from fastapi import APIRouter, HTTPException, Security, Query, Depends
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from enum import Enum
from datetime import datetime

from app.auth.auth import VerifyToken
from app.singleton import prisma

# Router setup
router = APIRouter(prefix="/api/v1/system/attendance", tags=["Employee Attendance"])
auth = VerifyToken()
logger = logging.getLogger("system_attendance")
logger.setLevel(logging.INFO)

# Office location constants (Peace Tower, Ulaanbaatar)
OFFICE_LATITUDE = 47.9162536
OFFICE_LONGITUDE = 106.902233
ALLOWED_RADIUS_METERS = 20  # Allow 20 meters radius from office

# --- ENUMS and Pydantic Models ---
class AttendanceTypeEnum(str, Enum):
    """Defines the type of attendance event (only Check-In/Out)."""
    CHECK_IN = "CHECK_IN"
    CHECK_OUT = "CHECK_OUT"

class LocationData(BaseModel):
    """Schema for GPS location data."""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    accuracy: Optional[float] = Field(None, ge=0, description="GPS accuracy in meters")
    
    @validator('latitude', 'longitude')
    def validate_coordinates(cls, v):
        if v is None:
            raise ValueError('Coordinates cannot be null')
        return v

class RecordAttendanceRequest(BaseModel):
    """Schema for recording a new attendance event."""
    event_type: AttendanceTypeEnum = Field(..., description="The type of attendance event being recorded (CHECK_IN or CHECK_OUT).")
    location: LocationData = Field(..., description="GPS coordinates for location verification")
    device_info: Optional[str] = Field(None, max_length=200, description="Optional device information")

class AttendanceEventResponse(BaseModel):
    """Schema for returning an attendance event detail."""
    id: str
    employee_id: int
    event_type: AttendanceTypeEnum
    event_time: datetime
    latitude: float
    longitude: float
    distance_from_office: float
    device_info: Optional[str]

# --- Helper Functions ---
def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the distance between two GPS coordinates using Haversine formula.
    Returns distance in meters.
    """
    # Convert latitude and longitude from degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = (math.sin(dlat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth's radius in meters
    earth_radius = 6371000
    distance = earth_radius * c
    
    return distance

def validate_office_location(latitude: float, longitude: float) -> tuple[bool, float]:
    """
    Validate if the provided coordinates are within allowed distance from office.
    Returns (is_valid, distance_from_office)
    """
    distance = calculate_distance(latitude, longitude, OFFICE_LATITUDE, OFFICE_LONGITUDE)
    is_within_range = distance <= ALLOWED_RADIUS_METERS
    
    return is_within_range, distance

# --- Dependency ---
async def verify_employee_access(auth_result: str = Security(auth.verify)):
    """Fetches the authenticated employee from the database."""
    try:
        auth0_id = auth_result["sub"]
        employee = await prisma.employee.find_first(where={"auth0_id": auth0_id})

        if not employee:
            logger.warning(f"Employee not found in database: {auth0_id}")
            raise HTTPException(status_code=404, detail="Employee not found")

        return employee
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying employee access: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# --- Routes ---

@router.post("/record", status_code=201, response_model=AttendanceEventResponse)
async def record_attendance(
    request: RecordAttendanceRequest,
    employee = Depends(verify_employee_access)
):
    """Allows an employee to record a check-in or check-out event with location validation."""
    try:
        # CRITICAL: Validate location before processing
        is_valid_location, distance_from_office = validate_office_location(
            request.location.latitude, 
            request.location.longitude
        )
        
        if not is_valid_location:
            logger.warning(
                f"Employee {employee.auth0_id} attempted {request.event_type.value} "
                f"from invalid location: {distance_from_office:.2f}m from office"
            )
            raise HTTPException(
                status_code=403, 
                detail=f"Check-in/out not allowed from this location. "
                       f"You are {distance_from_office:.0f}m from the office. "
                       f"Maximum allowed distance is {ALLOWED_RADIUS_METERS}m."
            )

        # Check GPS accuracy if provided
        if request.location.accuracy and request.location.accuracy > 50:
            logger.warning(
                f"Employee {employee.auth0_id} has low GPS accuracy: {request.location.accuracy}m"
            )
            # You might want to warn but still allow, or reject based on business rules
            # For now, we'll warn but proceed

        # Get the last attendance event to enforce alternation
        last_event = await prisma.attendanceevent.find_first(
            where={"employee_id": employee.id},
            order={"event_time": "desc"}
        )
        
        # Logic to enforce alternation (Critical for attendance accuracy)
        if last_event and last_event.event_type == request.event_type.value:
            action = "checked in" if request.event_type == AttendanceTypeEnum.CHECK_IN else "checked out"
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot record {request.event_type.value}. Employee is already {action}."
            )

        # Create the new attendance event
        new_event = await prisma.attendanceevent.create(
            data={
                "employee_id": employee.id,
                "event_type": request.event_type.value,
                "event_time": datetime.utcnow(),
                "latitude": request.location.latitude,
                "longitude": request.location.longitude,
                "distance_from_office": distance_from_office,
                "device_info": request.device_info
            }
        )

        logger.info(
            f"Employee {employee.auth0_id} recorded {request.event_type.value} "
            f"at {distance_from_office:.2f}m from office"
        )

        # Format response
        return AttendanceEventResponse(
            id=str(new_event.id),
            employee_id=new_event.employee_id,
            event_type=AttendanceTypeEnum(new_event.event_type),
            event_time=new_event.event_time,
            latitude=new_event.latitude,
            longitude=new_event.longitude,
            distance_from_office=new_event.distance_from_office,
            device_info=new_event.device_info
        )
    
    except HTTPException:
        raise # Re-raise controlled HTTP exceptions
    except Exception as e:
        logger.error(f"Error recording attendance for {employee.auth0_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to record attendance event")

@router.get("/history", response_model=List[AttendanceEventResponse])
async def get_my_attendance_history(
    employee = Depends(verify_employee_access),
    start_date: Optional[datetime] = Query(None, description="Filter from this date (inclusive)"),
    end_date: Optional[datetime] = Query(None, description="Filter up to this date (exclusive)"),
    per_page: int = Query(50, ge=1, le=200, description="Events per page"),
    page: int = Query(1, ge=1, description="Page number")
):
    """Retrieves the authenticated employee's attendance history."""
    try:
        skip = (page - 1) * per_page
        
        filters = {
            "employee_id": employee.id,
            "is_deleted": False # Good practice for soft deletion
        }
        
        # Date filtering logic
        if start_date or end_date:
            filters["event_time"] = {}
            if start_date:
                filters["event_time"]["gte"] = start_date
            if end_date:
                filters["event_time"]["lt"] = end_date

        history = await prisma.attendanceevent.find_many(
            where=filters,
            skip=skip,
            take=per_page,
            order={"event_time": "desc"}
        )
        
        # Format response
        formatted_history = []
        for event in history:
            formatted_history.append(AttendanceEventResponse(
                id=str(event.id),
                employee_id=event.employee_id,
                event_type=AttendanceTypeEnum(event.event_type),
                event_time=event.event_time,
                latitude=event.latitude,
                longitude=event.longitude,
                distance_from_office=event.distance_from_office,
                device_info=event.device_info
            ))
        
        logger.info(f"Employee {employee.auth0_id} retrieved attendance history.")
        
        return formatted_history

    except Exception as e:
        logger.error(f"Error retrieving history for {employee.auth0_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve attendance history")

@router.get("/office-info")
async def get_office_location_info(employee = Depends(verify_employee_access)):
    """Returns office location information for client-side validation."""
    return {
        "status": "success",
        "data": {
            "office_location": {
                "latitude": OFFICE_LATITUDE,
                "longitude": OFFICE_LONGITUDE,
                "allowed_radius_meters": ALLOWED_RADIUS_METERS,
                "address": "Peace Tower, ЧД - 3 хороо, Улаанбаатар 15172"
            }
        }
    }