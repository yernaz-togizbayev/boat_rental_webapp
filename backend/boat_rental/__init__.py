from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf

import os


app = Flask(__name__, template_folder="../templates", static_folder="../static")
csrf = CSRFProtect(app)

app.secret_key = "dev"
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{os.getenv('DB_USER', 'user')}:"
    f"{os.getenv('DB_PASSWORD', 'pass')}@"
    f"{os.getenv('DB_HOST', 'db')}:"
    f"{os.getenv('DB_PORT', '3306')}/"
    f"{os.getenv('DB_NAME', 'boatdb')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

@app.context_processor
def inject_csrf():
    return dict(csrf_token=generate_csrf)

from boat_rental import routes  # noqa: E402, F401
