import random
from datetime import datetime, timedelta, date
from sqlalchemy import text

from boat_rental import db

from boat_rental.models import (
    Office,
    Client,
    Boat,
    Rental,
    Yacht,
    Motorboat,
    Catamaran,
    Employee,
    Staff,
    Manager
)


def generate_data():
    try:
        db.session.execute(text("DELETE FROM `Maintains`"))
        db.session.execute(text("DELETE FROM `Supervises`"))


        db.session.query(Rental).delete()
        db.session.query(Staff).delete()

        db.session.execute(text("UPDATE `Manager` SET `SupervisorID` = NULL"))
        
        db.session.query(Manager).delete()
        db.session.query(Employee).delete()

        db.session.query(Yacht).delete()
        db.session.query(Motorboat).delete()
        db.session.query(Catamaran).delete()
        db.session.query(Boat).delete()
        db.session.query(Client).delete()
        db.session.query(Office).delete()


        offices = [
            Office(
                OfficeID="O1",
                Street="Tourlos Marina",
                Country="Greece",
                City="Mykonos",
                ZIP="84600",
            ),
            Office(
                OfficeID="O2",
                Street="Quai des Docks",
                Country="France",
                City="Nice",
                ZIP="06000",
            ),
            Office(
                OfficeID="O3",
                Street="Moll de la Barceloneta, 1",
                Country="Spain",
                City="Barcelona",
                ZIP="08039",
            ),
            Office(
                OfficeID="O4",
                Street="Old Port of Fira",
                Country="Greece",
                City="Santorini",
                ZIP="84700",
            ),
            Office(
                OfficeID="O5",
                Street="Obala Stjepana Radića, 2",
                Country="Croatia",
                City="Dubrovnik",
                ZIP="20000",
            ),
        ]
        for office in offices:
            db.session.add(office)

        db.session.flush()

        do_employees(offices)
        do_clients()
        do_boats(offices)
        do_rentals()

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print("generate_data failed:", e)
        raise


def do_clients():
    first_names = [
        "Max",
        "Olga",
        "Fabio",
        "Anna",
        "John",
        "Sarah",
        "Mike",
        "Lisa",
        "Tom",
        "Emma",
    ]
    last_names = [
        "Mustermann",
        "Primerova",
        "Exemplario",
        "Schmidt",
        "Doe",
        "Johnson",
        "Brown",
        "Wilson",
    ]
    countries = ["Austria", "Germany", "Italy", "France", "Spain"]
    cities = ["Vienna", "Berlin", "Rome", "Paris", "Madrid"]

    for i in range(10):
        client = Client(
            ClientID=f"C{i + 1}",
            FirstName=random.choice(first_names),
            LastName=random.choice(last_names),
            Street=f"Test Street {i + 1}",
            ZIP=f"{random.randint(10000, 99999)}",
            Country=random.choice(countries),
            City=random.choice(cities),
            Birthdate=date(
                random.randint(1970, 2000),
                random.randint(1, 12),
                random.randint(1, 28),
            ),
            Email=f"client{i}@example.com",
            MobileNumber=f"+{random.randint(1, 74)}-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
            CaptainLicenseNumber=f"CAPT-{random.randint(100000, 999999)}",
        )
        db.session.add(client)


def do_boats(offices):
    boat_type = ["yacht", "motorboat", "catamaran"]
    availability_status = ["Available", "Maintenance"]

    for i in range(100):
        boat = Boat(
            BoatID=f"B{i + 1}",
            OfficeID=random.choice(offices).OfficeID,
            Length=random.randint(5, 30),
            Seats=random.randint(2, 10),
            Manufacturer=f"Manufacturer{random.randint(1, 5)}",
            AvailabilityStatus=random.choice(availability_status),
            Weight=random.uniform(500.0, 5000.0),
            Horsepower=random.randint(50, 300),
        )
        db.session.add(boat)

        boat_type_choice = random.choice(boat_type)
        concrete_boat = None
        if boat_type_choice == "yacht":
            concrete_boat = Yacht(
                YachtID=boat.BoatID,
                YachtName=f"Yacht {i + 1}",
                HasJacuzzi=random.choice([True, False]),
            )
        elif boat_type_choice == "motorboat":
            concrete_boat = Motorboat(
                MotorboatID=boat.BoatID,
                EngineType=random.choice(["Inboard", "Outboard"]),
                FuelType=random.choice(["Diesel", "Benzin"]),
            )
        elif boat_type_choice == "catamaran":
            concrete_boat = Catamaran(
                CatamaranID=boat.BoatID,
                NrOfCabins=random.randint(1, 5),
                MaxCapacity=random.randint(4, 20),
            )

        db.session.add(concrete_boat)


