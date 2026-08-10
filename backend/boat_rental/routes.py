from flask import flash, redirect, request, render_template, session, url_for
from datetime import datetime, date, timedelta
from sqlalchemy import and_, select, or_, text
from sqlalchemy.exc import IntegrityError
from functools import wraps
from uuid import uuid4

from boat_rental.forms import BoatSelectionForm, BookingSearchForm, ManagerLoginForm, EmployeeHireForm, EmployeeEditForm, ConfirmDeleteForm
from boat_rental import app, db
from boat_rental.generator import generate_data
from boat_rental.models import (
    AVAILABILITY_AVAILABLE,
    Office,
    Client,
    Boat,
    Rental,
    Employee,
    Staff,
    Manager
)

# Role session helpers
EXCLUSIVE_SESSION_KEYS = ("manager", "client")

def sign_in(role, payload):
    # clear any other role
    for key in EXCLUSIVE_SESSION_KEYS:
        if key != role:
            session.pop(key, None)

    match role:
        case "manager":
            session["manager"] = payload

        case "client":
            session["client"] = payload

        case _:
            raise ValueError(f"Unknown role: {role}")

def sign_out():
    """Drop both role keys, leaving the rest of the session intact.

    Deliberately not session.clear() -- that would also drop `data_generated`,
    and the seed button would come back every time someone logs out.
    """
    for key in EXCLUSIVE_SESSION_KEYS:
        session.pop(key, None)

def manager_required(f):
    @wraps(f)
    def _wrapped(*args, **kwargs):
        match True:
            case _ if 'manager' in session:
                return f(*args, **kwargs)
            
            case _ if 'client' in session:
                flash("Please sign in as a manager to access this page.", "error")
                return redirect(url_for("manager_login"))
            
            case _:
                return redirect(url_for("manager_login"))
            
    return _wrapped

@app.route("/", methods=["GET", "POST"])
def index():
    return redirect(url_for("login"))


@app.route("/login")
def login():
    clients = Client.query.all()
    return render_template("login.html", clients=clients)


@app.route("/logout")
def logout():
    sign_out()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


@app.route("/select-client/<client_id>")
def select_client(client_id):
    client = Client.query.get(client_id)

    if not client:
        flash(f"Unknown client {client_id}.", "error")
        return redirect(url_for("login"))

    sign_in('client',
            {
                "ClientID":  client.ClientID,
                "FirstName": client.FirstName,
                "LastName":  client.LastName,
                "FullName":  client.full_name,
                "Email":     client.Email,
            }
        )
    return redirect(url_for("home"))


@app.route("/home")
def home():
    if "manager" in session:
        return redirect(url_for("list_employees"))

    if "client" not in session:
        return redirect(url_for("login"))

    return render_template("home.html", client=session["client"])


@app.route("/booking", methods=["GET", "POST"])
def booking():
    if "client" not in session:
        return redirect(url_for("login"))

    search_form = BookingSearchForm()
    booking_form = None
    available_boats = []
    search_params = {}
    rental_days = 0

    if request.method == "POST" and request.form.get("book"):
        search_params = parse_search_params(
            request.form, "rental_date", "rental_end_date"
        )
        if search_params and attempt_booking(search_params):
            return redirect(url_for("report"))
    elif search_form.validate_on_submit():
        search_params = {
            "city": search_form.city.data,
            "start_date": search_form.start_date.data,
            "end_date": search_form.end_date.data,
        }
    elif request.method == "GET" and request.args.get("city"):
        search_params = parse_search_params(request.args)
        if search_params:
            search_form.city.data = search_params["city"]
            search_form.start_date.data = search_params["start_date"]
            search_form.end_date.data = search_params["end_date"]

    if search_params:
        available_boats = get_available_boats(**search_params)
        booking_form = build_booking_form(search_params, available_boats)
        rental_days = (search_params["end_date"] - search_params["start_date"]).days

    return render_template(
        "booking.html",
        search_form=search_form,
        booking_form=booking_form,
        available_boats=available_boats,
        search_params=search_params,
        rental_days=rental_days,
    )


