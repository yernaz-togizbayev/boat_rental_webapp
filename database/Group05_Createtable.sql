--  -- Create a database for a boat rental system
-- CREATE DATABASE boat_rental;
--
-- -- Use the created database
-- USE boat_rental;

-- Office
CREATE TABLE IF NOT EXISTS Office (
  OfficeID VARCHAR(50) PRIMARY KEY,
  Street VARCHAR(100) NOT NULL,
  Country VARCHAR(50) NOT NULL,
  City VARCHAR(50) NOT NULL,
  ZIP VARCHAR(10) NOT NULL
);

-- Employee (superclass for Staff and Manager)
CREATE TABLE IF NOT EXISTS Employee (
    EmployeeID VARCHAR(50) PRIMARY KEY,
    OfficeID VARCHAR(50) NOT NULL,
    FirstName VARCHAR(50) NOT NULL,
    LastName VARCHAR(50) NOT NULL,
    Street VARCHAR(100),
    ZIP VARCHAR(10),
    Country VARCHAR(50),
    City VARCHAR(50),
    Birthdate DATE NOT NULL,
    Email VARCHAR(100) NOT NULL,
    MobileNumber VARCHAR(20),
    SelfInsuranceNr  VARCHAR(20) NOT NULL UNIQUE,
    Salary DECIMAL(10,2) NOT NULL,
    CONSTRAINT FK_employee_officeID FOREIGN KEY (OfficeID) REFERENCES Office(OfficeID)
);

-- Staff (IS-A Employee)
CREATE TABLE IF NOT EXISTS Staff (
    StaffID VARCHAR(50) PRIMARY KEY,
    WorkShift VARCHAR(50) NOT NULL,
    IsOnDuty BOOLEAN NOT NULL,
    CONSTRAINT FK_staff_employeeID FOREIGN KEY (StaffID) REFERENCES Employee(EmployeeID)
);

-- Manager (IS-A Employee)
CREATE TABLE IF NOT EXISTS Manager (
    ManagerID VARCHAR(50) PRIMARY KEY,
    Department VARCHAR(50),
    ManagementLevel VARCHAR(50),
    SupervisorID VARCHAR(50),
    CONSTRAINT FK_manager_employeeID FOREIGN KEY (ManagerID) REFERENCES Employee(EmployeeID),
    CONSTRAINT FK_manager_supervisorID FOREIGN KEY (SupervisorID) REFERENCES Manager(ManagerID)
);

-- Client
CREATE TABLE IF NOT EXISTS Client (
    ClientID VARCHAR(50) PRIMARY KEY,
    FirstName VARCHAR(50) NOT NULL,
    LastName VARCHAR(50) NOT NULL,
    Street VARCHAR(100),
    ZIP VARCHAR(10),
    Country VARCHAR(50),
    City VARCHAR(50),
    Birthdate DATE NOT NULL,
    Email VARCHAR(100) NOT NULL,
    MobileNumber VARCHAR(20),
    CaptainLicenseNumber VARCHAR(50) UNIQUE
);

-- Boat
CREATE TABLE IF NOT EXISTS Boat (
    BoatID VARCHAR(50) PRIMARY KEY,
	OfficeID VARCHAR(50) NOT NULL,
    Length FLOAT,
    Seats INT,
    Manufacturer VARCHAR(50),
    AvailabilityStatus VARCHAR(20),
    Weight FLOAT,
    Horsepower INT,
    -- What the boat costs per day. The charter total is stored on the Rental
    -- rather than recomputed from this, so changing a rate never rewrites the
    -- price of a booking someone has already paid.
    DailyRate DECIMAL(10,2),
	CONSTRAINT FK_boat_officeID FOREIGN KEY (OfficeID) REFERENCES Office(OfficeID)
);

-- Rental (weak entity)
CREATE TABLE IF NOT EXISTS Rental (
    ClientID VARCHAR(50) NOT NULL,
    BoatID VARCHAR(50) NOT NULL,
    RentalDate DATE NOT NULL,
    RentalEndDate DATE,
    PaymentStatus VARCHAR(20),
    -- Agreed at booking time: DailyRate x days, frozen here.
    TotalAmount DECIMAL(10,2),
    -- Handover time on RentalDate. Kept separate from RentalDate so the
    -- primary key stays a date and a charter still means one boat per day.
    StartTime TIME,
    -- When the booking was made. An unpaid booking is only a hold, and the
    -- deadline for paying it is measured against both the ride and this.
    CreatedAt DATETIME,
    CONSTRAINT PK_rental PRIMARY KEY (ClientID, BoatID, RentalDate),
    CONSTRAINT FK_rental_clientID FOREIGN KEY (ClientID) REFERENCES Client(ClientID),
    CONSTRAINT FK_rental_boatID FOREIGN KEY (BoatID) REFERENCES Boat(BoatID)
);

-- Yacht (IS-A Boat)
CREATE TABLE IF NOT EXISTS Yacht (
    YachtID VARCHAR(50) PRIMARY KEY,
    YachtName VARCHAR(50),
    HasJacuzzi BOOLEAN,
    CONSTRAINT FK_yacht_boat FOREIGN KEY (YachtID) REFERENCES Boat(BoatID)
);

-- Motorboat (IS-A Boat)
CREATE TABLE IF NOT EXISTS Motorboat (
    MotorboatID VARCHAR(50) PRIMARY KEY,
    EngineType VARCHAR(50),
    FuelType VARCHAR(50),
    CONSTRAINT FK_motorboat_boat FOREIGN KEY (MotorboatID) REFERENCES Boat(BoatID)
);

-- Catamaran (IS-A Boat)
CREATE TABLE IF NOT EXISTS Catamaran (
    CatamaranID VARCHAR(50) PRIMARY KEY,
    NrOfCabins INT,
    MaxCapacity INT,
    HasJacuzzi BOOLEAN,
    CONSTRAINT FK_catamaran_boat FOREIGN KEY (CatamaranID) REFERENCES Boat(BoatID)
);

-- Supervises (m:n Manager-Staff)
CREATE TABLE IF NOT EXISTS Supervises (
    ManagerID VARCHAR(50),
    StaffID VARCHAR(50),
    CONSTRAINT PK_Supervises PRIMARY KEY (ManagerID, StaffID),
    CONSTRAINT FK_Supervises_Manager FOREIGN KEY (ManagerID) REFERENCES Manager(ManagerID),
    CONSTRAINT FK_Supervises_Staff FOREIGN KEY (StaffID) REFERENCES Staff(StaffID)
);

-- Maintains (m:n Staff-Boat)
CREATE TABLE IF NOT EXISTS Maintains (
    StaffID VARCHAR(50) NOT NULL,
    BoatID VARCHAR(50) NOT NULL,
    PRIMARY KEY (StaffID, BoatID),
    FOREIGN KEY (StaffID) REFERENCES Staff(StaffID),
    FOREIGN KEY (BoatID) REFERENCES Boat(BoatID)
);
