-- This query returns all available boats that are not booked in Dubrovnik

SET @desiredCity = 'Dubrovnik';
SET @desiredStart = '2025-07-01';
SET @desiredEnd   = '2025-07-05';

SELECT 
  b.BoatID,
  b.Length,
  b.Seats,
  b.Manufacturer,
  b.Weight,
  b.Horsepower
FROM Boat b
JOIN Office o 
  ON b.OfficeID = o.OfficeID
WHERE o.City = @desiredCity
  AND b.AvailabilityStatus = 'Available'
  AND NOT EXISTS (
    SELECT 1
    FROM Rental r
    WHERE r.BoatID = b.BoatID
      AND r.RentalDate < @desiredEnd
      AND r.RentalEndDate > @desiredStart
  );
