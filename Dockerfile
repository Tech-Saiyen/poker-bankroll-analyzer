FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5001

CMD ["sh", "-c", "flask db upgrade && flask seed-dfw && gunicorn --bind 0.0.0.0:${PORT:-5001} app:app"]
