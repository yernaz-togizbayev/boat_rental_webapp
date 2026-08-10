from flask import current_app
from flask_wtf import FlaskForm
from wtforms import SelectField, EmailField, DateField, SubmitField, StringField, HiddenField, BooleanField, IntegerField, FloatField
from wtforms.validators import DataRequired, Email, Optional, Length, NumberRange, ValidationError
from datetime import date, timedelta
from boat_rental.models import Office, AVAILABILITY_AVAILABLE, AVAILABILITY_MAINTENANCE


def validate_future_date(form, field):
    if field.data < date.today():
        raise ValidationError("Date cannot be in the past.")


def validate_end_after_start(form, field):
    if hasattr(form, "start_date") and form.start_date.data:
        if field.data <= form.start_date.data:
            raise ValidationError("End date must be after start date.")




class BookingSearchForm(FlaskForm):
    city = SelectField(
        "City",
        validators=[DataRequired()],
        choices=[],
        render_kw={"placeholder": "Select City..."},
    )
    start_date = DateField(
        "Start Date",
        validators=[DataRequired(), validate_future_date],
        default=date.today,
    )
    end_date = DateField(
        "End Date",
        validators=[DataRequired(), validate_end_after_start],
        default=lambda: date.today() + timedelta(days=1),
    )
    search = SubmitField("Search available boats")

    def __init__(self, *args, **kwargs):
        super(BookingSearchForm, self).__init__(*args, **kwargs)
        try:
            cities = Office.query.with_entities(Office.City).distinct().all()
            self.city.choices = [("", "Select City...")] + [
                (city[0], city[0]) for city in cities
            ]
        except Exception:
            # The office table may not exist yet (first boot, before the
            # init scripts have run) — fall back to an empty picker.
            current_app.logger.exception("Could not load city choices")
            self.city.choices = [("", "Select City...")]


class BoatSelectionForm(FlaskForm):
    boat_id = SelectField(
        "Select Boat",
        validators=[DataRequired()],
        choices=[],
        render_kw={"placeholder": "Choose a boat..."},
    )
    rental_date = HiddenField()
    rental_end_date = HiddenField()
    city = HiddenField()
    book = SubmitField("Book")

    def __init__(self, available_boats=None, *args, **kwargs):
        super(BoatSelectionForm, self).__init__(*args, **kwargs)
        if available_boats:
            self.boat_id.choices = [("", "Choose a boat...")] + [
                (str(boat.BoatID), _describe_boat(boat)) for boat, office in available_boats
            ]


def _describe_boat(boat):
    length = f"{boat.Length:.1f}m" if boat.Length is not None else "length n/a"
    return f"{boat.BoatID} - {boat.Manufacturer} ({boat.Seats} seats, {length}, {boat.Horsepower}HP)"



# =========================
# Manager & Employee forms
# =========================
MIN_EMPLOYEE_AGE = 18
MIN_CLIENT_AGE = 18

def min_age(years, subject):
    """Validator factory: `subject` must be at least `years` old.

    A factory rather than a plain function so clients and employees can share
    the arithmetic without the error message calling a client an "Employee".
    """
    def _validate(form, field):
        if field.data:
            today = date.today()
            age = today.year - field.data.year - ((today.month, today.day) < (field.data.month, field.data.day))
            if age < years:
                raise ValidationError(f"{subject} must be at least {years} years old.")
    return _validate

# The employee forms below refer to this name; keeping it means their
# validators lists and their error text are unchanged.
validate_min_age = min_age(MIN_EMPLOYEE_AGE, "Employee")

class ManagerLoginForm(FlaskForm):
    manager_id = SelectField("Select manager", validators=[DataRequired()])
    submit = SubmitField("Login as manager")

class EmployeeHireForm(FlaskForm):
    office_id = SelectField("Office", validators=[DataRequired()], coerce=str)
    first_name = StringField("First name", validators=[DataRequired(), Length(max=50)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=50)])
    street = StringField("Street", validators=[Optional(), Length(max=100)])
    zip = StringField("ZIP", validators=[Optional(), Length(max=10)])
    country = StringField("Country", validators=[Optional(), Length(max=50)])
    city = StringField("City", validators=[Optional(), Length(max=50)])
    birthdate = DateField("Birthdate", format="%Y-%m-%d",validators=[DataRequired(), validate_min_age], render_kw={"type": "date"})
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=100)])
    mobile = StringField("Mobile number", validators=[Optional(), Length(max=20)])
    self_insurance_nr = StringField("Self insurance number", validators=[DataRequired(), Length(max=20)])
    salary = IntegerField("Salary", validators=[DataRequired(), NumberRange(min=0, max=10_000_000)])

    # Role-specific
    role = SelectField("Role", choices=[("staff", "Staff"), ("manager", "Manager")], validators=[DataRequired()], coerce=str)
    # Staff extras
    work_shift = SelectField("Work shift", choices=[("Day", "Day"), ("Night", "Night")], validators=[Optional()], coerce=str)
    is_on_duty = BooleanField("Is on duty?")
    # Manager extras
    department = StringField("Department", validators=[Optional(), Length(max=50)])
    management_level = StringField("Management level", validators=[Optional(), Length(max=50)])
    supervisor_id = SelectField("Supervisor (optional)", validators=[Optional()], coerce=str)

    submit = SubmitField("Hire")

