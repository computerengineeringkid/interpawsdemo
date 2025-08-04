# backend/api.py
import os
import json
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, time, timedelta

from flask import Flask, jsonify, redirect, render_template, request, url_for
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Time,
    ForeignKey,
    Date,
    Boolean,
)
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

_config_file = os.path.join(_current_dir, 'appointment_types.json')


def load_appointment_types():
    """Load appointment types from configuration file."""
    try:
        with open(_config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []


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

class Client(Base):
    __tablename__ = 'clients'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    email_opt_in = Column(Boolean, default=True)
    sms_opt_in = Column(Boolean, default=True)

class Appointment(Base):
    __tablename__ = 'appointments'
    id = Column(Integer, primary_key=True)
    pet_name = Column(String)
    reason = Column(String)
    date = Column(Date)
    start_time = Column(Time)
    end_time = Column(Time)
    type = Column(String)
    duration_minutes = Column(Integer)
    vet_id = Column(Integer, ForeignKey('vets.id'))
    room_id = Column(Integer, ForeignKey('rooms.id'))
    client_id = Column(Integer, ForeignKey('clients.id'))

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


VET_COLORS = [
    "#e57373",  # red
    "#64b5f6",  # blue
    "#81c784",  # green
    "#ffd54f",  # yellow
    "#ba68c8",  # purple
    "#4db6ac",  # teal
]


def get_vet_colors(session):
    """Return a mapping of vet.id -> color for consistent color coding."""
    vets = session.query(Vet).order_by(Vet.id).all()
    return {vet.id: VET_COLORS[i % len(VET_COLORS)] for i, vet in enumerate(vets)}

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
    appointment_types = load_appointment_types()
    return render_template('booking.html', appointment_types=appointment_types)


@app.route('/calendar')
def calendar_view():
    """Display a calendar of appointments."""
    session = Session()
    try:
        vets = session.query(Vet).all()
        rooms = session.query(Room).all()
    finally:
        session.close()
    return render_template('calendar.html', vets=vets, rooms=rooms)

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
        client_name = request.form.get('client_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        email_opt_in = bool(request.form.get('email_opt_in'))
        sms_opt_in = bool(request.form.get('sms_opt_in'))
        appointment_date_str = request.form.get('date')
        appointment_type = request.form.get('appointment_type')
        appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d').date()

        types = load_appointment_types()
        duration = next((t['duration_minutes'] for t in types if t['type'] == appointment_type), 30)

        # --- Core Logic ---
        # 1. Get resources and existing appointments from DB
        vets = session.query(Vet).all()
        rooms = session.query(Room).all()
        existing_appointments = session.query(Appointment).filter_by(date=appointment_date).all()

        # 2. Use OR-Tools to find all feasible slots
        feasible_slots = find_available_slots(
            appointment_date, vets, rooms, existing_appointments, duration
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

        return render_template(
            'results.html',
            slots=top_slots,
            pet_name=pet_name,
            reason=reason,
            date=appointment_date_str,
            appointment_type=appointment_type,
            duration_minutes=duration,
            client_name=client_name,
            email=email,
            phone=phone,
            email_opt_in=email_opt_in,
            sms_opt_in=sms_opt_in,
        )

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
        appointment_type = request.form.get('appointment_type')
        duration = int(request.form.get('duration_minutes'))
        vet_id = int(request.form.get('vet_id'))
        room_id = int(request.form.get('room_id'))
        client_name = request.form.get('client_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        email_opt_in = request.form.get('email_opt_in') == 'True'
        sms_opt_in = request.form.get('sms_opt_in') == 'True'

        appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time_obj = datetime.strptime(time_str, '%H:%M').time()

        end_time_obj = (datetime.combine(appointment_date, start_time_obj) + timedelta(minutes=duration)).time()

        client = Client(
            name=client_name,
            email=email,
            phone=phone,
            email_opt_in=email_opt_in,
            sms_opt_in=sms_opt_in,
        )
        session.add(client)
        session.flush()

        new_appointment = Appointment(
            pet_name=pet_name,
            reason=reason,
            type=appointment_type,
            duration_minutes=duration,
            date=appointment_date,
            start_time=start_time_obj,
            end_time=end_time_obj,
            vet_id=vet_id,
            room_id=room_id,
            client_id=client.id,
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


@app.route('/api/appointments')
def api_appointments():
    """Return appointments in JSON for the calendar."""
    vet_id = request.args.get('vet_id', type=int)
    room_id = request.args.get('room_id', type=int)
    session = Session()
    try:
        query = session.query(Appointment, Vet, Room).join(Vet).join(Room)
        if vet_id:
            query = query.filter(Appointment.vet_id == vet_id)
        if room_id:
            query = query.filter(Appointment.room_id == room_id)

        vet_colors = get_vet_colors(session)

        events = []
        for appt, vet, room in query.all():
            start_dt = datetime.combine(appt.date, appt.start_time)
            end_dt = datetime.combine(appt.date, appt.end_time)
            events.append({
                "id": appt.id,
                "title": f"{appt.pet_name} ({vet.name})",
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "url": url_for('appointment_detail', appointment_id=appt.id),
                "color": vet_colors.get(vet.id)
            })

        return jsonify(events)
    finally:
        session.close()


@app.route('/appointment/<int:appointment_id>')
def appointment_detail(appointment_id):
    """Simple appointment details page."""
    session = Session()
    appointment = session.query(Appointment).filter_by(id=appointment_id).first()
    if not appointment:
        session.close()
        return "Appointment not found", 404
    vet = session.get(Vet, appointment.vet_id)
    room = session.get(Room, appointment.room_id)
    session.close()
    return render_template('appointment_detail.html', appointment=appointment, vet=vet, room=room)

if __name__ == '__main__':
    # This is for local development without Gunicorn
    Base.metadata.create_all(engine)
    app.run(host='0.0.0.0', port=8000, debug=True)
