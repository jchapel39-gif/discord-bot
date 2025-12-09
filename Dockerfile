FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie explicite du bot.py
COPY bot.py .

# Debug : liste les fichiers présents dans /app (apparaîtra dans les logs du BUILD)
RUN ls -la /app

# Commande de démarrage
CMD ["python", "bot.py"]
