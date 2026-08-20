FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV FLASK_APP=app.py
ENV FLASK_RUN_PORT=5000
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_DEBUG=1

# --reload keeps the hot reload the bind-mounted source relies on.
# --no-debugger drops only Werkzeug's interactive console, which turns any
# traceback into a Python prompt running as this container's user. Compose
# already binds the port to loopback; this is the second lock, so publishing
# the port for a demo cannot quietly hand out a shell. Tracebacks still go to
# the container log, where `docker compose logs -f backend` shows them.
CMD ["sh", "-c", "flask run --host=0.0.0.0 --port=5000 --reload --no-debugger"]
