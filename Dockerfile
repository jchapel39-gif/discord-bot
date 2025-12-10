FROM python:3.12-slim

WORKDIR /app

# Copier les fichiers
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Lancer le bot
CMD ["python", "bot.py"]

