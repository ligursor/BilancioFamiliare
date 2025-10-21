FROM python:3.11-slim

WORKDIR /app

# Copia i file requirements e installa le dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice dell'applicazione
COPY . .

# Espone la porta 5001
EXPOSE 5001

# Comando per avviare l'applicazione
# Usa run.py che inizializza il DB e avvia l'app
CMD ["python", "run.py"]
