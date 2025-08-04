# Interpaws Demo

This project showcases a veterinary clinic scheduling backend built with **Flask**.
It includes a small HTML interface and uses SQLite for persistence.

The application now stores client contact details and supports appointment
reminders via email (SendGrid) and SMS (Twilio). Reminder preferences can be
configured per client.

## Running with Docker

Build and start the backend service:

```bash
docker-compose up --build
```

The container seeds a demo database and launches the Flask app on [http://localhost:8000](http://localhost:8000).

## Sending Reminder Notifications

Reminders for the next day's appointments can be sent by running:

```bash
python backend/reminder_job.py
```

This script is suitable for execution via cron. Configure the following
environment variables to enable notifications:

- `SENDGRID_API_KEY` and `REMINDER_EMAIL` for email reminders.
- `TWILIO_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_PHONE_NUMBER` for SMS reminders.

