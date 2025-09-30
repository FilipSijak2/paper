FROM postgres:15

# Instaliraj PostGIS ekstenziju za prostorne podatke
RUN apt-get update && apt-get install -y \
    postgresql-15-postgis-3 \
    postgresql-15-postgis-3-scripts \
    && rm -rf /var/lib/apt/lists/*

# Postavke za bazu podataka
ENV POSTGRES_DB=robot_data
ENV POSTGRES_USER=robot_user
ENV POSTGRES_PASSWORD=robot_pass

# Kopiraj initialization skripte
COPY init-db.sql /docker-entrypoint-initdb.d/

# Postavke za performance
ENV POSTGRES_SHARED_PRELOAD_LIBRARIES=postgis

# Izloži port
EXPOSE 5432

# Postavi custom prompt (samo 'db_cont:' u plavoj boji)
RUN echo "export PS1='\[\033[1;34m\]db_cont: \[\033[0m\]'" >> /root/.bashrc

# Koristi zadani PostgreSQL entrypoint
CMD ["postgres"]

#test