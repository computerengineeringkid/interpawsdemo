# backend/app/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from .database import Base

class Vet(Base):
    __tablename__ = "vets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    appointments = relationship("Appointment", back_populates="vet")

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    appointments = relationship("Appointment", back_populates="room")

class AppointmentType(Base):
    __tablename__ = "appointment_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, unique=True)
    duration_minutes = Column(Integer)

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    phone_number = Column(String)
    patients = relationship("Patient", back_populates="owner")

class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    species = Column(String)
    breed = Column(String)
    age = Column(Integer)
    owner_id = Column(Integer, ForeignKey("clients.id"))
    owner = relationship("Client", back_populates="patients")

class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime, index=True)
    end_time = Column(DateTime, index=True)
    reason_for_visit = Column(String)
    vet_id = Column(Integer, ForeignKey("vets.id"))
    room_id = Column(Integer, ForeignKey("rooms.id"))
    appointment_type_id = Column(Integer, ForeignKey("appointment_types.id"))
    client_id = Column(Integer, ForeignKey("clients.id"))
    patient_id = Column(Integer, ForeignKey("patients.id"))

    vet = relationship("Vet", back_populates="appointments")
    room = relationship("Room", back_populates="appointments")
    appointment_type = relationship("AppointmentType")
    client = relationship("Client")
    patient = relationship("Patient")

class RankedSlot(Base):
    __tablename__ = "ranked_slots"
    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    vet_id = Column(Integer, ForeignKey("vets.id"))
    vet_name = Column(String)
    room_id = Column(Integer, ForeignKey("rooms.id"))
    room_name = Column(String)
    score = Column(Float)