@app.route("/report")
def report():
    if "client" not in session:
        return redirect(url_for("login"))

    rentals = (
        db.session.query(Rental)
        .filter(Rental.ClientID == session.get("client").get("ClientID"))
        .all()
    )
    return render_template("report.html", rentals=rentals)


@app.route("/analytics")
def analytics():
    if "client" not in session:
        return redirect(url_for("login"))

    offices = Office.query.all()
    filtered_city = request.args.get("city") or "Dubrovnik"

    default_start = date.today()
    default_end = default_start + timedelta(days=7)
    start_date = parse_date_arg("start_date", default_start)
    end_date = parse_date_arg("end_date", default_end)

    if end_date <= start_date:
        flash("End date must be after start date — showing the default range.", "warning")
        start_date, end_date = default_start, default_end

    available_boats = get_available_boats(filtered_city, start_date, end_date)

    total_boats = Boat.query.count()
    available_count = Boat.query.filter_by(
        AvailabilityStatus=AVAILABILITY_AVAILABLE
    ).count()
    rentals_in_period = (
        db.session.query(Rental)
        .filter(rental_overlap_filter(start_date, end_date))
        .count()
    )
    period_days = (end_date - start_date).days

    return render_template(
        "analytics.html",
        boats=available_boats,
        current_filter=filtered_city,
        start_date=start_date,
        end_date=end_date,
        period_days=period_days,
        total_boats=total_boats,
        available_count=available_count,
        rentals_in_period=rentals_in_period,
        offices=offices,
    )


@app.route("/generate-data", methods=["POST"])
def reset_data():
    """Seed the demo data once per browser session.

    The button that posts here is offered to anonymous visitors, so the
    one-shot guard is the session flag below rather than a role check: once
    this browser has generated the data, the button is gone and a replayed
    POST is refused. Nothing stops a fresh session from wiping the DB again --
    that is acceptable for a demo app with no passwords.
    """
    if session.get("data_generated"):
        flash("Demo data has already been generated.", "warning")
        return redirect(url_for("login"))

    try:
        generate_data()
    except Exception:
        app.logger.exception("Data generation failed")
        flash("Could not generate the demo data.", "error")
        return redirect(url_for("login"))

    # generate_data() deletes the clients and managers a signed-in visitor
    # would be pointing at, so drop the role keys.
    sign_out()
    session["data_generated"] = True
    flash("Demo data generated. Please sign in.", "success")
    return redirect(url_for("login"))


