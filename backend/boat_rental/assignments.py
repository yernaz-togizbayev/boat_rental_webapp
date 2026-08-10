from sqlalchemy import text

from boat_rental import db


def list_supervises():
    return db.session.execute(text("""
        SELECT s.`ManagerID`  AS ManagerID,
               me.`FirstName` AS ManagerFirst,
               me.`LastName`  AS ManagerLast,
               s.`StaffID`    AS StaffID,
               se.`FirstName` AS StaffFirst,
               se.`LastName`  AS StaffLast
        FROM `Supervises` s
        JOIN `Employee` me ON me.`EmployeeID` = s.`ManagerID`
        JOIN `Employee` se ON se.`EmployeeID` = s.`StaffID`
        ORDER BY me.`LastName`, se.`LastName`
    """)).mappings().all()


def add_supervises(manager_id, staff_id):
    db.session.execute(
        text("INSERT INTO `Supervises` (`ManagerID`, `StaffID`) VALUES (:m, :s)"),
        {"m": manager_id, "s": staff_id},
    )


def remove_supervises(manager_id, staff_id):
    """Delete one link. Returns the row count so the caller can tell a real
    removal from a stale button press."""
    return db.session.execute(
        text("DELETE FROM `Supervises` WHERE `ManagerID` = :m AND `StaffID` = :s"),
        {"m": manager_id, "s": staff_id},
    ).rowcount


def list_maintains():
    """Every maintenance link, with the staff name and the boat's home city."""
    return db.session.execute(text("""
        SELECT m.`StaffID`      AS StaffID,
               e.`FirstName`    AS StaffFirst,
               e.`LastName`     AS StaffLast,
               m.`BoatID`       AS BoatID,
               b.`Manufacturer` AS Manufacturer,
               o.`City`         AS City
        FROM `Maintains` m
        JOIN `Employee` e ON e.`EmployeeID` = m.`StaffID`
        JOIN `Boat` b     ON b.`BoatID`     = m.`BoatID`
        JOIN `Office` o   ON o.`OfficeID`   = b.`OfficeID`
        ORDER BY e.`LastName`, m.`BoatID`
    """)).mappings().all()


def add_maintains(staff_id, boat_id):
    db.session.execute(
        text("INSERT INTO `Maintains` (`StaffID`, `BoatID`) VALUES (:s, :b)"),
        {"s": staff_id, "b": boat_id},
    )


def remove_maintains(staff_id, boat_id):
    return db.session.execute(
        text("DELETE FROM `Maintains` WHERE `StaffID` = :s AND `BoatID` = :b"),
        {"s": staff_id, "b": boat_id},
    ).rowcount


def detach_manager_links(emp_id):
    """Clear the references that block removing a Manager row."""
    db.session.execute(
        text("UPDATE `Manager` SET `SupervisorID` = NULL WHERE `SupervisorID` = :id"),
        {"id": emp_id},
    )
    db.session.execute(
        text("DELETE FROM `Supervises` WHERE `ManagerID` = :id"), {"id": emp_id}
    )


def detach_staff_links(emp_id):
    """Clear the references that block removing a Staff row."""
    db.session.execute(
        text("DELETE FROM `Supervises` WHERE `StaffID` = :id"), {"id": emp_id}
    )
    db.session.execute(
        text("DELETE FROM `Maintains` WHERE `StaffID` = :id"), {"id": emp_id}
    )


def detach_boat_links(boat_id):
    """Clear the references that block removing a Boat row."""
    db.session.execute(
        text("DELETE FROM `Maintains` WHERE `BoatID` = :id"), {"id": boat_id}
    )
