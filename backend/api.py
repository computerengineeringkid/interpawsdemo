# backend/api.py
import os
import sqlite3
from datetime import datetime, time, timedelta

from flask import Flask, jsonify, redirect, render_template, request, url_for
from sqlalchemy import (create_engine, Column, Integer, String, Time, ForeignKey,
                        Date)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError

from scheduler.solver import find_available_slots
from scheduler.ranker import rank_slots_with_llm

# --- Configuration & Setup ---
DATABASE_URL = "sqlite:///clinic.db"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

_current_dir = os.path.dirname(os.path.abspath(__file__))
_template_folder = os.path.join(_current_dir, 'templates')
app = Flask(__name__, template_folder=_template_folder)


# --- Database Models ---
class Vet(Base):
    __tablename__ = 'vets'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)

class Room(Base):
    __tablename__ = 'rooms'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)

class Appointment(Base):
    __tablename__ = 'appointments'
    id = Column(Integer, primary_key=True)
    pet_name = Column(String)
    reason = Column(String)
    date = Column(Date)
    start_time = Column(Time)
    end_time = Column(Time)
    vet_id = Column(Integer, ForeignKey('vets.id'))
    room_id = Column(Integer, ForeignKey('rooms.id'))

# --- Helper functions to provide additional context ---
def get_vet_specialties(vets):
    """Return a mapping of vet IDs to their specialties."""
    return {v.id: getattr(v, 'specialty', 'general practice') for v in vets}


def get_room_features(rooms):
    """Return a mapping of room IDs to their notable features."""
    return {r.id: getattr(r, 'features', ['standard exam room']) for r in rooms}


def get_patient_history(pet_name):
    """Stub for fetching patient history."""
    # In a real system, this would query a medical records database.
    return {"pet_name": pet_name, "notes": "No prior history available."}

# --- App Routes ---

@app.route('/')
def wizard():
    """Serves the initial clinic setup wizard page."""
    session = Session()
    clinic_exists = session.query(Vet).first() is not None
    session.close()
    if clinic_exists:
        return redirect(url_for('booking_form'))
    return render_template('wizard.html')

@app.route('/setup-clinic', methods=['POST'])
def setup_clinic():
    """
    Initializes the clinic with a number of vets and rooms.
    This is a demo-only function to set up the resources.
    """
    session = Session()
    try:
        num_vets = int(request.form.get('vets', 5))
        num_rooms = int(request.form.get('rooms', 5))

        # Clear existing data for a clean demo setup
        session.query(Appointment).delete()
        session.query(Vet).delete()
        session.query(Room).delete()

        for i in range(1, num_vets + 1):
            session.add(Vet(name=f"Dr. Pawson {i}"))
        for i in range(1, num_rooms + 1):
            session.add(Room(name=f"Exam Room {i}"))
        
        session.commit()
    except Exception as e:
        session.rollback()
        app.logger.error(f"Error setting up clinic: {e}")
    finally:
        session.close()
    
    return redirect(url_for('booking_form'))

@app.route('/booking')
def booking_form():
    """Serves the main appointment booking page."""
    return render_template('booking.html')

@app.route('/find-appointment', methods=['POST'])
def find_appointment():
    """
    API endpoint to find and rank appointment slots.
    This is called by the booking form via HTMX.
    """
    session = Session()
    try:
        # --- Get data from form ---
        pet_name = request.form.get('pet_name')
        reason = request.form.get('reason')
        appointment_date_str = request.form.get('date')
        appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d').date()

        # --- Core Logic ---
        # 1. Get resources and existing appointments from DB
        vets = session.query(Vet).all()
        rooms = session.query(Room).all()
        existing_appointments = session.query(Appointment).filter_by(date=appointment_date).all()

        # 2. Use OR-Tools to find all feasible slots
        feasible_slots = find_available_slots(
            appointment_date, vets, rooms, existing_appointments
        )

        if not feasible_slots:
            return "<div>No available slots found for this date.</div>"

        # 3. Gather additional context and use LLM to rank the feasible slots
        vet_specialties = get_vet_specialties(vets)
        room_features = get_room_features(rooms)
        patient_history = get_patient_history(pet_name)
        app.logger.info("Sending slots to AI ranker...")
        ranked_slots = rank_slots_with_llm(
            feasible_slots,
            reason,
            vet_specialties,
            room_features,
            patient_history,
        )

        # 4. Prepare top 3 slots for display
        top_slots = ranked_slots[:3]

        return render_template('results.html', slots=top_slots, pet_name=pet_name, reason=reason, date=appointment_date_str)

    except Exception as e:
        app.logger.error(f"Error finding appointment: {e}")
        return f"<div class='text-red-500 p-4'>An error occurred: {e}</div>"
    finally:
        session.close()

@app.route('/book-appointment', methods=['POST'])
def book_appointment():
    """
    Simulates booking an appointment and saves it to the database.
    """
    session = Session()
    try:
        pet_name = request.form.get('pet_name')
        reason = request.form.get('reason')
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        vet_id = int(request.form.get('vet_id'))
        room_id = int(request.form.get('room_id'))

        appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time_obj = datetime.strptime(time_str, '%H:%M').time()
        
        # Appointments are 30 minutes for this demo
        end_time_obj = (datetime.combine(appointment_date, start_time_obj) + timedelta(minutes=30)).time()

        new_appointment = Appointment(
            pet_name=pet_name,
            reason=reason,
            date=appointment_date,
            start_time=start_time_obj,
            end_time=end_time_obj,
            vet_id=vet_id,
            room_id=room_id
        )
        session.add(new_appointment)
        session.commit()
        
        # In a real app, you'd return a confirmation page.
        # For this demo, we just confirm it's "booked".
        return f"Booked appointment for {pet_name} at {time_str} on {date_str}!"

    except IntegrityError:
        session.rollback()
        return "Error: This slot was just booked by someone else. Please try another."
    except Exception as e:
        session.rollback()
        app.logger.error(f"Error booking appointment: {e}")
        return f"An error occurred during booking: {e}"
    finally:
        session.close()

if __name__ == '__main__':
    # This is for local development without Gunicorn
    Base.metadata.create_all(engine)
    app.run(host='0.0.0.0', port=8000, debug=True)