def attempt_booking(params):
    """Validate a booking POST against live availability and store the rental.

    Returns True only if the rental was written. Everything the browser sends
    is untrusted here: boat_id is a <select> and both dates are hidden fields,
    all of which can be edited before submission. So rather than trusting the
    list of boats the client was originally shown, this re-derives what is
    bookable right now and validates the choice against that.
    """
    if params["start_date"] < date.today():
        flash("Rental start date cannot be in the past.", "error")
        return False

    available_boats = get_available_boats(**params)
    form = BoatSelectionForm(available_boats=available_boats, formdata=request.form)
    if not form.validate_on_submit():
        flash("That boat is not available for those dates. Please search again.", "error")
        return False

    boat_id = form.boat_id.data

    if rental_conflicts(boat_id, params["start_date"], params["end_date"]):
        flash(f"Boat {boat_id} was just booked by someone else.", "error")
        return False

    try:
        db.session.add(
            Rental(
                ClientID=session["client"]["ClientID"],
                BoatID=boat_id,
                RentalDate=params["start_date"],
                RentalEndDate=params["end_date"],
                PaymentStatus="UNPAID",
            )
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("You have already booked this boat for that start date.", "error")
        return False
    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to store rental for boat %s", boat_id)
        flash("Could not complete the booking. Please try again.", "error")
        return False

    flash(f"Boat {boat_id} successfully booked!", "success")
    return True


def parse_date_arg(name, fallback):
    """Read a YYYY-MM-DD query-string argument, falling back on bad input."""
    raw = request.args.get(name)
    if not raw:
        return fallback
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        flash(f"Ignoring invalid {name.replace('_', ' ')}: {raw!r}.", "warning")
        return fallback


def parse_search_params(source, start_key="start_date", end_key="end_date"):
    """Extract city/start/end from a form or query-string mapping.

    Returns {} and flashes on anything malformed, so callers never have to
    handle a ValueError from strptime.
    """
    city = (source.get("city") or "").strip()
    try:
        start_date = datetime.strptime(source.get(start_key, ""), "%Y-%m-%d").date()
        end_date = datetime.strptime(source.get(end_key, ""), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        flash("Invalid search parameters.", "error")
        return {}

    if not city or end_date <= start_date:
        flash("Invalid search parameters.", "error")
        return {}

    return {"city": city, "start_date": start_date, "end_date": end_date}


def build_booking_form(search_params, available_boats):
    """Booking form pre-filled with the searched dates, or None if nothing is free."""
    if not available_boats:
        return None

    form = BoatSelectionForm(available_boats=available_boats, formdata=None)
    form.city.data = search_params["city"]
    form.rental_date.data = search_params["start_date"].strftime("%Y-%m-%d")
    form.rental_end_date.data = search_params["end_date"].strftime("%Y-%m-%d")
    return form


def rental_overlap_filter(start_date, end_date):
    """Rentals overlapping the half-open interval [start_date, end_date).

    A rental whose RentalEndDate is NULL is open-ended and blocks the boat from
    its start date onwards.
    """
    return and_(
        Rental.RentalDate < end_date,
        or_(Rental.RentalEndDate.is_(None), Rental.RentalEndDate > start_date),
    )


def rental_conflicts(boat_id, start_date, end_date):
    return db.session.query(
        db.session.query(Rental)
        .filter(Rental.BoatID == boat_id)
        .filter(rental_overlap_filter(start_date, end_date))
        .exists()
    ).scalar()


def get_available_boats(city, start_date, end_date):
    conflicting_rentals = select(Rental.BoatID).filter(
        rental_overlap_filter(start_date, end_date)
    )

    return (
        db.session.query(Boat, Office)
        .select_from(Boat)
        .join(Office, Boat.OfficeID == Office.OfficeID)
        .filter(Office.City == city)
        .filter(Boat.AvailabilityStatus == AVAILABILITY_AVAILABLE)
        .filter(~Boat.BoatID.in_(conflicting_rentals))
        .order_by(Boat.Manufacturer, Boat.BoatID)
        .all()
    )


@app.route("/manager/login", methods=["GET", "POST"])
def manager_login():
    managers = db.session.query(Manager, Employee).join(Employee, Manager.ManagerID == Employee.EmployeeID).order_by(Employee.LastName).all()
    form = ManagerLoginForm()
    form.manager_id.choices = [(m.ManagerID, f"{e.FirstName} {e.LastName} ({e.EmployeeID})") for m, e in managers]

    if form.validate_on_submit():
        selected = next(((m, e) for m, e in managers if m.ManagerID == form.manager_id.data), None)
        if selected:
            m, e = selected
            sign_in('manager',
                    {
                        'ManagerID':  m.ManagerID,
                        'EmployeeID': e.EmployeeID,
                        'FirstName':  e.FirstName,
                        'LastName':   e.LastName,
                        'FullName':   f"{e.FirstName} {e.LastName}"
                    }
            )
            flash(f"Logged in as manager {e.FirstName} {e.LastName}.", "success")
            return redirect(url_for("list_employees"))
        flash("Invalid manager selected.", "error")
    return render_template("manager_login.html", form=form)

@app.route("/manager/logout")
def manager_logout():
    session.pop('manager', None)
    flash("Logged out as manager.", "success")
    return redirect(url_for("manager_login"))

@app.route("/manager/employees")
@manager_required
def list_employees():
    employees = db.session.query(Employee).order_by(Employee.LastName, Employee.FirstName).all()
    staff_ids = {s.StaffID for s in Staff.query.all()}
    manager_ids = {m.ManagerID for m in Manager.query.all()}
    roles = {e.EmployeeID: ("Manager" if e.EmployeeID in manager_ids else "Staff" if e.EmployeeID in staff_ids else "-")
             for e in employees}
    return render_template("employees_list.html", employees=employees, roles=roles, delete_form=ConfirmDeleteForm())

@app.route("/manager/employees/new", methods=["GET", "POST"])
@manager_required
def hire_employee():
    form = EmployeeHireForm()
    form.office_id.choices = [(o.OfficeID, f"{o.City} ({o.OfficeID})") for o in Office.query.order_by(Office.City).all()]
    mgrs = db.session.query(Manager, Employee).join(Employee, Manager.ManagerID == Employee.EmployeeID).order_by(Employee.LastName).all()
    form.supervisor_id.choices = [("", "— None —")] + [(m.ManagerID, f"{e.FirstName} {e.LastName}") for m, e in mgrs]

    if form.validate_on_submit():
        emp_id = f"E{uuid4().hex[:8]}"
        try:
            employee = Employee(
                EmployeeID=emp_id,
                OfficeID=form.office_id.data,
                FirstName=form.first_name.data,
                LastName=form.last_name.data,
                Street=form.street.data or None,
                ZIP=form.zip.data or None,
                Country=form.country.data or None,
                City=form.city.data or None,
                Birthdate=form.birthdate.data,
                Email=form.email.data,
                MobileNumber=form.mobile.data or None,
                SelfInsuranceNr=form.self_insurance_nr.data,
                Salary=form.salary.data
            )
            db.session.add(employee)
            db.session.flush()

            if form.role.data == "staff":
                db.session.add(Staff(StaffID=emp_id, WorkShift=form.work_shift.data or "Day", IsOnDuty=bool(form.is_on_duty.data)))
            else:
                db.session.add(Manager(ManagerID=emp_id, Department=form.department.data or None, ManagementLevel=form.management_level.data or None, SupervisorID=form.supervisor_id.data or None))

            db.session.commit()
            flash(f"Employee {employee.FirstName} {employee.LastName} hired.", "success")
            return redirect(url_for("list_employees"))
        except IntegrityError:
            db.session.rollback()
            flash("Unique constraint failed (Self insurance number must be unique).", "error")
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "error")
    return render_template("employee_new.html", form=form)

@app.route("/manager/employees/<emp_id>/edit", methods=["GET", "POST"])
@manager_required
def edit_employee(emp_id):
    employee = Employee.query.get_or_404(emp_id)
    is_staff = Staff.query.get(emp_id) is not None
    is_manager = Manager.query.get(emp_id) is not None

    # obj= is deliberately not passed: the model attributes are FirstName /
    # LastName while the form fields are first_name / last_name, so it matched
    # nothing. The GET block below populates the form explicitly.
    form = EmployeeEditForm()
    form.office_id.choices = [(o.OfficeID, f"{o.City} ({o.OfficeID})") for o in Office.query.order_by(Office.City).all()]
    mgrs = db.session.query(Manager, Employee).join(Employee, Manager.ManagerID == Employee.EmployeeID).filter(Manager.ManagerID != emp_id).order_by(Employee.LastName).all()
    form.supervisor_id.choices = [("", "— None —")] + [(m.ManagerID, f"{e.FirstName} {e.LastName}") for m, e in mgrs]

    if request.method == "GET":
        # base employee fields
        form.office_id.data = employee.OfficeID
        form.first_name.data = employee.FirstName
        form.last_name.data = employee.LastName
        form.street.data = employee.Street or ""
        form.zip.data = employee.ZIP or ""
        form.country.data = employee.Country or ""
        form.city.data = employee.City or ""
        form.birthdate.data = employee.Birthdate
        form.email.data = employee.Email
        form.mobile.data = employee.MobileNumber or ""
        form.self_insurance_nr.data = employee.SelfInsuranceNr
        form.salary.data = employee.Salary

        # role-specific fields
        form.role.data = "manager" if is_manager else "staff" if is_staff else ""
        if is_staff:
            s = Staff.query.get(emp_id)
            form.work_shift.data = s.WorkShift
            form.is_on_duty.data = s.IsOnDuty
        if is_manager:
            m = Manager.query.get(emp_id)
            form.department.data = m.Department or ""
            form.management_level.data = m.ManagementLevel or ""
            form.supervisor_id.data = m.SupervisorID or ""

    if form.validate_on_submit():
        if (
            is_manager
            and form.role.data == "staff"
            and emp_id == session.get("manager", {}).get("EmployeeID")
        ):
            flash("You cannot demote the manager you are signed in as.", "error")
            return render_template("employee_edit.html", form=form, employee=employee)

        try:
            employee.OfficeID = form.office_id.data
            employee.FirstName = form.first_name.data
            employee.LastName = form.last_name.data
            employee.Street = form.street.data or None
            employee.ZIP = form.zip.data or None
            employee.Country = form.country.data or None
            employee.City = form.city.data or None
            employee.Birthdate = form.birthdate.data
            employee.Email = form.email.data
            employee.MobileNumber = form.mobile.data or None
            employee.SelfInsuranceNr = form.self_insurance_nr.data
            employee.Salary = form.salary.data

            if form.role.data == "staff":
                if is_manager:
                    detach_manager_links(emp_id)
                    Manager.query.filter_by(ManagerID=emp_id).delete()
                if is_staff:
                    s = Staff.query.get(emp_id)
                    s.WorkShift = form.work_shift.data or "Day"
                    s.IsOnDuty = bool(form.is_on_duty.data)
                else:
                    db.session.add(Staff(StaffID=emp_id, WorkShift=form.work_shift.data or "Day", IsOnDuty=bool(form.is_on_duty.data)))
            else:
                if is_staff:
                    detach_staff_links(emp_id)
                    Staff.query.filter_by(StaffID=emp_id).delete()
                if is_manager:
                    m = Manager.query.get(emp_id)
                    m.Department = form.department.data or None
                    m.ManagementLevel = form.management_level.data or None
                    m.SupervisorID = form.supervisor_id.data or None
                else:
                    db.session.add(Manager(ManagerID=emp_id, Department=form.department.data or None, ManagementLevel=form.management_level.data or None, SupervisorID=form.supervisor_id.data or None))

            db.session.commit()
            flash("Employee updated.", "success")
            return redirect(url_for("list_employees"))
        except IntegrityError:
            db.session.rollback()
            flash("Unique constraint failed (Self insurance number must be unique).", "error")
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "error")

    return render_template("employee_edit.html", form=form, employee=employee)

@app.route("/manager/employees/<emp_id>/delete", methods=["POST"])
@manager_required
def delete_employee(emp_id):
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        flash("Invalid delete request.", "error")
        return redirect(url_for("list_employees"))

    if emp_id == session.get("manager", {}).get("EmployeeID"):
        flash("You cannot delete the employee you are signed in as.", "error")
        return redirect(url_for("list_employees"))

    employee = Employee.query.get_or_404(emp_id)

    try:
        detach_staff_links(emp_id)
        detach_manager_links(emp_id)
        Staff.query.filter_by(StaffID=emp_id).delete()
        Manager.query.filter_by(ManagerID=emp_id).delete()
        db.session.delete(employee)
        db.session.commit()
        flash("Employee deleted.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Cannot delete this employee — other records still reference them.", "error")
    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to delete employee %s", emp_id)
        flash("Delete failed.", "error")

    return redirect(url_for("list_employees"))


def detach_manager_links(emp_id):
    """Clear the references that block removing a Manager row.

    Supervises and Maintains have no SQLAlchemy models, so they are reached
    with raw SQL — same approach as generator.generate_data().
    """
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
