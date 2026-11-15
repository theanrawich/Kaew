FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    KAEW_HOST=0.0.0.0 \
    KAEW_TRUST_EDGE_HTTPS=1 \
    KAEW_DB_PATH=/data/kaew.sqlite3
WORKDIR /app
RUN useradd --uid 10001 --create-home kaew && mkdir /data && chown kaew:kaew /data
COPY --chown=kaew:kaew cloud/ /app/cloud/
USER kaew
EXPOSE 8080
CMD ["python", "cloud/server.py"]
