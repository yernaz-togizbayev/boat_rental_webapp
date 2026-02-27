-- Query to retrieve staff information along with their manager's name and office details which they assigned to.
-- This query retrieves the StaffID, StaffFirstName, StaffLastName, IsOnDuty status, City, Country, and ManagerName for all staff members supervised by the HR manager (M2).
SELECT
    s.StaffID,
    se.FirstName AS StaffFirstName,
    se.LastName AS StaffLastName,
    s.IsOnDuty,
    o.City,
    o.Country,
    CONCAT(me.FirstName, ' ', me.LastName) AS ManagerName
FROM Supervises sup
JOIN Staff s ON sup.StaffID = s.StaffID
JOIN Employee se ON s.StaffID = se.EmployeeID
JOIN Employee me ON sup.ManagerID = me.EmployeeID
JOIN Manager m ON m.ManagerID = me.EmployeeID
JOIN Office o ON se.OfficeID = o.OfficeID
WHERE m.ManagerID = 'M2';