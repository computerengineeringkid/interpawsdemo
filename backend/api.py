# backend/api.py
import os
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
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

# Configure server-side logging
log_file = os.path.join(_current_dir, 'server.log')
handler = RotatingFileHandler(log_file, maxBytes=100000, backupCount=3)
handler.setLevel(logging.ERROR)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)


def api_error(code: str, message: str, status: int = 400):
    """Return a standardized JSON API error response."""
    app.logger.error(f"{code}: {message}")
    return jsonify({'error': {'code': code, 'message': message}}), status


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
    except Exception:
        session.rollback()
        app.logger.exception("Error setting up clinic")
        return api_error('SETUP_FAILED', 'Failed to set up clinic', 500)
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

        # 3. Use LLM to rank the feasible slots
        app.logger.info("Sending slots to AI ranker...")
        ranked_slots = rank_slots_with_llm(feasible_slots, reason)

        # 4. Prepare top 3 slots for display
        top_slots = ranked_slots[:3]

        return render_template('results.html', slots=top_slots, pet_name=pet_name, reason=reason, date=appointment_date_str)

    except Exception:
        app.logger.exception("Error finding appointment")
        return api_error('FIND_APPOINTMENT_FAILED', 'Unable to search appointments', 500)
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
        app.logger.exception("Slot already booked")
        return api_error('SLOT_TAKEN', 'This slot was just booked by someone else. Please try another.', 409)
    except Exception:
        session.rollback()
        app.logger.exception("Error booking appointment")
        return api_error('BOOKING_FAILED', 'An error occurred during booking', 500)
    finally:
        session.close()

if __name__ == '__main__':
    # This is for local development without Gunicorn
    Base.metadata.create_all(engine)
    app.run(host='0.0.0.0', port=8000, debug=True)
