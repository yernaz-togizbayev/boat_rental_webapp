from flask import flash, redirect, request, jsonify, render_template, session, url_for
from datetime import datetime, date
from sqlalchemy import and_, select, or_
from sqlalchemy.exc import IntegrityError
from functools import wraps

from boat_rental.forms import BoatSelectionForm, BookingSearchForm, ManagerLoginForm, EmployeeHireForm, EmployeeEditForm, ConfirmDeleteForm
from boat_rental import app, db
from boat_rental.generator import generate_data
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
    session.pop("client", None)
    flash("Logged out.", "success")
    return redirect(url_for("login"))


@app.route("/select-client/<client_id>")
def select_client(client_id):
    client = Client.query.get(client_id)

    if client:
        sign_in('client',
                {
                    "ClientID": client.ClientID,
                    "FirstName": client.FirstName,
                    "LastName": client.LastName,
                    "FullName": client.full_name,
                    "Email": client.Email,
                }
            )
    return redirect(url_for("home"))


@app.route("/home")
def home():
    if "client" not in session and "manager" not in session:
        return redirect(url_for("login"))

    client = session.get("client")
    return render_template("home.html", client=client)


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
        print("DEBUG: Booking form submitted")
        book_rental()
        return redirect(url_for("report"))
    elif search_form.validate_on_submit():
        booking_form, search_params, available_boats = handle_search_form_submission(
            search_form
        )
    elif request.method == "GET" and request.form.get("city"):
        booking_form, search_params, available_boats = handle_get_search(search_form)

    if (
        search_params
        and search_params.get("start_date")
        and search_params.get("end_date")
    ):
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

    filtered_city = request.args.get("city", "Dubrovnik")
    start_date_str = request.args.get("start_date", "2025-07-01")
    end_date_str = request.args.get("end_date", "2025-07-05")
    offices = Office.query.all()

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

    available_boats = (
        db.session.query(Boat, Office)
        .select_from(Boat)
        .join(Office, Boat.OfficeID == Office.OfficeID)
        .filter(Office.City == filtered_city)
        .filter(Boat.AvailabilityStatus == "Available")
        .outerjoin(
            Rental,
            db.and_(
                Rental.BoatID == Boat.BoatID,
                Rental.RentalDate < end_date,
                Rental.RentalEndDate > start_date,
            ),
        )
        .filter(Rental.BoatID.is_(None))
        .all()
    )

    total_boats = Boat.query.count()
    available_count = Boat.query.filter_by(AvailabilityStatus="Available").count()
    rentals_in_period = (
        db.session.query(Rental)
        .filter(
            or_(
                and_(Rental.RentalDate >= start_date, Rental.RentalDate < end_date),
                and_(
                    Rental.RentalEndDate > start_date, Rental.RentalEndDate <= end_date
                ),
                and_(Rental.RentalDate <= start_date, Rental.RentalEndDate >= end_date),
            )
        )
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
    generate_data()
    return redirect(url_for("login"))


def book_rental():
    print("DEBUG: book_rental called")
    print(f"DEBUG: Form data: {dict(request.form)}")

    boat_id = request.form.get("boat_id")
    rental_date = request.form.get("rental_date")
    rental_end_date = request.form.get("rental_end_date")

    print(
        f"DEBUG: boat_id={boat_id}, rental_date={rental_date}, rental_end_date={rental_end_date}"
    )

    if not boat_id or not rental_date or not rental_end_date:
        flash("Missing booking information", "error")
        return

    try:
        rental = Rental(
            ClientID=session.get("client").get("ClientID"),
            BoatID=boat_id,
            RentalDate=datetime.strptime(rental_date, "%Y-%m-%d").date(),
            RentalEndDate=datetime.strptime(rental_end_date, "%Y-%m-%d").date(),
            PaymentStatus="UNPAID",
        )
        db.session.add(rental)
        db.session.commit()
        print(f"DEBUG: Rental saved successfully")
        flash(f"Boat {boat_id} successfully booked!", "success")
    except Exception as e:
        print(f"DEBUG: Error saving rental: {e}")
        db.session.rollback()
        flash(f"Error booking boat: {str(e)}", "error")


def get_available_boats(city, start_date, end_date):
    conflicting_rentals = select(Rental.BoatID).filter(
        or_(
            and_(Rental.RentalDate >= start_date, Rental.RentalDate < end_date),
            and_(Rental.RentalEndDate > start_date, Rental.RentalEndDate <= end_date),
            and_(Rental.RentalDate <= start_date, Rental.RentalEndDate >= end_date),
        )
    )

    available_boats = (
        db.session.query(Boat, Office)
        .select_from(Boat)
        .join(Office, Boat.OfficeID == Office.OfficeID)
        .filter(Office.City == city)
        .filter(Boat.AvailabilityStatus == "AVAILABLE")
        .filter(~Boat.BoatID.in_(conflicting_rentals))
        .order_by(Boat.Manufacturer, Boat.BoatID)
        .all()
    )

    return available_boats


def handle_search_form_submission(search_form):
    search_params = {
        "city": search_form.city.data,
        "start_date": search_form.start_date.data,
        "end_date": search_form.end_date.data,
    }
    available_boats = get_available_boats(
        search_params["city"], search_params["start_date"], search_params["end_date"]
    )

    if available_boats:
        booking_form = BoatSelectionForm(available_boats=available_boats)
        booking_form.rental_date.data = search_params["start_date"].strftime("%Y-%m-%d")
        booking_form.rental_end_date.data = search_params["end_date"].strftime(
            "%Y-%m-%d"
        )

    return booking_form, search_params, available_boats


def handle_get_search(search_form):
    try:
        booking_form = None
        search_params = {
            "city": request.args.get("city"),
            "start_date": datetime.strptime(
                request.args.get("start_date"), "%Y-%m-%d"
            ).date(),
            "end_date": datetime.strptime(
                request.args.get("end_date"), "%Y-%m-%d"
            ).date(),
        }
        search_form.city.data = search_params["city"]
        search_form.start_date.data = search_params["start_date"]
        search_form.end_date.data = search_params["end_date"]

        available_boats = get_available_boats(
            search_params["city"],
            search_params["start_date"],
            search_params["end_date"],
        )

        if available_boats:
            booking_form = BoatSelectionForm(available_boats=available_boats)
            booking_form.rental_date.data = search_params["start_date"].strftime(
                "%Y-%m-%d"
            )
            booking_form.rental_end_date.data = search_params["end_date"].strftime(
                "%Y-%m-%d"
            )

        return booking_form, search_params, available_boats
    except (ValueError, TypeError):
        flash("Invalid search parameters.", "error")
        return None, {}, []


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
                        'ManagerID': m.ManagerID,
                        'EmployeeID': e.EmployeeID,
                        'FirstName': e.FirstName,
                        'LastName': e.LastName,
                        'FullName': f"{e.FirstName} {e.LastName}"
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
        emp_id = f"E{int(datetime.utcnow().timestamp())}"
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

    form = EmployeeEditForm(obj=employee)
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
                if not is_staff:
                    if is_manager:
                        Manager.query.filter_by(ManagerID=emp_id).delete()
                    db.session.add(Staff(StaffID=emp_id, WorkShift=form.work_shift.data or "Day", IsOnDuty=bool(form.is_on_duty.data)))
                else:
                    s = Staff.query.get(emp_id)
                    s.WorkShift = form.work_shift.data or "Day"
                    s.IsOnDuty = bool(form.is_on_duty.data)
                Manager.query.filter_by(ManagerID=emp_id).delete()
            else:
                if not is_manager:
                    if is_staff:
                        Staff.query.filter_by(StaffID=emp_id).delete()
                    db.session.add(Manager(ManagerID=emp_id, Department=form.department.data or None, ManagementLevel=form.management_level.data or None, SupervisorID=form.supervisor_id.data or None))
                else:
                    m = Manager.query.get(emp_id)
                    m.Department = form.department.data or None
                    m.ManagementLevel = form.management_level.data or None
                    m.SupervisorID = form.supervisor_id.data or None
                Staff.query.filter_by(StaffID=emp_id).delete()

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
    if form.validate_on_submit():
        try:
            Staff.query.filter_by(StaffID=emp_id).delete()
            Manager.query.filter_by(ManagerID=emp_id).delete()
            emp = Employee.query.get_or_404(emp_id)
            db.session.delete(emp)
            db.session.commit()
            flash("Employee deleted.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Delete failed: {e}", "error")
    return redirect(url_for("list_employees"))