class EmployeeEditForm(FlaskForm):
    office_id = SelectField("Office", validators=[DataRequired()], coerce=str)
    first_name = StringField("First name", validators=[DataRequired(), Length(max=50)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=50)])
    street = StringField("Street", validators=[Optional(), Length(max=100)])
    zip = StringField("ZIP", validators=[Optional(), Length(max=10)])
    country = StringField("Country", validators=[Optional(), Length(max=50)])
    city = StringField("City", validators=[Optional(), Length(max=50)])
    birthdate = DateField("Birthdate", format="%Y-%m-%d", validators=[DataRequired(), validate_min_age])
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=100)])
    mobile = StringField("Mobile number", validators=[Optional(), Length(max=20)])
    self_insurance_nr = StringField("Self insurance number", validators=[DataRequired(), Length(max=20)])
    salary = IntegerField("Salary", validators=[DataRequired(), NumberRange(min=0, max=10_000_000)])

    role = SelectField("Role", choices=[("staff", "Staff"), ("manager", "Manager")], validators=[DataRequired()], coerce=str)
    # Staff extras
    work_shift = SelectField("Work shift", choices=[("Day", "Day"), ("Night", "Night")], validators=[Optional()], coerce=str)
    is_on_duty = BooleanField("Is on duty?")
    # Manager extras
    department = StringField("Department", validators=[Optional(), Length(max=50)])
    management_level = StringField("Management level", validators=[Optional(), Length(max=50)])
    supervisor_id = SelectField("Supervisor (optional)", validators=[Optional()], coerce=str)

    submit = SubmitField("Save changes")

class ConfirmDeleteForm(FlaskForm):
    submit = SubmitField("Delete")

class ClientRegistrationForm(FlaskForm):
    # Required fields mirror the NOT NULL columns on Client; everything else
    # is Optional() and written as NULL when blank.
    first_name = StringField("First name", validators=[DataRequired(), Length(max=50)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=50)])
    street = StringField("Street", validators=[Optional(), Length(max=100)])
    zip = StringField("ZIP", validators=[Optional(), Length(max=10)])
    country = StringField("Country", validators=[Optional(), Length(max=50)])
    city = StringField("City", validators=[Optional(), Length(max=50)])
    birthdate = DateField(
        "Birthdate",
        format="%Y-%m-%d",
        validators=[DataRequired(), min_age(MIN_CLIENT_AGE, "Client")],
        render_kw={"type": "date"},
    )
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=100)])
    mobile = StringField("Mobile number", validators=[Optional(), Length(max=20)])
    captain_license = StringField(
        "Captain licence number (optional)", validators=[Optional(), Length(max=50)]
    )
    submit = SubmitField("Create account")


class OfficeForm(FlaskForm):
    city = StringField("City", validators=[DataRequired(), Length(max=50)])
    country = StringField("Country", validators=[DataRequired(), Length(max=50)])
    street = StringField("Street", validators=[DataRequired(), Length(max=100)])
    zip = StringField("ZIP", validators=[DataRequired(), Length(max=10)])
    submit = SubmitField("Save office")


# The m:n relations from the ER model. Choices are filled in by the route, so
# SelectField.pre_validate is what rejects a POST naming, say, a manager in the
# staff slot -- the check happens before anything reaches SQL.
class SupervisesForm(FlaskForm):
    manager_id = SelectField("Manager", validators=[DataRequired()], coerce=str)
    staff_id = SelectField("Staff member", validators=[DataRequired()], coerce=str)
    submit = SubmitField("Assign supervision")


class MaintainsForm(FlaskForm):
    staff_id = SelectField("Staff member", validators=[DataRequired()], coerce=str)
    boat_id = SelectField("Boat", validators=[DataRequired()], coerce=str)
    submit = SubmitField("Assign boat")


BOAT_TYPES = [("yacht", "Yacht"), ("motorboat", "Motorboat"), ("catamaran", "Catamaran")]


class BoatForm(FlaskForm):
    office_id = SelectField("City / office", validators=[DataRequired()], coerce=str)
    manufacturer = StringField("Manufacturer", validators=[DataRequired(), Length(max=50)])
    seats = IntegerField("Seats", validators=[DataRequired(), NumberRange(min=1, max=1000)])
    length = FloatField("Length (m)", validators=[Optional(), NumberRange(min=0, max=1000)])
    weight = FloatField("Weight (t)", validators=[Optional(), NumberRange(min=0, max=100_000)])
    horsepower = IntegerField("Horsepower", validators=[Optional(), NumberRange(min=0, max=100_000)])
    availability_status = SelectField(
        "Availability",
        choices=[(AVAILABILITY_AVAILABLE, "Available"), (AVAILABILITY_MAINTENANCE, "Maintenance")],
        validators=[DataRequired()],
        coerce=str,
    )

    boat_type = SelectField("Type", choices=BOAT_TYPES, validators=[DataRequired()], coerce=str)
    
    # Yacht extras
    yacht_name = StringField("Yacht name", validators=[Optional(), Length(max=50)])
    has_jacuzzi = BooleanField("Has jacuzzi?")
    
    # Motorboat extras
    engine_type = StringField("Engine type", validators=[Optional(), Length(max=50)])
    fuel_type = StringField("Fuel type", validators=[Optional(), Length(max=50)])
    
    # Catamaran extras
    nr_of_cabins = IntegerField("Number of cabins", validators=[Optional(), NumberRange(min=0, max=500)])
    max_capacity = IntegerField("Max capacity", validators=[Optional(), NumberRange(min=0, max=5000)])

    submit = SubmitField("Save boat")