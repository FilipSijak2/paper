FROM postgres:15

# Install PostGIS for spatial data support
RUN apt-get update && apt-get install -y \
    postgresql-15-postgis-3 \
    postgresql-15-postgis-3-scripts \
    && rm -rf /var/lib/apt/lists/*

# Optional: install editors (nano) only when explicitly requested.
# Use at build time: docker build --build-arg INSTALL_EDITORS=true -t your_tag .
ARG INSTALL_EDITORS=true
RUN if [ "$INSTALL_EDITORS" = "true" ]; then \
            echo "Installing editors (nano) for debugging..." && \
            apt-get update && apt-get install -y --no-install-recommends nano && \
            rm -rf /var/lib/apt/lists/*; \
        else \
            echo "Skipping editor installation (set INSTALL_EDITORS=true to enable)."; \
        fi

# Settings for the database
ENV POSTGRES_DB=robot_data
ENV POSTGRES_USER=robot_user
ENV POSTGRES_PASSWORD=robot_pass

RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Europe/Zagreb

# Copy initialization scripts
COPY init-db.sql /docker-entrypoint-initdb.d/

# PostGIS is enabled as an extension via init-db.sql (CREATE EXTENSION postgis)
# No shared_preload_libraries entry is needed for PostGIS

# Expose port
EXPOSE 5432

# Set custom prompt (just 'db_cont:' in blue)
RUN printf '%s\n' "export PS1='\\[\\033[1;34m\\]db_cont: \\[\\033[0m\\]'" >> /root/.bashrc

# Use default PostgreSQL entrypoint
CMD ["postgres"]
