FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install flask flask_sqlalchemy email-validator pymysql wtforms flask-wtf

ENV FLASK_APP=app.py
ENV FLASK_RUN_PORT=5000
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=development
ENV FLASK_DEBUG=1

CMD ["flask", "run", "--host=0.0.0.0", "--port=5000", "--debug"]
