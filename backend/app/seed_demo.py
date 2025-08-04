# backend/app/seed_demo.py
from .database import SessionLocal, engine
from .models import Vet, Room, Base, AppointmentType
from .crud import create_appointment_type
from .schemas import AppointmentTypeCreate

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Seed Vets
    if not db.query(Vet).first():
        vets = [Vet(name="Dr. Smith"), Vet(name="Dr. Jones")]
        db.add_all(vets)
        db.commit()

    # Seed Rooms
    if not db.query(Room).first():
        rooms = [Room(name="Room 1"), Room(name="Room 2")]
        db.add_all(rooms)
        db.commit()

    # Seed Appointment Types
    if not db.query(AppointmentType).first():
        appointment_types = [
            AppointmentTypeCreate(name="Routine Check-up", duration_minutes=30),
            AppointmentTypeCreate(name="Vaccination", duration_minutes=15),
            AppointmentTypeCreate(name="Surgery", duration_minutes=90),
            AppointmentTypeCreate(name="Emergency", duration_minutes=60),
        ]
        for at in appointment_types:
            create_appointment_type(db, at)

    db.close()

if __name__ == "__main__":
    seed()