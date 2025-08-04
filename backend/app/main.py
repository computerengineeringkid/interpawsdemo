# backend/app/main.py
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from . import crud, models, schemas
from .database import SessionLocal, engine
from datetime import datetime, timedelta
import httpx
import json
from typing import Optional

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/appointments/", response_model=schemas.Appointment)
def create_appointment(appointment: schemas.AppointmentCreate, db: Session = Depends(get_db)):
    return crud.create_appointment(db=db, appointment=appointment)

@app.get("/appointments/", response_model=list[schemas.Appointment])
def read_appointments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    appointments = crud.get_appointments(db, skip=skip, limit=limit)
    return appointments

@app.get("/find_slots/")
async def find_slots(reason_for_visit: str, appointment_type_id: int, db: Session = Depends(get_db)):
    today = datetime.now().date()
    start_of_day = datetime.combine(today, datetime.min.time()).replace(hour=9)
    end_of_day = datetime.combine(today, datetime.min.time()).replace(hour=17)

    vets = crud.get_vets(db)
    rooms = crud.get_rooms(db)
    appointment_type = crud.get_appointment_type(db, appointment_type_id)
    if not appointment_type:
        raise HTTPException(status_code=404, detail="Appointment type not found")

    duration = timedelta(minutes=appointment_type.duration_minutes)
    
    existing_appointments = crud.get_appointments_for_day(db, today)
    
    available_slots = []
    
    current_time = start_of_day
    while current_time + duration <= end_of_day:
        slot_end_time = current_time + duration
        
        for vet in vets:
            for room in rooms:
                is_vet_busy = any(
                    apt.vet_id == vet.id and 
                    not (slot_end_time <= apt.start_time or current_time >= apt.end_time)
                    for apt in existing_appointments
                )
                
                is_room_busy = any(
                    apt.room_id == room.id and
                    not (slot_end_time <= apt.start_time or current_time >= apt.end_time)
                    for apt in existing_appointments
                )

                if not is_vet_busy and not is_room_busy:
                    available_slots.append({
                        "start_time": current_time.isoformat(),
                        "end_time": slot_end_time.isoformat(),
                        "vet_id": vet.id,
                        "vet_name": vet.name,
                        "room_id": room.id,
                        "room_name": room.name
                    })

        current_time += timedelta(minutes=15)

    prompt = f"""
    A client wants to book an appointment for the following reason: '{reason_for_visit}'.
    The available slots are:
    {json.dumps(available_slots, indent=2)}

    Please rank these slots based on suitability. The ideal time is usually earlier in the day.
    Return a JSON list of ranked slots with a score from 0.0 to 1.0.
    The format should be:
    [
        {{
            "start_time": "...",
            "end_time": "...",
            "vet_id": ...,
            "vet_name": "...",
            "room_id": ...,
            "room_name": "...",
            "score": ...
        }}
    ]
    """

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post("http://host.docker.internal:11434/api/generate", json={
                "model": "llama2",
                "prompt": prompt,
                "stream": False,
                "format": "json"
            }, timeout=60.0)
        
        response.raise_for_status()
        ranked_slots_data = json.loads(response.json()['response'])

        # Persist ranked slots
        crud.clear_ranked_slots(db)
        for slot_data in ranked_slots_data:
            slot_data['start_time'] = datetime.fromisoformat(slot_data['start_time'])
            slot_data['end_time'] = datetime.fromisoformat(slot_data['end_time'])
            slot = schemas.RankedSlot(**slot_data)
            crud.create_ranked_slot(db, slot)

        return ranked_slots_data
    except (httpx.RequestError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"Error contacting AI model: {e}")

@app.post("/book_appointment/")
def book_appointment(slot: schemas.RankedSlot, reason_for_visit: str, appointment_type_id: int, client_id: int, patient_id: int, db: Session = Depends(get_db)):
    appointment_create = schemas.AppointmentCreate(
        start_time=slot.start_time,
        end_time=slot.end_time,
        vet_id=slot.vet_id,
        room_id=slot.room_id,
        reason_for_visit=reason_for_visit,
        appointment_type_id=appointment_type_id,
        client_id=client_id,
        patient_id=patient_id,
    )
    try:
        created_appointment = crud.create_appointment(db, appointment_create)
        crud.clear_ranked_slots(db)
        return {"message": "Appointment booked successfully", "appointment": created_appointment}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/clients/", response_model=schemas.Client)
def create_client(client: schemas.ClientCreate, db: Session = Depends(get_db)):
    db_client = crud.get_client_by_email(db, email=client.email)
    if db_client:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_client(db=db, client=client)

@app.get("/clients/", response_model=list[schemas.Client])
def read_clients(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    clients = crud.get_clients(db, skip=skip, limit=limit)
    return clients

@app.post("/patients/", response_model=schemas.Patient)
def create__patient(patient: schemas.PatientCreate, db: Session = Depends(get_db)):
    return crud.create_patient(db=db, patient=patient)

@app.get("/patients/", response_model=list[schemas.Patient])
def read_patients(owner_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    if owner_id:
        return crud.get_patients_by_owner(db, owner_id=owner_id)
    return crud.get_patients(db)

@app.get("/appointment_types/", response_model=list[schemas.AppointmentType])
def read_appointment_types(db: Session = Depends(get_db)):
    return crud.get_appointment_types(db)