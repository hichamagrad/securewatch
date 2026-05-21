FROM python:3.11-slim

WORKDIR /app

# Installation des dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY app.py .

# Création du dossier de logs
RUN mkdir -p /app/logs

EXPOSE 5001

CMD ["python", "app.py"]
