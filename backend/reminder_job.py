"""Cron-friendly script to send upcoming appointment reminders."""
from datetime import datetime, timedelta

from api import Base, Session, Appointment, Client, engine
from reminders import send_email_reminder, send_sms_reminder


def main() -> None:
    Base.metadata.create_all(engine)
    session = Session()
    try:
        target_date = datetime.now().date() + timedelta(days=1)
        appointments = session.query(Appointment).filter_by(date=target_date).all()
        for appt in appointments:
            client = session.query(Client).get(appt.client_id)
            if not client:
                continue
            message = (
                f"Reminder: appointment for {appt.pet_name} on {appt.date} at {appt.start_time}"
            )
            subject = "Appointment Reminder"
            if client.email and client.email_opt_in:
                send_email_reminder(client.email, subject, message)
            if client.phone and client.sms_opt_in:
                send_sms_reminder(client.phone, message)
    finally:
        session.close()


if __name__ == "__main__":
    main()
