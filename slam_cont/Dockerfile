FROM ros:humble

# Instalirajte potrebne alate
RUN apt-get update && apt-get install -y \
    python3-pip \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalirajte potrebne Python ovisnosti
RUN pip3 install psycopg2 pyyaml

# Kopirajte Python skriptu u container
WORKDIR /app
COPY slam_manager.py /app/slam_manager.py

# Postavite ulaznu točku za pokretanje mapiranja
CMD ["python3", "/app/slam_manager.py"]