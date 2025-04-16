FROM ros:humble

# Instalirajte potrebne alate i ROS 2 RMW implementaciju
RUN apt-get update && apt-get install -y \
    python3-pip \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Kopirajte projekt u Docker container
WORKDIR /app
COPY . /app

# Instalirajte Python ovisnosti
RUN pip3 install --no-cache-dir -r requirements.txt

# Postavite prilagođeni prompt (samo 'nav_cont:' u plavoj boji)
RUN echo "export PS1='\[\033[1;34m\]nav_cont: \[\033[0m\]'" >> /root/.bashrc

# Postavite ulaznu točku za pokretanje ROS 2 čvorova
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && python3 move.py & python3 path_planner.py"]