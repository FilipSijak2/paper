# Koristi službeni ROS 2 Humble image kao osnovu
FROM ros:humble

# Instaliraj potrebne pakete za rosbridge i CycloneDDS
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
