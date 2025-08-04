# backend/app/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class AppointmentBase(BaseModel):
    reason_for_visit: str
    appointment_type_id: int
    client_id: int
    patient_id: int

class AppointmentCreate(AppointmentBase):
    start_time: datetime
    end_time: datetime
    vet_id: int
    room_id: int

class Appointment(AppointmentBase):
    id: int
    start_time: datetime
    end_time: datetime
    vet_id: int
    room_id: int

    class Config:
        from_attributes = True

class VetBase(BaseModel):
    name: str

class VetCreate(VetBase):
    pass

class Vet(VetBase):
    id: int
    appointments: List[Appointment] = []

    class Config:
        from_attributes = True

class RoomBase(BaseModel):
    name: str

class RoomCreate(RoomBase):
    pass

class Room(RoomBase):
    id: int
    appointments: List[Appointment] = []

    class Config:
        from_attributes = True

class AppointmentTypeBase(BaseModel):
    name: str
    duration_minutes: int

class AppointmentTypeCreate(AppointmentTypeBase):
    pass

class AppointmentType(AppointmentTypeBase):
    id: int

    class Config:
        from_attributes = True

class ClientBase(BaseModel):
    name: str
    email: str
    phone_number: str

class ClientCreate(ClientBase):
    pass

class Client(ClientBase):
    id: int

    class Config:
        from_attributes = True

class PatientBase(BaseModel):
    name: str
    species: str
    breed: str
    age: int
    owner_id: int

class PatientCreate(PatientBase):
    pass

class Patient(PatientBase):
    id: int

    class Config:
        from_attributes = True

class RankedSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    vet_id: int
    vet_name: str
    room_id: int
    room_name: str
    score: float