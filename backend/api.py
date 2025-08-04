# backend/api.py
import os
import sqlite3
from datetime import datetime, time, timedelta

from flask import Flask, jsonify, redirect, render_template, request, url_for
from sqlalchemy import (create_engine, Column, Integer, String, Time, ForeignKey,
                        Date)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
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

class Client(Base):
    __tablename__ = 'clients'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    phone = Column(String)

class Patient(Base):
    __tablename__ = 'patients'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    client_id = Column(Integer, ForeignKey('clients.id'))
    client = relationship('Client')

class Appointment(Base):
    __tablename__ = 'appointments'
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patients.id'))
    patient = relationship('Patient')
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
    except Exception as e:
        session.rollback()
        app.logger.error(f"Error setting up clinic: {e}")
    finally:
        session.close()
    
    return redirect(url_for('booking_form'))

@app.route('/booking')
def booking_form():
    """Serves the main appointment booking page."""
    session = Session()
    patients = session.query(Patient).all()
    session.close()
    return render_template('booking.html', patients=patients)

@app.route('/find-appointment', methods=['POST'])
def find_appointment():
    """
    API endpoint to find and rank appointment slots.
    This is called by the booking form via HTMX.
    """
    session = Session()
    try:
        # --- Get data from form ---
        patient_id = int(request.form.get('patient_id'))
        reason = request.form.get('reason')
        appointment_date_str = request.form.get('date')
        patient = session.get(Patient, patient_id)
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

        return render_template('results.html', slots=top_slots, patient_name=patient.name, patient_id=patient_id, reason=reason, date=appointment_date_str)

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
        patient_id = int(request.form.get('patient_id'))
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
            patient_id=patient_id,
            reason=reason,
            date=appointment_date,
            start_time=start_time_obj,
            end_time=end_time_obj,
            vet_id=vet_id,
            room_id=room_id
        )
        session.add(new_appointment)
        session.commit()

        patient = session.get(Patient, patient_id)

        # In a real app, you'd return a confirmation page.
        # For this demo, we just confirm it's "booked".
        return f"Booked appointment for {patient.name} at {time_str} on {date_str}!"

    except IntegrityError:
        session.rollback()
        return "Error: This slot was just booked by someone else. Please try another."
    except Exception as e:
        session.rollback()
        app.logger.error(f"Error booking appointment: {e}")
        return f"An error occurred during booking: {e}"
    finally:
        session.close()


# --- Client CRUD Routes ---

@app.route('/clients')
def list_clients():
    session = Session()
    clients = session.query(Client).all()
    session.close()
    return render_template('clients/list.html', clients=clients)


@app.route('/clients/new', methods=['GET', 'POST'])
def create_client():
    session = Session()
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        session.add(Client(name=name, phone=phone))
        session.commit()
        session.close()
        return redirect(url_for('list_clients'))
    session.close()
    return render_template('clients/form.html', client=None)


@app.route('/clients/<int:client_id>/edit', methods=['GET', 'POST'])
def edit_client(client_id):
    session = Session()
    client = session.get(Client, client_id)
    if request.method == 'POST':
        client.name = request.form.get('name')
        client.phone = request.form.get('phone')
        session.commit()
        session.close()
        return redirect(url_for('list_clients'))
    session.close()
    return render_template('clients/form.html', client=client)


@app.route('/clients/<int:client_id>/delete', methods=['POST'])
def delete_client(client_id):
    session = Session()
    client = session.get(Client, client_id)
    session.delete(client)
    session.commit()
    session.close()
    return redirect(url_for('list_clients'))


# --- Patient CRUD Routes ---

@app.route('/patients')
def list_patients():
    session = Session()
    patients = session.query(Patient).all()
    session.close()
    return render_template('patients/list.html', patients=patients)


@app.route('/patients/new', methods=['GET', 'POST'])
def create_patient():
    session = Session()
    if request.method == 'POST':
        name = request.form.get('name')
        client_id = int(request.form.get('client_id'))
        session.add(Patient(name=name, client_id=client_id))
        session.commit()
        session.close()
        return redirect(url_for('list_patients'))
    clients = session.query(Client).all()
    session.close()
    return render_template('patients/form.html', patient=None, clients=clients)


@app.route('/patients/<int:patient_id>/edit', methods=['GET', 'POST'])
def edit_patient(patient_id):
    session = Session()
    patient = session.get(Patient, patient_id)
    if request.method == 'POST':
        patient.name = request.form.get('name')
        patient.client_id = int(request.form.get('client_id'))
        session.commit()
        session.close()
        return redirect(url_for('list_patients'))
    clients = session.query(Client).all()
    session.close()
    return render_template('patients/form.html', patient=patient, clients=clients)


@app.route('/patients/<int:patient_id>/delete', methods=['POST'])
def delete_patient(patient_id):
    session = Session()
    patient = session.get(Patient, patient_id)
    session.delete(patient)
    session.commit()
    session.close()
    return redirect(url_for('list_patients'))

if __name__ == '__main__':
    # This is for local development without Gunicorn
    Base.metadata.create_all(engine)
    app.run(host='0.0.0.0', port=8000, debug=True)