def do_rentals():
    clients = Client.query.all()
    boats = Boat.query.filter_by(AvailabilityStatus="Available").all()

    for i in range(10):
        rental_date = date.today() + timedelta(days=random.randint(-30, 30))
        rental_end_date = rental_date + timedelta(days=random.randint(1, 14))
        rental = Rental(
            ClientID=random.choice(clients).ClientID,
            BoatID=random.choice(boats).BoatID,
            RentalDate=rental_date,
            RentalEndDate=rental_end_date,
            PaymentStatus=random.choice(["PAID", "UNPAID", "PENDING"]),
        )
        try:
            db.session.add(rental)
            db.session.commit()
        except Exception as e:
            db.session.rollback()


def do_employees(offices):
    first_names = [
        "Alex",
        "Jamie",
        "Taylor",
        "Jordan", 
        "Casey",
        "Riley",
        "Sam",
        "Morgan",
        "Avery",
        "Quinn"
    ]

    last_names = [
        "Smith",
        "Johnson",
        "Brown",
        "Davis",
        "Miller",
        "Wilson",
        "Moore",
        "Taylor", 
        "Anderson",
        "Thomas"
    
    ]
    managers = []

    # staff
    for i in range(6):
        fn, ln = random.choice(first_names), random.choice(last_names)
        emp = Employee(
            EmployeeID=f"E{i+1}",
            OfficeID=random.choice(offices).OfficeID,
            FirstName=fn, LastName=ln,
            Street="Main Street 1", ZIP="1000", Country="Country", City="City",
            Birthdate=date(1990, random.randint(1, 12), random.randint(1, 28)),
            Email=f"{fn.lower()}.{ln.lower()}@example.com",
            MobileNumber=f"+1-555-{random.randint(100,999)}-{random.randint(1000,9999)}",
            SelfInsuranceNr=f"INS-{random.randint(1000000, 9999999)}",
            Salary=random.randint(32000, 65000)
        )
        db.session.add(emp)
        db.session.add(Staff(StaffID=emp.EmployeeID, WorkShift=random.choice(["Day","Night"]), IsOnDuty=random.choice([True, False])))

    # managers
    for i in range(3):
        fn, ln = random.choice(first_names), random.choice(last_names)
        idx = i + 7
        emp = Employee(
            EmployeeID=f"E{idx}",
            OfficeID=random.choice(offices).OfficeID,
            FirstName=fn, LastName=ln,
            Street="Harbor Road 2", ZIP="2000", Country="Country", City="City",
            Birthdate=date(1985, random.randint(1, 12), random.randint(1, 28)),
            Email=f"{fn.lower()}.{ln.lower()}@example.com",
            MobileNumber=f"+1-555-{random.randint(100,999)}-{random.randint(1000,9999)}",
            SelfInsuranceNr=f"INS-{random.randint(1000000, 9999999)}",
            Salary=random.randint(70000, 140000)
        )
        db.session.add(emp)
        m = Manager(ManagerID=emp.EmployeeID, Department=random.choice(["Sales","Ops","HR"]), ManagementLevel=random.choice(["L1","L2","L3"]), SupervisorID=None)
        db.session.add(m)
        managers.append(m)

    # simple supervisor chain
    if len(managers) >= 2:
        sup_id = managers[0].ManagerID
        for m in managers[1:]:
            m.SupervisorID = sup_id

    db.session.commit()
