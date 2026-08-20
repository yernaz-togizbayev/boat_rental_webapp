# Boat Rental — IMSE Group 05

Coursework for *052400-1 VU Information Management and Systems Engineering*, University of Vienna.

A boat rental web app: clients search a harbour for a date range, book a boat, and pay for the
charter; managers run the fleet, the offices, the staff and the bookings behind it.

- **Student 1:** Golovanov, Ilja — 12133820
- **Student 2:** Togizbayev, Yernaz — 01429473

## Running it

Docker is the only prerequisite. From the repository root:

```bash
docker compose up --build
```

Then open <http://localhost:5000>. MariaDB is exposed on `3306`.

There is no sign-up wall to get past: `/login` lists every client and one click signs you in, and
`/manager/login` picks a manager from a dropdown. Authentication is passwordless **by design** —
this is a database course, not an auth exercise. See [Scope](#scope-and-known-limits).

A fresh database is seeded by the SQL in `database/`. If the app looks empty, or you want a bigger
fleet to click around, use the **Demo data** panel at the top of any page — it is deliberately
available without signing in, and it keeps any harbours you have added.

```bash
docker compose down -v          # -v is required to re-run the DB init scripts
docker compose logs -f backend
```

`./backend/` is bind-mounted, so Python edits reload and template edits show on the next request.
**Schema changes need `down -v`,** which destroys the volume and everything in it.

### Configuration

Everything has a working default; a `.env` file in the repository root can override it.

| Variable | Default | Purpose |
|---|---|---|
| `TZ` | `Europe/Vienna` | Both containers. Payment deadlines are naive `DATETIME`s, so the app, MariaDB and the clock on the wall have to agree. |
| `UNSPLASH_ACCESS_KEY` | *(unset)* | Optional. Fetches a photo for a harbour the app has no hand-picked image for. Without it there is a Wikipedia lookup and then a generic pool. |
| `IMAGE_FETCH` | `on` | Set to `off` to skip all outbound image lookups and run fully offline. |
| `SECRET_KEY` | `dev` | Flask session signing. |

`.env` is gitignored and must stay that way.

## Tests

`backend/smoke_test.py` drives the real app end to end over the flows that have actually broken
before — booking validation, double booking, payment holds expiring, cancellation, employee role
changes, the FK cleanup around deletes. It runs against a throwaway SQLite database, so it needs no
Docker:

```bash
cd backend
pip install -r requirements.txt
python smoke_test.py
```

It does **not** cover the SQL seed scripts; those need MariaDB.

## Layout

```
backend/          Flask app (boat_rental/), Jinja templates, static assets, smoke_test.py
database/         Graded SQL: shared CREATE TABLEs + per-student insert and query scripts
docs/             Graded deliverables: ER diagram, NoSQL designs, SQL screenshots
Group05_MS1.pdf   Milestone 1 report
CLAUDE.md         Architecture notes and the invariants that are easy to break
```

Two details about `database/` that are easy to trip over:

- MariaDB's entrypoint runs top-level files alphabetically and **does not recurse**, so `init.sql`
  exists only to `SOURCE` the per-student scripts in `Student1/` and `Student2/`.
- Student 1 owns the shared `Office` rows; Student 2 must not re-insert them. A single missing
  semicolon kills the rest of the chain, and the only symptom is an empty app.

### Deliverables

| Requirement | Where |
|---|---|
| ER diagram | `docs/ER-diagram/` — BEE-UP source (`.adl`) and export (`.jpg`) |
| Relational schema | `database/Group05_Createtable.sql` |
| Use-case + analytics SQL | `database/Student1/`, `database/Student2/` |
| NoSQL designs | `docs/json/NoSQLDesign_IG.json`, `docs/json/NoSQLDesign_TY.json` |

## Scope and known limits

Deliberate, so they are not mistaken for oversights:

- **No passwords.** `/login` is a client picker. Adding real auth would not change anything the
  coursework is assessed on.
- **Payment is a local simulation.** No payment provider is contacted and no network call is made.
  `4242 4242 4242 4242` is accepted and `4000 0000 0000 0002` is declined, following Stripe's
  published test numbers as a convention a grader will recognise. **Card numbers are validated and
  then discarded** — never stored, never put in the session, never logged.
- **No scheduler.** Unpaid bookings are holds that expire, and they are swept when availability is
  read rather than by a background job, because a search is the moment the answer has to be honest.
- **No migrations.** `models.py` is a hand-maintained mirror of `Group05_Createtable.sql`; a column
  added to one must be added to the other.
