# People Cache

*Because human relationships shouldn't rely on RAM.*

A small Django app for tracking your direct reports: a shared bank of profile
questions you fill in per person, plus a running history of 1:1 notes and
action items.

## Run it (Docker)

```
docker compose up --build
```

Then open http://localhost:8000

Data is persisted in a Docker volume (`manager_data`) as a SQLite file, so it
survives rebuilds. To reset everything: `docker compose down -v`.

## Usage

1. Go to **Questions** and define the profile questions you want to ask every
   direct report (e.g. "What motivates you?", "How do you like to receive
   feedback?").
2. Go to **Direct Reports** and add each person.
3. On a report's page, fill in answers under **Profile Questions**, and log
   dated notes with optional action items under **1:1 History**.

An admin site is also available at `/admin/` if you want direct data access;
create a superuser with:

```
docker compose exec web python manage.py createsuperuser
```

## Local development (without Docker)

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```
