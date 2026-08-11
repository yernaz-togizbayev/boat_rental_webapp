"""End-to-end smoke test for the flows that used to be broken.

Runs the real Flask app against a throwaway SQLite database so it can be
executed without Docker:

    DATABASE_URL=sqlite:///smoke.db python smoke_test.py

The MariaDB-only parts (generator.do_assignments, the SQL seed scripts) are not
exercised here — those need `docker compose up`.
"""

import os
import re
import sqlite3
import sys
import tempfile
from datetime import date, timedelta

os.environ.setdefault(
    "DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(), "smoke.db")
)
os.environ["WTF_CSRF_ENABLED"] = "0"
# No live photo lookups: the suite must pass offline and must not spend a
# network round trip on every booking-page render.
os.environ["IMAGE_FETCH"] = "off"

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


def rentals_card(body):
    """Read the 'Rentals in <city>' figure off an /analytics page."""
    match = re.search(r'id="rentals-in-period"[^>]*>\s*(\d+)', body)
    return int(match.group(1)) if match else -1


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

        # 7b. The "Rentals in <city>" card must follow the city filter. It used
        #     to be an unjoined count over every Rental, so it showed the same
        #     fleet-wide number whatever city was selected.
        db.session.add(Rental(ClientID="C2", BoatID="B3", RentalDate=START,
                              RentalEndDate=END, PaymentStatus="PAID"))
        db.session.commit()
        with app.test_client() as c:
            as_client(c, "C1")

            def card(city):
                body = c.get(
                    f"/analytics?city={city}&start_date={START}&end_date={END}"
                ).get_data(as_text=True)
                return rentals_card(body)

            # C1 rents B1 in Dubrovnik; C2 now rents B3 in Mykonos.
            check("analytics rental count excludes other cities", card("Dubrovnik") == 1,
                  f"got {card('Dubrovnik')}")
            check("analytics rental count follows the city filter", card("Mykonos") == 1,
                  f"got {card('Mykonos')}")
            # Nice has only a maintenance boat and no rentals at all, so a
            # non-zero here would mean the join is not filtering.
            check("analytics counts nothing in a city with no rentals", card("Nice") == 0,
                  f"got {card('Nice')}")

        # 8. GET search links work (this branch was dead: it read request.form)
        with app.test_client() as c:
            as_client(c, "C1")
            body = c.get(
                f"/booking?city=Dubrovnik&start_date={START}&end_date={END}"
            ).get_data(as_text=True)
            check("bookmarkable GET search returns results", "Available Boats in" in body)

        # 8b. The two m:n relations are editable from the manager UI. Must run
        #     before section 9 deletes M2 and section 11 turns S1 into a manager.
        def count_supervises(manager_id, staff_id):
            return db.session.execute(
                text("SELECT COUNT(*) FROM Supervises WHERE ManagerID = :m AND StaffID = :s"),
                {"m": manager_id, "s": staff_id},
            ).scalar()

        def count_maintains(staff_id, boat_id):
            return db.session.execute(
                text("SELECT COUNT(*) FROM Maintains WHERE StaffID = :s AND BoatID = :b"),
                {"s": staff_id, "b": boat_id},
            ).scalar()

        with app.test_client() as c:
            as_manager(c, "M1")

            body = c.get("/manager/assignments/supervision").get_data(as_text=True)
            check("supervision page lists the seeded pair",
                  "M2" in body and "S1" in body, body[:300])

            body = c.post("/manager/assignments/supervision", data={
                "manager_id": "M1", "staff_id": "S1", "submit": "Assign supervision",
            }, follow_redirects=True).get_data(as_text=True)
            check("a manager can assign supervision", count_supervises("M1", "S1") == 1, body[:300])

            body = c.post("/manager/assignments/supervision", data={
                "manager_id": "M1", "staff_id": "S1", "submit": "Assign supervision",
            }, follow_redirects=True).get_data(as_text=True)
            check("a duplicate supervision is refused", "already supervises" in body, body[:300])
            check("no second supervision row", count_supervises("M1", "S1") == 1)

            # M2 is a manager, not staff. SelectField.pre_validate must reject
            # this before it ever reaches the INSERT.
            c.post("/manager/assignments/supervision", data={
                "manager_id": "M1", "staff_id": "M2", "submit": "Assign supervision",
            }, follow_redirects=True)
            check("a manager cannot be assigned into the staff slot",
                  count_supervises("M1", "M2") == 0)

            body = c.post("/manager/assignments/supervision/M1/S1/delete",
                          follow_redirects=True).get_data(as_text=True)
            check("supervision can be unassigned", "Supervision removed" in body, body[:300])
            check("the supervision row is gone", count_supervises("M1", "S1") == 0)

            body = c.post("/manager/assignments/supervision/M1/S1/delete",
                          follow_redirects=True).get_data(as_text=True)
            check("unassigning a missing supervision does not 500",
                  "no longer exists" in body, body[:300])

            # Same shape for Maintains. S1 already maintains B1 from the seed.
            body = c.get("/manager/assignments/maintenance").get_data(as_text=True)
            check("maintenance page lists the seeded pair", "B1" in body, body[:300])

            c.post("/manager/assignments/maintenance", data={
                "staff_id": "S1", "boat_id": "B2", "submit": "Assign boat",
            }, follow_redirects=True)
            check("a manager can assign maintenance", count_maintains("S1", "B2") == 1)

            body = c.post("/manager/assignments/maintenance", data={
                "staff_id": "S1", "boat_id": "B2", "submit": "Assign boat",
            }, follow_redirects=True).get_data(as_text=True)
            check("a duplicate maintenance assignment is refused",
                  "already maintains" in body, body[:300])

            body = c.post("/manager/assignments/maintenance/S1/B2/delete",
                          follow_redirects=True).get_data(as_text=True)
            check("maintenance can be unassigned",
                  "Maintenance assignment removed" in body, body[:300])
            check("the maintenance row is gone", count_maintains("S1", "B2") == 0)

        with app.test_client() as c:
            r = c.get("/manager/assignments/supervision")
            check("assignments pages are manager-only", r.status_code == 302,
                  f"status {r.status_code}")

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

        # 13b. A client can cancel a future rental, and only their own.
        far_start = date.today() + timedelta(days=60)
        far_end = far_start + timedelta(days=2)
        with app.test_client() as c:
            as_client(c, "C1")
            search(c, "Dubrovnik", far_start, far_end)
            book(c, "B4", start=far_start, end=far_end)
            check("a far-future rental was booked",
                  Rental.query.filter_by(BoatID="B4", ClientID="C1").count() == 1)

            body = c.get("/report").get_data(as_text=True)
            check("report offers a cancel button for a future rental", "/cancel" in body)

            body = c.post(f"/rentals/B4/{far_start.isoformat()}/cancel",
                          follow_redirects=True).get_data(as_text=True)
            check("a client can cancel a future rental", "cancelled" in body, body[:300])
            check("the cancelled rental is gone",
                  Rental.query.filter_by(BoatID="B4", ClientID="C1").count() == 0)

            # C2 booked B1 for END+10 back in section 6. C1 must not reach it,
            # which is the whole point of taking ClientID from the session.
            c2_start = END + timedelta(days=10)
            body = c.post(f"/rentals/B1/{c2_start.isoformat()}/cancel",
                          follow_redirects=True).get_data(as_text=True)
            check("a client cannot cancel another client's rental",
                  "not on your list" in body, body[:300])
            check("the other client's rental survived",
                  Rental.query.filter_by(ClientID="C2", BoatID="B1",
                                         RentalDate=c2_start).count() == 1)

            # Booking refuses past start dates, so this row can only be made
            # directly -- but the guard still has to hold.
            past = date.today() - timedelta(days=2)
            db.session.add(Rental(ClientID="C1", BoatID="B4", RentalDate=past,
                                  RentalEndDate=date.today() + timedelta(days=1),
                                  PaymentStatus="PAID"))
            db.session.commit()
            body = c.post(f"/rentals/B4/{past.isoformat()}/cancel",
                          follow_redirects=True).get_data(as_text=True)
            check("a started rental cannot be cancelled",
                  "already started" in body, body[:300])
            check("the started rental survived",
                  Rental.query.filter_by(BoatID="B4", RentalDate=past).count() == 1)

            r = c.post("/rentals/B1/banana/cancel", follow_redirects=True)
            check("an unparseable cancel date does not 500", r.status_code == 200,
                  f"status {r.status_code}")
            check("an unparseable cancel date is reported",
                  "Invalid rental date" in r.get_data(as_text=True))

        with app.test_client() as c:
            r = c.post(f"/rentals/B4/{past.isoformat()}/cancel")
            check("an anonymous visitor cannot cancel", r.status_code == 302,
                  f"status {r.status_code}")
            check("the rental survived the anonymous cancel",
                  Rental.query.filter_by(BoatID="B4", RentalDate=past).count() == 1)

        # 13c. The office can call off anyone's charter, including one already
        #      under way -- both things the client route deliberately refuses.
        with app.test_client() as c:
            as_manager(c, "M1")
            body = c.get("/manager/rentals").get_data(as_text=True)
            check("manager sees rentals across clients",
                  "C1" in body or "Max" in body, body[:300])
            check("manager rentals page shows the harbour",
                  "Dubrovnik" in body, body[:300])

            filtered = c.get("/manager/rentals?city=Nice").get_data(as_text=True)
            check("manager rentals filter by city works",
                  "No rentals in Nice" in filtered, filtered[:300])

            # C2's rental, which C1 was refused in 13b.
            c2_start = END + timedelta(days=10)
            body = c.post(f"/manager/rentals/C2/B1/{c2_start.isoformat()}/delete",
                          follow_redirects=True).get_data(as_text=True)
            check("manager can cancel another client's rental",
                  "Cancelled" in body, body[:300])
            check("that rental is gone",
                  Rental.query.filter_by(ClientID="C2", BoatID="B1",
                                         RentalDate=c2_start).count() == 0)

            # A charter under way: starts yesterday, ends next week. The client
            # route refuses this; the office must be able to call it off.
            live_start = date.today() - timedelta(days=1)
            db.session.add(Rental(ClientID="C1", BoatID="B3", RentalDate=live_start,
                                  RentalEndDate=date.today() + timedelta(days=7),
                                  PaymentStatus="PAID"))
            db.session.commit()
            body = c.post(f"/manager/rentals/C1/B3/{live_start.isoformat()}/delete",
                          follow_redirects=True).get_data(as_text=True)
            check("manager can cancel a charter already under way",
                  Rental.query.filter_by(BoatID="B3", RentalDate=live_start).count() == 0,
                  body[:300])

            # A finished charter is the record that it happened.
            done_start = date.today() - timedelta(days=20)
            db.session.add(Rental(ClientID="C1", BoatID="B3", RentalDate=done_start,
                                  RentalEndDate=date.today() - timedelta(days=14),
                                  PaymentStatus="PAID"))
            db.session.commit()
            body = c.post(f"/manager/rentals/C1/B3/{done_start.isoformat()}/delete",
                          follow_redirects=True).get_data(as_text=True)
            check("a finished charter cannot be deleted",
                  "cannot be removed" in body, body[:300])
            check("the finished charter survived",
                  Rental.query.filter_by(BoatID="B3", RentalDate=done_start).count() == 1)

            r = c.post("/manager/rentals/C1/B3/banana/delete", follow_redirects=True)
            check("an unparseable manager cancel date does not 500",
                  r.status_code == 200, f"status {r.status_code}")

        with app.test_client() as c:
            as_client(c, "C1")
            r = c.get("/manager/rentals")
            check("the rentals page is manager-only", r.status_code == 302,
                  f"status {r.status_code}")

        # 14. Client self-registration. Runs before the generate-data section,
        #     which deletes every client.
        def registration(**overrides):
            payload = {
                "first_name": "Nina", "last_name": "Novak",
                "street": "Ilica 1", "zip": "10000", "city": "Zagreb", "country": "Croatia",
                "birthdate": "1995-06-15", "email": "nina@example.com",
                "mobile": "+385 1 234", "captain_license": "CAPT-555001",
                "submit": "Create account",
            }
            payload.update(overrides)
            return payload

        before = Client.query.count()
        with app.test_client() as c:
            body = c.post("/register", data=registration(),
                          follow_redirects=True).get_data(as_text=True)
            check("a new client can register", "Welcome, Nina" in body, body[:300])
            check("client row was written", Client.query.count() == before + 1)
            # Landing on /report at all proves registration signed them in.
            check("registration signs the new client in",
                  c.get("/report").status_code == 200)

            # The real point: the new ClientID has to satisfy the Rental FK.
            search(c, "Dubrovnik")
            body = book(c, "B4").get_data(as_text=True)
            nina = Client.query.filter_by(Email="nina@example.com").first()
            check("a freshly registered client can book",
                  Rental.query.filter_by(ClientID=nina.ClientID).count() == 1, body[:300])

            # Already signed in -> no duplicate account on a refresh.
            c.post("/register", data=registration(email="nina2@example.com",
                                                  captain_license="CAPT-555002"),
                   follow_redirects=True)
            check("a signed-in client cannot register again",
                  Client.query.count() == before + 1)

        with app.test_client() as c:
            body = c.post("/register", data=registration(email="other@example.com"),
                          follow_redirects=True).get_data(as_text=True)
            check("duplicate captain licence is refused", "must be unique" in body, body[:300])
            check("no client row after the refused registration",
                  Client.query.count() == before + 1)

        # A blank licence must be stored as NULL, not "": the column is UNIQUE,
        # and two empty strings would collide where two NULLs do not.
        for i, email in enumerate(("noline1@example.com", "noline2@example.com")):
            with app.test_client() as c:
                c.post("/register", data=registration(email=email, captain_license=""),
                       follow_redirects=True)
        check("two clients can register without a captain licence",
              Client.query.filter_by(CaptainLicenseNumber=None).count() >= 2)

        with app.test_client() as c:
            body = c.post("/register", data=registration(
                email="kid@example.com", captain_license="",
                birthdate=(date.today() - timedelta(days=365 * 10)).isoformat(),
            ), follow_redirects=True).get_data(as_text=True)
            check("an underage client is refused", "at least 18" in body, body[:300])
            check("no client row after the underage registration",
                  Client.query.filter_by(Email="kid@example.com").first() is None)

        with app.test_client() as c:
            body = c.get("/login").get_data(as_text=True)
            check("login page links to registration", "Create an account" in body)

        # 15. generate-data is open to anonymous visitors, but only once per session
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

        # 16. The Generate Data reset runs cleanly and fills the m:n tables
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
