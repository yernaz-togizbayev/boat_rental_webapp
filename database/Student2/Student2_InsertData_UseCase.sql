-- Insert a new Employee, Staff and Supervises to simulate a new hire use case
INSERT INTO Employee VALUES (
  'S8', 'O1', 'Lena', 'Karras', 'Seaside Road 11', '84600', 'Greece', 'Mykonos', '1993-06-15', 'lena@boat-rental.com', '+30111222333', '0987254121', 3300.00
);
INSERT INTO Staff VALUES ('S8', 'Evening', TRUE); -- Lena Karras is a new staff member with evening shift

INSERT INTO Supervises VALUES ('M2', 'S8'); -- HR hires Lena Karras (S8)