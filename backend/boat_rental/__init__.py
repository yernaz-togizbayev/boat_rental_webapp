from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf

import os

# Load the repo-root .env so running python outside Docker sees the same
# settings Compose injects. Existing env vars win, so the container -- where
# there is no .env -- is unaffected. Guarded because the app must still start
# if the image predates python-dotenv landing in requirements.txt.
try:
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv())
except ImportError:  # pragma: no cover - only before the next image rebuild
    pass


app = Flask(__name__, template_folder="../templates", static_folder="../static")
csrf = CSRFProtect(app)

app.secret_key = os.getenv("SECRET_KEY", "dev")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL") or (
    f"mysql+pymysql://{os.getenv('DB_USER', 'user')}:"
    f"{os.getenv('DB_PASSWORD', 'pass')}@"
    f"{os.getenv('DB_HOST', 'db')}:"
    f"{os.getenv('DB_PORT', '3306')}/"
    f"{os.getenv('DB_NAME', 'boatdb')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 280,
}
db = SQLAlchemy(app)

@app.context_processor
def inject_csrf():
    return dict(csrf_token=generate_csrf)


@app.context_processor
def inject_unsplash():
    """The attribution link the footer needs, so every page carries it.

    Imported inside the function rather than at the top: images.py is a
    sibling of this module, and importing it up there closes the same
    circular loop that keeps `routes` at the bottom of the file.
    """
    from boat_rental.images import UNSPLASH_HOME
    return dict(unsplash_home=UNSPLASH_HOME)


@app.template_filter("money")
def format_money(amount):
    """Euro with thousands separators, or an em dash when there is no price.

    A filter rather than repeated formatting in five templates -- a boat with
    no DailyRate is a real state (the column is nullable and a manager can
    leave it blank), and every one of those templates has to render it the
    same way.
    """
    if amount is None:
        return "—"
    return f"€{amount:,.2f}"

from boat_rental import routes  # noqa: E402, F401
