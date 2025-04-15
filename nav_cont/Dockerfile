FROM ros:humble-ros-base:latest
# Instalirajte potrebne alate i Python ovisnosti
RUN apt-get update && apt-get install -y \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Kopirajte projekt u Docker container
WORKDIR /app
COPY . /app

# Instalirajte Python ovisnosti
RUN pip3 install --no-cache-dir -r requirements.txt

# Postavite ulaznu točku za pokretanje ROS 2 čvorova
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && python3 move.py & python3 path_planner.py"]