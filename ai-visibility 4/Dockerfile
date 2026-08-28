FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY alembic.ini .
COPY migrations/ ./migrations/

# Actual process command is set per-service in docker-compose.yml / your
# host's service config — this default just makes `docker run` on its own
# do something sane (start the web server).
CMD ["uvicorn", "src.web:app", "--host", "0.0.0.0", "--port", "8000"]
