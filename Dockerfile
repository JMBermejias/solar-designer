FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SOLAR_DATA_DIR=/data \
    SOLAR_APP_DIR=/app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py database.py solar_cli.py ./
COPY solar/ solar/
COPY templates/ templates/
COPY static/ static/

RUN python -c "import solar_cli; solar_cli.init_db()"

EXPOSE 5000
VOLUME ["/data"]

CMD ["python", "solar_cli.py", "--web", "--host", "0.0.0.0", "--port", "5000"]
