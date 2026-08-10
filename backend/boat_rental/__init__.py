from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf

import os


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
