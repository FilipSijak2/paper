# Koristi službeni ROS 2 Humble image kao osnovu
FROM ros:humble

# 1. Ukloni stare ros2 repozitorije privremeno
RUN sed -i '/ros2/d' /etc/apt/sources.list.d/*.list || true && \
    apt-get update && \
    apt-get install -y --no-install-recommends curl gnupg2 lsb-release

# comment
# 2. Dodaj novi ključ i repozitorij
RUN rm -f /etc/apt/sources.list.d/ros2.list && \
    rm -f /usr/share/keyrings/ros-archive-keyring.gpg && \
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" > /etc/apt/sources.list.d/ros2.list

# 3. Sada je sigurno pokrenuti apt-get update i instalirati ROS pakete
RUN apt-get update && apt-get install -y \
    ros-humble-rosbridge-server \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Postavi radni direktorij na /ros_ws
WORKDIR /ros_ws

# Kopiraj sve iz trenutnog direktorija u /ros_ws
COPY ./src /ros_ws/src

# Instaliraj zavisnosti za ROS 2 workspace
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && colcon build"

# Pokreni rosbridge automatski koristeći XML launch datoteku
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && ros2 launch rosbridge_server rosbridge_websocket_launch.xml"]
