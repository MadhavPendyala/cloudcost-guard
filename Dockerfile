FROM python:3.12
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8000 DB_PATH=/data/costs.db
RUN mkdir -p /data
EXPOSE 8000
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT} app:app"]
