# backend/seed_demo.py
import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
# The api module is now in the same directory, so the import path changes.
from api import Base, Vet, Room, Appointment

# The DB file will be created in the current directory (/app in the container)
DATABASE_FILE = "clinic.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

def seed_database():
    """
    Initializes the database with default data if it's empty.
    This ensures the demo works out-of-the-box on first run.
    """
    engine = create_engine(DATABASE_URL)
    
    inspector = inspect(engine)
    if inspector.has_table("vets"):
        print("Database already seeded. Skipping initialization.")
        return

    print("Database not found or empty. Initializing with demo data...")
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # --- Default Clinic Setup ---
        num_vets = 5
        num_rooms = 5

        # Add Vets
        for i in range(1, num_vets + 1):
            session.add(Vet(name=f"Dr. Pawson {i}"))

        # Add Rooms
        for i in range(1, num_rooms + 1):
            session.add(Room(name=f"Exam Room {i}"))
        
        session.commit()
        print(f"Successfully created {num_vets} vets and {num_rooms} rooms.")

    except Exception as e:
        print(f"An error occurred during seeding: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    seed_database()
