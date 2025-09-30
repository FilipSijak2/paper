FROM ros:humble

# Instalirajte potrebne alate i ROS 2 pakete
RUN apt-get update && apt-get install -y \
    apt-utils \
    python3-pip \
    libpq-dev \
    ros-humble-nav2-msgs \
    ros-humble-slam-toolbox \
    && rm -rf /var/lib/apt/lists/*

# Postavite ROS 2 okruženje u bashrc
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

# Postavite prilagođeni prompt (samo 'slam_cont:' u plavoj boji)
RUN echo "export PS1='\[\033[1;34m\]slam_cont: \[\033[0m\]'" >> /root/.bashrc

# Instalirajte potrebne Python ovisnosti
RUN pip3 install psycopg2 pyyaml

# Kopirajte Python skriptu u container
WORKDIR /app
COPY slam_manager.py /app/slam_manager.py

# Postavite ulaznu točku za pokretanje mapiranja
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && python3 /app/slam_manager.py"]