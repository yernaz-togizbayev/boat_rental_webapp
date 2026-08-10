"""End-to-end smoke test for the flows that used to be broken.

Runs the real Flask app against a throwaway SQLite database so it can be
executed without Docker:

    DATABASE_URL=sqlite:///smoke.db python smoke_test.py

The MariaDB-only parts (generator.do_assignments, the SQL seed scripts) are not
exercised here — those need `docker compose up`.
"""

import os
import sqlite3
import sys
import tempfile
from datetime import date, timedelta

os.environ.setdefault(
    "DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(), "smoke.db")
)
os.environ["WTF_CSRF_ENABLED"] = "0"

from sqlalchemy import event, text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from boat_rental import app, db  # noqa: E402
from boat_rental.models import (  # noqa: E402
    AVAILABILITY_AVAILABLE,
    AVAILABILITY_MAINTENANCE,
    Boat,
    Catamaran,
    Client,
    Employee,
    Manager,
    Office,
    Rental,
    Staff,
    Yacht,
)

app.config["WTF_CSRF_ENABLED"] = False


@event.listens_for(Engine, "connect")
def _enforce_sqlite_foreign_keys(dbapi_connection, _record):
    """SQLite ignores foreign keys unless asked. Without this the FK bugs this
    script exists to catch would silently pass here, because MariaDB enforces
    them and SQLite would not."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

FAILURES = []
START = date.today() + timedelta(days=3)
END = START + timedelta(days=5)


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f"  -- {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


def seed():
    db.drop_all()
    db.create_all()
    # Supervises / Maintains have no models; the app reaches them with raw SQL.
    db.session.execute(text("""
        CREATE TABLE Supervises (
            ManagerID VARCHAR(50) REFERENCES Manager(ManagerID),
            StaffID VARCHAR(50) REFERENCES Staff(StaffID),
            PRIMARY KEY (ManagerID, StaffID))
    """))
    db.session.execute(text("""
        CREATE TABLE Maintains (
            StaffID VARCHAR(50) REFERENCES Staff(StaffID),
            BoatID VARCHAR(50) REFERENCES Boat(BoatID),
            PRIMARY KEY (StaffID, BoatID))
    """))

    db.session.add(Office(OfficeID="O1", Street="Quay 1", Country="HR", City="Dubrovnik", ZIP="20000"))
    db.session.add(Office(OfficeID="O2", Street="Quay 2", Country="GR", City="Mykonos", ZIP="84600"))
    # Nice has an office but only a boat under maintenance -> always empty.
    db.session.add(Office(OfficeID="O3", Street="Quay 3", Country="FR", City="Nice", ZIP="06000"))
    db.session.add(Boat(BoatID="B9", OfficeID="O3", Length=8.0, Seats=3, Manufacturer="M9",
                        AvailabilityStatus=AVAILABILITY_MAINTENANCE, Weight=800.0, Horsepower=60))
    for cid, first in (("C1", "Max"), ("C2", "Olga")):
        db.session.add(Client(ClientID=cid, FirstName=first, LastName="Test",
                              Birthdate=date(1990, 1, 1), Email=f"{cid}@example.com"))
    # B1 free, B2 under maintenance, B3 in another city, B4 has a NULL length.
    db.session.add(Boat(BoatID="B1", OfficeID="O1", Length=10.0, Seats=4, Manufacturer="M1",
                        AvailabilityStatus=AVAILABILITY_AVAILABLE, Weight=900.0, Horsepower=90))
    db.session.add(Boat(BoatID="B2", OfficeID="O1", Length=12.0, Seats=6, Manufacturer="M1",
                        AvailabilityStatus=AVAILABILITY_MAINTENANCE, Weight=950.0, Horsepower=95))
    db.session.add(Boat(BoatID="B3", OfficeID="O2", Length=14.0, Seats=8, Manufacturer="M2",
                        AvailabilityStatus=AVAILABILITY_AVAILABLE, Weight=990.0, Horsepower=99))
    db.session.add(Boat(BoatID="B4", OfficeID="O1", Length=None, Seats=2, Manufacturer="M3",
                        AvailabilityStatus=AVAILABILITY_AVAILABLE, Weight=None, Horsepower=50))

    # Flushed in dependency order: with foreign keys enforced, each referenced
    # row has to be on disk before the row pointing at it.
    db.session.flush()

    # M1 supervises M2; M2 supervises staff S1 -> deleting M1 or M2 used to fail.
    for eid, first, salary in (("M1", "Boss", 9000), ("M2", "Anna", 6000), ("S1", "Jane", 3000)):
        db.session.add(Employee(EmployeeID=eid, OfficeID="O1", FirstName=first, LastName="X",
                                Birthdate=date(1980, 1, 1), Email=f"{eid}@example.com",
                                SelfInsuranceNr=f"INS-{eid}", Salary=salary))
    db.session.flush()

    db.session.add(Manager(ManagerID="M1", Department="Exec", ManagementLevel="Top", SupervisorID=None))
    db.session.flush()
    db.session.add(Manager(ManagerID="M2", Department="HR", ManagementLevel="Senior", SupervisorID="M1"))
    db.session.add(Staff(StaffID="S1", WorkShift="Day", IsOnDuty=True))
    db.session.commit()
    db.session.execute(text("INSERT INTO Supervises VALUES ('M2', 'S1')"))
    db.session.execute(text("INSERT INTO Maintains VALUES ('S1', 'B1')"))
    db.session.commit()


def as_client(c, client_id):
    c.get(f"/select-client/{client_id}", follow_redirects=True)


def as_manager(c, manager_id="M1"):
    c.post("/manager/login", data={"manager_id": manager_id}, follow_redirects=True)


def search(c, city, start=START, end=END):
    return c.post("/booking", data={
        "city": city,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "search": "Search available boats",
    }, follow_redirects=True)


def book(c, boat_id, city="Dubrovnik", start=START, end=END):
    return c.post("/booking", data={
        "boat_id": boat_id,
        "city": city,
        "rental_date": start.isoformat(),
        "rental_end_date": end.isoformat(),
        "book": "true",
    }, follow_redirects=True)


def main():
    with app.app_context():
        seed()

        # 1. Search with no available boats -> used to be a 500 (UnboundLocalError)
        with app.test_client() as c:
            as_client(c, "C1")
            r = search(c, "Nice")
            body = r.get_data(as_text=True)
            check("empty search renders instead of 500", r.status_code == 200,
                  f"status {r.status_code}")
            check("empty search shows the 'no boats' message",
                  "No boats available" in body)

        # 2. A normal search lists the free boat and hides the unavailable ones
        with app.test_client() as c:
            as_client(c, "C1")
            body = search(c, "Dubrovnik").get_data(as_text=True)
            check("search lists the available boat", "B1" in body)
            check("search hides the maintenance boat", "B2" not in body)
            check("search hides boats in other cities", "B3" not in body)
            check("NULL boat length renders as a dash", "—" in body)

        # 3. Booking works and shows on the report
        with app.test_client() as c:
            as_client(c, "C1")
            search(c, "Dubrovnik")
            body = book(c, "B1").get_data(as_text=True)
            check("booking succeeds", "successfully booked" in body)
            check("booking lands on the report page", "Your Rentals" in body)
        with app.app_context():
            check("rental was persisted", Rental.query.count() == 1)

        # 4. A different client cannot double-book the same boat/dates
        with app.test_client() as c:
            as_client(c, "C2")
            body = book(c, "B1", start=START + timedelta(days=1)).get_data(as_text=True)
            check("overlapping booking by another client is rejected",
                  "successfully booked" not in body, body[:200])
        check("no second rental was written", Rental.query.count() == 1)

        # 5. Tampering: booking a maintenance boat / a boat in another city
        with app.test_client() as c:
            as_client(c, "C2")
            check("maintenance boat is rejected",
                  "successfully booked" not in book(c, "B2").get_data(as_text=True))
            check("boat from another city is rejected",
                  "successfully booked" not in book(c, "B3").get_data(as_text=True))
            check("past start date is rejected",
                  "successfully booked" not in book(
                      c, "B4", start=date.today() - timedelta(days=5),
                      end=date.today() + timedelta(days=1)).get_data(as_text=True))
        check("no rentals added by tampering", Rental.query.count() == 1)

        # 6. A non-overlapping booking of the same boat still works
        with app.test_client() as c:
            as_client(c, "C2")
            later = END + timedelta(days=10)
            body = book(c, "B1", start=later, end=later + timedelta(days=2)).get_data(as_text=True)
            check("non-overlapping booking of same boat succeeds",
                  "successfully booked" in body)

        # 7. Analytics survives junk input
        with app.test_client() as c:
            as_client(c, "C1")
            r = c.get("/analytics?city=Dubrovnik&start_date=banana&end_date=2026-01-01")
            check("analytics tolerates an unparseable date", r.status_code == 200,
                  f"status {r.status_code}")
            r2 = c.get("/analytics")
            check("analytics default view renders", r2.status_code == 200)
            check("analytics no longer defaults to the stale 2025 window",
                  "2025-07-01" not in r2.get_data(as_text=True))

        # 8. GET search links work (this branch was dead: it read request.form)
        with app.test_client() as c:
            as_client(c, "C1")
            body = c.get(
                f"/booking?city=Dubrovnik&start_date={START}&end_date={END}"
            ).get_data(as_text=True)
            check("bookmarkable GET search returns results", "Available Boats in" in body)

        # 9. Manager deleting a supervisor -> used to fail on FK constraints
        with app.test_client() as c:
            as_manager(c, "M1")
            body = c.post("/manager/employees/M2/delete", data={"submit": "Delete"},
                          follow_redirects=True).get_data(as_text=True)
            check("deleting a supervising manager succeeds", "Employee deleted" in body, body[:300])
        check("manager row is gone", Manager.query.get("M2") is None)
        check("supervises rows were cleaned up",
              db.session.execute(text("SELECT COUNT(*) FROM Supervises WHERE ManagerID='M2'")).scalar() == 0)

        # 10. Self-delete is blocked
        with app.test_client() as c:
            as_manager(c, "M1")
            body = c.post("/manager/employees/M1/delete", data={"submit": "Delete"},
                          follow_redirects=True).get_data(as_text=True)
            check("self-delete is refused", "cannot delete" in body.lower())
        check("signed-in manager still exists", Manager.query.get("M1") is not None)

        # 11. Promoting supervised staff to manager -> used to fail on FK
        with app.test_client() as c:
            as_manager(c, "M1")
            body = c.post("/manager/employees/S1/edit", data={
                "office_id": "O1", "first_name": "Jane", "last_name": "X",
                "birthdate": "1980-01-01", "email": "s1@example.com",
                "self_insurance_nr": "INS-S1", "salary": "3000",
                "role": "manager", "department": "Ops", "management_level": "L2",
                "supervisor_id": "", "submit": "Save changes",
            }, follow_redirects=True).get_data(as_text=True)
            check("promoting supervised staff to manager succeeds",
                  "Employee updated" in body, body[:300])
        check("staff row removed after promotion", Staff.query.get("S1") is None)
        check("manager row created after promotion", Manager.query.get("S1") is not None)

        # 12. /logout clears a manager session too
        with app.test_client() as c:
            as_manager(c, "M1")
            c.get("/logout", follow_redirects=True)
            r = c.get("/manager/employees")
            check("logout clears the manager session", r.status_code == 302,
                  f"status {r.status_code}")

        # 13. A manager can add a city, stock it with a boat, and a client can
        #     then book there. This is the whole point of the office/boat CRUD,
        #     so it is tested as one chain rather than as isolated routes.
        with app.test_client() as c:
            as_manager(c, "M1")
            body = c.post("/manager/offices/new", data={
                "city": "Split", "country": "Croatia",
                "street": "Riva 5", "zip": "21000", "submit": "Save office",
            }, follow_redirects=True).get_data(as_text=True)
            check("manager can add a city", "Split added" in body, body[:300])

        split = Office.query.filter_by(City="Split").first()
        check("new office row was written", split is not None)

        with app.test_client() as c:
            as_client(c, "C1")
            body = c.get("/booking").get_data(as_text=True)
            check("new city shows up in the booking search", "Split" in body, body[:300])
            body = search(c, "Split").get_data(as_text=True)
            check("new city has no boats yet", "no boats" in body.lower(), body[:300])

        with app.test_client() as c:
            as_manager(c, "M1")
            body = c.post("/manager/boats/new", data={
                "office_id": split.OfficeID, "manufacturer": "Lagoon",
                "seats": "8", "length": "13.5", "weight": "1200", "horsepower": "150",
                "availability_status": AVAILABILITY_AVAILABLE,
                "boat_type": "catamaran", "nr_of_cabins": "4", "max_capacity": "10",
                "submit": "Save boat",
            }, follow_redirects=True).get_data(as_text=True)
            check("manager can add a boat", "added" in body, body[:300])

        new_boat_row = Boat.query.filter_by(OfficeID=split.OfficeID).first()
        check("boat row was written", new_boat_row is not None)
        check("catamaran subclass row was written",
              Catamaran.query.get(new_boat_row.BoatID) is not None)

        with app.test_client() as c:
            as_client(c, "C1")
            body = search(c, "Split").get_data(as_text=True)
            check("new boat is offered in the new city",
                  new_boat_row.BoatID in body, body[:300])
            body = book(c, new_boat_row.BoatID, city="Split").get_data(as_text=True)
            check("client can book a boat in the new city",
                  Rental.query.filter_by(BoatID=new_boat_row.BoatID).count() == 1,
                  body[:300])

        # Switching subclass moves the row between tables, like a staff/manager
        # role change does.
        with app.test_client() as c:
            as_manager(c, "M1")
            c.post(f"/manager/boats/{new_boat_row.BoatID}/edit", data={
                "office_id": split.OfficeID, "manufacturer": "Lagoon",
                "seats": "8", "length": "13.5", "weight": "1200", "horsepower": "150",
                "availability_status": AVAILABILITY_AVAILABLE,
                "boat_type": "yacht", "yacht_name": "Sea Star", "has_jacuzzi": "y",
                "submit": "Save boat",
            }, follow_redirects=True)
        check("old subclass row removed on type change",
              Catamaran.query.get(new_boat_row.BoatID) is None)
        check("new subclass row created on type change",
              Yacht.query.get(new_boat_row.BoatID) is not None)

        # Delete guards: neither of these may take referenced rows with them.
        with app.test_client() as c:
            as_manager(c, "M1")
            body = c.post(f"/manager/boats/{new_boat_row.BoatID}/delete",
                          follow_redirects=True).get_data(as_text=True)
            check("deleting a boat with rentals is refused",
                  "rental(s) on record" in body, body[:300])
            check("boat survived the refused delete",
                  Boat.query.get(new_boat_row.BoatID) is not None)

            body = c.post(f"/manager/offices/{split.OfficeID}/delete",
                          follow_redirects=True).get_data(as_text=True)
            check("deleting a city that still has boats is refused",
                  "Cannot delete Split" in body, body[:300])

            # An empty city deletes cleanly.
            c.post("/manager/offices/new", data={
                "city": "Zadar", "country": "Croatia",
                "street": "Obala 1", "zip": "23000", "submit": "Save office",
            }, follow_redirects=True)
            zadar = Office.query.filter_by(City="Zadar").first()
            c.post(f"/manager/offices/{zadar.OfficeID}/delete", follow_redirects=True)
            check("an empty city can be deleted",
                  Office.query.filter_by(City="Zadar").first() is None)

        # 14. generate-data is open to anonymous visitors, but only once per session
        with app.test_client() as c:
            body = c.post("/generate-data", follow_redirects=True).get_data(as_text=True)
            check("anonymous can generate data", "Demo data generated" in body, body[:300])
            check("button hides after generating",
                  "Generate demo data" not in body, body[:300])
            body = c.post("/generate-data", follow_redirects=True).get_data(as_text=True)
            check("replayed generate-data is refused",
                  "already been generated" in body, body[:300])

            # logging in and out must not resurrect the button
            client_id = Client.query.first().ClientID
            c.get(f"/select-client/{client_id}", follow_redirects=True)
            body = c.get("/logout", follow_redirects=True).get_data(as_text=True)
            check("button stays hidden after a client login/logout",
                  "Generate demo data" not in body, body[:300])
            as_manager(c, Manager.query.first().ManagerID)
            body = c.get("/manager/logout", follow_redirects=True).get_data(as_text=True)
            check("button stays hidden after a manager login/logout",
                  "Generate demo data" not in body, body[:300])

        # 15. The Generate Data reset runs cleanly and fills the m:n tables
        with app.app_context():
            from boat_rental.generator import generate_data
            try:
                generate_data()
                ok = True
            except Exception as exc:  # noqa: BLE001 - reported as a failure
                ok = False
                print(f"       generate_data raised: {exc!r}")
            check("generate_data completes", ok)
            check("generate_data created boats", Boat.query.count() > 0)
            check("generate_data created rentals", Rental.query.count() > 0)
            check("generate_data refills Supervises",
                  db.session.execute(text("SELECT COUNT(*) FROM Supervises")).scalar() > 0)
            check("generate_data refills Maintains",
                  db.session.execute(text("SELECT COUNT(*) FROM Maintains")).scalar() > 0)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
