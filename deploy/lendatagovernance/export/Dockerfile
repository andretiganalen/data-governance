FROM python:3.12-slim
RUN pip install --no-cache-dir trino==0.340.0 openpyxl==3.1.5
WORKDIR /app
CMD ["python", "-u", "/app/export_server.py"]
