# backend/scheduler/solver.py
from ortools.sat.python import cp_model
from datetime import time, timedelta, datetime

def find_available_slots(appointment_date, vets, rooms, existing_appointments):
    """
    Uses Google OR-Tools CP-SAT solver to find all available 30-minute
    appointment slots for a given day.

    Args:
        appointment_date (date): The date to search for slots.
        vets (list): List of Vet objects.
        rooms (list): List of Room objects.
        existing_appointments (list): List of Appointment objects for the given date.

    Returns:
        list: A list of dictionaries, where each dictionary represents a
              feasible appointment slot with 'vet_id', 'room_id', 'start_time',
              and 'end_time'.
    """
    model = cp_model.CpModel()

    # --- Constants ---
    # Working hours: 9:00 AM to 5:00 PM (17:00)
    # We represent time in minutes from midnight for easier calculations.
    day_start_min = 9 * 60  # 9:00 AM
    day_end_min = 17 * 60 # 5:00 PM
    appointment_duration = 30 # minutes

    vet_ids = [v.id for v in vets]
    room_ids = [r.id for r in rooms]

    # --- Create Interval Variables for Existing Appointments ---
    # These are fixed intervals that potential new appointments cannot overlap with.
    vet_intervals = {v_id: [] for v_id in vet_ids}
    room_intervals = {r_id: [] for r_id in room_ids}

    for appt in existing_appointments:
        start_min = appt.start_time.hour * 60 + appt.start_time.minute
        end_min = appt.end_time.hour * 60 + appt.end_time.minute
        duration = end_min - start_min
        
        # Create a fixed interval for the vet
        # FIX: The correct method name is NewIntervalVar. This was the source of the error.
        vet_interval = model.NewIntervalVar(start_min, duration, start_min + duration, f"vet_{appt.vet_id}_appt_{appt.id}")
        vet_intervals[appt.vet_id].append(vet_interval)

        # Create a fixed interval for the room
        # FIX: The correct method name is NewIntervalVar.
        room_interval = model.NewIntervalVar(start_min, duration, start_min + duration, f"room_{appt.room_id}_appt_{appt.id}")
        room_intervals[appt.room_id].append(room_interval)

    # --- Create Potential Appointment Slots ---
    # We create a potential 30-minute slot for every vet/room combination at every possible start time.
    # The solver will then tell us which of these are feasible.
    
    possible_starts = range(day_start_min, day_end_min - appointment_duration + 1, 15) # Check every 15 mins
    
    # This will hold our potential slots: (task_literal, vet_id, room_id, start_time_min)
    potential_slots = []

    for start_min in possible_starts:
        for v_id in vet_ids:
            for r_id in room_ids:
                # A boolean variable that is true if this specific slot is selected
                literal = model.NewBoolVar(f"slot_v{v_id}_r{r_id}_t{start_min}")
                
                # The interval for this potential slot
                # FIX: The correct method name is NewOptionalIntervalVar.
                interval = model.NewOptionalIntervalVar(
                    start_min,
                    appointment_duration,
                    start_min + appointment_duration,
                    literal,
                    f"interval_v{v_id}_r{r_id}_t{start_min}"
                )
                
                # Add this potential slot to the lists for constraints
                vet_intervals[v_id].append(interval)
                room_intervals[r_id].append(interval)
                
                potential_slots.append((literal, v_id, r_id, start_min))

    # --- Add Constraints ---
    # 1. No overlapping appointments for each vet
    for v_id in vet_ids:
        model.AddNoOverlap(vet_intervals[v_id])

    # 2. No overlapping appointments for each room
    for r_id in room_ids:
        model.AddNoOverlap(room_intervals[r_id])

    # --- Solver and Solution Collection ---
    solver = cp_model.CpSolver()
    
    # We need a solution callback to find ALL feasible solutions, not just one.
    class AllSolutionsCallback(cp_model.CpSolverSolutionCallback):
        def __init__(self, variables):
            cp_model.CpSolverSolutionCallback.__init__(self)
            self.__variables = variables
            self.solutions = []

        def on_solution_callback(self):
            for var, v_id, r_id, start_min in self.__variables:
                if self.Value(var):
                    start_time_obj = time(hour=start_min // 60, minute=start_min % 60)
                    end_time_obj = (datetime.combine(datetime.today(), start_time_obj) + timedelta(minutes=appointment_duration)).time()
                    self.solutions.append({
                        "vet_id": v_id,
                        "vet_name": f"Dr. Pawson {v_id}", # Demo name
                        "room_id": r_id,
                        "room_name": f"Exam Room {r_id}", # Demo name
                        "date": appointment_date.strftime('%Y-%m-%d'),
                        "start_time": start_time_obj.strftime('%H:%M'),
                        "end_time": end_time_obj.strftime('%H:%M'),
                    })

    solution_callback = AllSolutionsCallback(potential_slots)
    solver.parameters.enumerate_all_solutions = True
    status = solver.Solve(model, solution_callback)
    
    # Remove duplicate slots (can happen if multiple rooms/vets are free)
    unique_solutions = []
    seen_slots = set()
    for sol in solution_callback.solutions:
        slot_key = (sol['start_time'], sol['end_time'])
        if slot_key not in seen_slots:
            unique_solutions.append(sol)
            seen_slots.add(slot_key)

    # Sort solutions by time
    unique_solutions.sort(key=lambda x: x['start_time'])

    return unique_solutions
