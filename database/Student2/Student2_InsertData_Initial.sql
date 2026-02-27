use boat_rental;

-- Initial Data for Office
INSERT INTO Office (OfficeID, Street, Country, City, ZIP) VALUES
('O1', 'Tourlos Marina​', 'Greece', 'Mykonos', '84600'),
('O2', 'Quai des Docks', 'France', 'Nice', '06000'),
('O3', 'Moll de la Barceloneta, 1', 'Spain', 'Barcelona', '08039'),
('O4', 'Old Port of Fira', 'Greece', 'Santorini', '84700'),
('O5', 'Obala Stjepana Radića, 2​', 'Croatia', 'Dubrovnik', '20000');

-- Initial Data for Employee
INSERT INTO Employee VALUES
('M1', 'O1', 'John', 'Doe', 'Main Street, 5', '54321', 'Greece', 'Mykonos', '1990-05-15', 'john.doe@boat-rental.com', '+30123456780', '0987654321', 10000.00),
('M2', 'O1', 'Anna', 'Smith', 'Beautiful Street, 3', '12345', 'Greece', 'Mykonos', '1980-01-01', 'anna.smith@boat-rental.com', '+30123456789', '1234567890', 6000.00),
('S1', 'O1', 'Jane', 'Doe', 'Second Street, 10', '67890', 'Greece', 'Mykonos', '1985-03-20', 'jane.doe@boat-rental.com', '+30123456781', '1122334455', 3500.00),
('S2', 'O1', 'Emily', 'Brown', 'Third Street, 15', '11111', 'Greece', 'Mykonos', '1992-07-10', 'emily.brown@boat-rental.com', '+30123456782', '2233445566', 3000.00),
('S3', 'O1', 'Michael', 'Johnson', 'Fourth Street, 20', '22222', 'Greece', 'Mykonos', '1988-11-25', 'michael.johnson@boat-rental.com', '+30123456783', '3344556677', 2800.00),
('S4', 'O1', 'Sophia', 'Davis', 'Fifth Street, 25', '33333', 'Greece', 'Mykonos', '1995-02-14', 'sophia.davis@boat-rental.com', '+30123456784', '4455667788', 3700.00)

-- Initial Data for Manager (CEO and HR)
INSERT INTO Manager VALUES
('M1', 'Executive', 'Top', NULL),
('M2', 'HR', 'Senior', 'M1');

-- Initial Data for Staff Member
INSERT INTO Staff VALUES
('S1', 'Morning', TRUE),
('S2', 'Evening', FALSE),
('S3', 'Night', FALSE),
('S4', 'Morning', TRUE);

-- Supervises relationship
INSERT INTO Supervises (ManagerID, StaffID) VALUES
('M2', 'S1'),  -- HR supervises S1 (Jane Doe)
('M2', 'S2');  -- HR supervises S2 (Emily Brown)