# backend/app/crud.py
from sqlalchemy.orm import Session
from sqlalchemy import text
from . import models, schemas
from datetime import date

def get_vets(db: Session):
    return db.query(models.Vet).all()

def get_rooms(db: Session):
    return db.query(models.Room).all()

def get_appointments_for_day(db: Session, day: date):
    start_of_day = day.strftime('%Y-%m-%d 00:00:00')
    end_of_day = day.strftime('%Y-%m-%d 23:59:59')
    return db.query(models.Appointment).filter(
        models.Appointment.start_time.between(start_of_day, end_of_day)
    ).all()

def create_appointment(db: Session, appointment: schemas.AppointmentCreate):
    db_appointment = models.Appointment(**appointment.model_dump())
    db.add(db_appointment)
    db.commit()
    db.refresh(db_appointment)
    return db_appointment

def get_appointments(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Appointment).offset(skip).limit(limit).all()

def clear_ranked_slots(db: Session):
    db.query(models.RankedSlot).delete()
    db.commit()

def create_ranked_slot(db: Session, slot: schemas.RankedSlot):
    db_slot = models.RankedSlot(**slot.model_dump())
    db.add(db_slot)
    db.commit()
    db.refresh(db_slot)
    return db_slot

# New CRUD functions
def get_client(db: Session, client_id: int):
    return db.query(models.Client).filter(models.Client.id == client_id).first()

def get_client_by_email(db: Session, email: str):
    return db.query(models.Client).filter(models.Client.email == email).first()

def get_clients(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Client).offset(skip).limit(limit).all()

def create_client(db: Session, client: schemas.ClientCreate):
    db_client = models.Client(name=client.name, email=client.email, phone_number=client.phone_number)
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

def get_patient(db: Session, patient_id: int):
    return db.query(models.Patient).filter(models.Patient.id == patient_id).first()

def get_patients(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Patient).offset(skip).limit(limit).all()

def get_patients_by_owner(db: Session, owner_id: int):
    return db.query(models.Patient).filter(models.Patient.owner_id == owner_id).all()

def create_patient(db: Session, patient: schemas.PatientCreate):
    db_patient = models.Patient(**patient.model_dump())
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient

def get_appointment_type(db: Session, appointment_type_id: int):
    return db.query(models.AppointmentType).filter(models.AppointmentType.id == appointment_type_id).first()

def get_appointment_types(db: Session):
    return db.query(models.AppointmentType).all()

def create_appointment_type(db: Session, appointment_type: schemas.AppointmentTypeCreate):
    db_appointment_type = models.AppointmentType(**appointment_type.model_dump())
    db.add(db_appointment_type)
    db.commit()
    db.refresh(db_appointment_type)
    return db_appointment_type