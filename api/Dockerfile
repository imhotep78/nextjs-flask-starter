FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ .

EXPOSE 5328

CMD ["python", "-m", "flask", "--app", "index", "run", "--host", "0.0.0.0", "-p", "5328"]
