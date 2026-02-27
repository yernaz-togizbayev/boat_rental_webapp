from boat_rental import db


class Office(db.Model):
    __tablename__ = "Office"
    OfficeID = db.Column(db.String(50), primary_key=True)
    Street = db.Column(db.String(100), nullable=False)
    Country = db.Column(db.String(50), nullable=False)
    City = db.Column(db.String(50), nullable=False)
    ZIP = db.Column(db.String(10), nullable=False)

    boats = db.relationship("Boat", backref="office", lazy=True)
    employees = db.relationship("Employee", backref="office", lazy=True)


class Client(db.Model):
    __tablename__ = "Client"
    ClientID = db.Column(db.String(50), primary_key=True)
    FirstName = db.Column(db.String(50), nullable=False)
    LastName = db.Column(db.String(50), nullable=False)
    Street = db.Column(db.String(100))
    ZIP = db.Column(db.String(10))
    Country = db.Column(db.String(50))
    City = db.Column(db.String(50))
    Birthdate = db.Column(db.Date, nullable=False)
    Email = db.Column(db.String(100), nullable=False)
    MobileNumber = db.Column(db.String(20))
    CaptainLicenseNumber = db.Column(db.String(50), unique=True)

    rentals = db.relationship("Rental", backref="client", lazy=True)

    @property
    def full_name(self):
        return f"{self.FirstName} {self.LastName}"


class Boat(db.Model):
    __tablename__ = "Boat"
    BoatID = db.Column(db.String(50), primary_key=True)
    OfficeID = db.Column(
        db.String(50), db.ForeignKey("Office.OfficeID"), nullable=False
    )
    Length = db.Column(db.Float)
    Seats = db.Column(db.Integer)
    Manufacturer = db.Column(db.String(50))
    AvailabilityStatus = db.Column(db.String(20))
    Weight = db.Column(db.Float)
    Horsepower = db.Column(db.Integer)

    rentals = db.relationship("Rental", backref="boat", lazy=True)
    yacht = db.relationship("Yacht", backref="boat_ref", uselist=False)
    motorboat = db.relationship("Motorboat", backref="boat_ref", uselist=False)
    catamaran = db.relationship("Catamaran", backref="boat_ref", uselist=False)


class Rental(db.Model):
    __tablename__ = "Rental"
    ClientID = db.Column(
        db.String(50), db.ForeignKey("Client.ClientID"), nullable=False
    )
    BoatID = db.Column(db.String(50), db.ForeignKey("Boat.BoatID"), nullable=False)
    RentalDate = db.Column(db.Date, nullable=False)
    RentalEndDate = db.Column(db.Date)
    PaymentStatus = db.Column(db.String(20))

    __table_args__ = (db.PrimaryKeyConstraint("ClientID", "BoatID", "RentalDate"),)

    @property
    def rental_days(self):
        if self.RentalEndDate and self.RentalDate:
            return (self.RentalEndDate - self.RentalDate).days
        return 0


class Yacht(db.Model):
    __tablename__ = "Yacht"
    YachtID = db.Column(db.String(50), db.ForeignKey("Boat.BoatID"), primary_key=True)
    YachtName = db.Column(db.String(50))
    HasJacuzzi = db.Column(db.Boolean)


class Motorboat(db.Model):
    __tablename__ = "Motorboat"
    MotorboatID = db.Column(
        db.String(50), db.ForeignKey("Boat.BoatID"), primary_key=True
    )
    EngineType = db.Column(db.String(50))
    FuelType = db.Column(db.String(50))


class Catamaran(db.Model):
    __tablename__ = "Catamaran"
    CatamaranID = db.Column(
        db.String(50), db.ForeignKey("Boat.BoatID"), primary_key=True
    )
    NrOfCabins = db.Column(db.Integer)
    MaxCapacity = db.Column(db.Integer)


class Employee(db.Model):
    __tablename__ = "Employee"
    EmployeeID = db.Column(db.String(50), primary_key=True)
    OfficeID = db.Column(
        db.String(50), db.ForeignKey("Office.OfficeID"), nullable=False
    )
    FirstName = db.Column(db.String(50), nullable=False)
    LastName = db.Column(db.String(50), nullable=False)
    Street = db.Column(db.String(100))
    ZIP = db.Column(db.String(10))
    Country = db.Column(db.String(50))
    City = db.Column(db.String(50))
    Birthdate = db.Column(db.Date, nullable=False)
    Email = db.Column(db.String(100), nullable=False)
    MobileNumber = db.Column(db.String(20))
    SelfInsuranceNr = db.Column(db.String(20), nullable=False, unique=True)
    Salary = db.Column(db.Numeric(10, 2), nullable=False)


class Staff(db.Model):
    __tablename__ = "Staff"
    StaffID = db.Column(
        db.String(50), db.ForeignKey("Employee.EmployeeID"), primary_key=True
    )
    WorkShift = db.Column(db.String(50), nullable=False)
    IsOnDuty = db.Column(db.Boolean, nullable=False)


class Manager(db.Model):
    __tablename__ = "Manager"
    ManagerID = db.Column(
        db.String(50), db.ForeignKey("Employee.EmployeeID"), primary_key=True
    )
    Department = db.Column(db.String(50))
    ManagementLevel = db.Column(db.String(50))
    SupervisorID = db.Column(db.String(50), db.ForeignKey("Manager.ManagerID"))
