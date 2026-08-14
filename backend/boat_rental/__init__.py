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

from boat_rental import routes  # noqa: E402, F401
