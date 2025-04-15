FROM --platform=linux/arm64 ros:humble

# Instalirajte potrebne alate i ROS 2 pakete
RUN apt-get update && apt-get install -y \
    apt-utils \
    python3-pip \
    libpq-dev \
    ros-humble-nav2-msgs \  # Dodano: Instalacija nav2_msgs
    && dpkg --configure -a || true \
    && rm -rf /var/lib/apt/lists/*

# Instalirajte potrebne Python ovisnosti
RUN pip3 install psycopg2 pyyaml

# Kopirajte Python skriptu u container
WORKDIR /app
COPY slam_manager.py /app/slam_manager.py

# Postavite ulaznu točku za pokretanje mapiranja
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && python3 /app/slam_manager.py"]