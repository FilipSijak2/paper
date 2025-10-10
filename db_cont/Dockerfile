FROM postgres:15

# Install PostGIS for spatial data support
RUN apt-get update && apt-get install -y \
    postgresql-15-postgis-3 \
    postgresql-15-postgis-3-scripts \
    && rm -rf /var/lib/apt/lists/*

# Settings for the database
ENV POSTGRES_DB=robot_data
ENV POSTGRES_USER=robot_user
ENV POSTGRES_PASSWORD=robot_pass

# Copy initialization scripts
COPY init-db.sql /docker-entrypoint-initdb.d/

# Performance settings
ENV POSTGRES_SHARED_PRELOAD_LIBRARIES=postgis

# Expose port
EXPOSE 5432

# Set custom prompt (just 'db_cont:' in blue)
RUN echo "export PS1='\[\033[1;34m\]db_cont: \[\033[0m\]'" >> /root/.bashrc

# Use default PostgreSQL entrypoint
CMD ["postgres"]