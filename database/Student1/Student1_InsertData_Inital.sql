USE boat_rental;

INSERT INTO Client (ClientID, FirstName, LastName, Street, ZIP, Country, City, Birthdate, Email, MobileNumber, CaptainLicenseNumber) VALUES
("C123", "Max", "Mustermann", "Bergergasse 8-10/7/15", "1080", "Austria", "Vienna", "1990-01-01", "max.mustermann@example.com", "+43-555-123-4567", "CAPT-123456"),
("C213", "Olga", "Primerova", "Potsdamer Str. 1", "10115", "Germany", "Berlin", "1985-02-15", "olga.primerova@example.com", "+49-30-123-4567", "CAPT-234567"),
("C984", "Fabio", "Exemplario", "Via di Vittorio Emanuele II, 1", "00186", "Italy", "Rome", "1992-03-10", "fabio.exemplario@example.com", "+39-06-123-4567", "CAPT-345678");

INSERT INTO Office (OfficeID, Street, Country, City, ZIP) VALUES
('O1', 'Tourlos Marina​', 'Greece', 'Mykonos', '84600'),
('O2', 'Quai des Docks', 'France', 'Nice', '06000'),
('O3', 'Moll de la Barceloneta, 1', 'Spain', 'Barcelona', '08039'),
('O4', 'Old Port of Fira', 'Greece', 'Santorini', '84700'),
('O5', 'Obala Stjepana Radića, 2​', 'Croatia', 'Dubrovnik', '20000');

INSERT INTO Boat (BoatID, OfficeID, Length, Seats, Manufacturer, AvailabilityStatus, Weight, Horsepower) VALUES
("B100", "O1", 14, 8, "Manufacturer1", "Available", 1200.0, 90),
("B101", "O2", 20, 12, "Manufacturer2", "Maintenance", 2400.0, 120),
("B200", "O3", 6, 4, "Manufacturer3", "Available", 900.0, 50),
("B201", "O5", 10, 6, "Manufacturer3", "Available", 1100.0, 70),
("B300", "O5", 15, 8, "Manufacturer1", "Available", 1300.0, 50),
("B301", "O5", 25, 16, "Manufacturer3", "Maintenance", 4000.0, 150);

INSERT INTO Yacht (YachtID, YachtName, HasJacuzzi) VALUES
("B100", "Golden Pearl", TRUE),
("B101", "Silver Wave", FALSE);

INSERT INTO Motorboat (MotorboatID, EngineType, FuelType) VALUES
("B200", "Inboard", "Diesel"),
("B201", "Outboard", "Benzin");

INSERT INTO Catamaran (CatamaranID, NrOfCabins, MaxCapacity) VALUES
("B300", 4, 16),
("B301", 5, 20);

INSERT INTO Rental (ClientID, BoatID, RentalDate, RentalEndDate, PaymentStatus) VALUES
("C123", "B100", "2025-05-01", "2025-05-03", "PAID"),
("C213", "B101", "2025-06-10", "2025-06-12", "UNPAID");
