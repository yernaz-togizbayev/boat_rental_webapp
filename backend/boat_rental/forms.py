from flask_wtf import FlaskForm
from wtforms import SelectField, EmailField, DateField, SubmitField, StringField, HiddenField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Email, Optional, Length, NumberRange, ValidationError
from datetime import date, timedelta
from boat_rental.models import Office


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
        default=date.today(),
    )
    end_date = DateField(
        "End Date",
        validators=[DataRequired(), validate_end_after_start],
        default=date.today() + timedelta(days=1),
    )
    search = SubmitField("Search available boats")

    def __init__(self, *args, **kwargs):
        super(BookingSearchForm, self).__init__(*args, **kwargs)
        try:
            cities = Office.query.with_entities(Office.City).distinct().all()
            self.city.choices = [("", "Select City...")] + [
                (city[0], city[0]) for city in cities
            ]
        except:
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
    book = SubmitField("Book")

    def __init__(self, available_boats=None, *args, **kwargs):
        super(BoatSelectionForm, self).__init__(*args, **kwargs)
        if available_boats:
            self.boat_id.choices = [("", "Choose a boat...")] + [
                (
                    str(boat.BoatID),
                    f"{boat.BoatID} - {boat.Manufacturer} ({boat.Seats} seats, {boat.Length:.1f}m, {boat.Horsepower}HP)",
                )
                for boat, office in available_boats
            ]



# =========================
# Manager & Employee forms
# =========================
MIN_EMPLOYEE_AGE = 18

def validate_min_age(form, field):
    if field.data:
        age = date.today().year - field.data.year - ((date.today().month, date.today().day) < (field.data.month, field.data.day))
        if age < MIN_EMPLOYEE_AGE:
            raise ValidationError(f"Employee must be at least {MIN_EMPLOYEE_AGE} years old.")

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