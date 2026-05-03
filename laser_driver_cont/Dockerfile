FROM ros:humble

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    python3-colcon-common-extensions \
    build-essential \
    ros-humble-rmw-cyclonedds-cpp \
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

RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Europe/Zagreb

# Set variables for ROS 2
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Create workspace
WORKDIR /ros2_ws
RUN mkdir src \
    && git clone -b ros2 https://github.com/Slamtec/rplidar_ros.git src/rplidar_ros \
    && . /opt/ros/humble/setup.sh && colcon build \
    && echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "source /ros2_ws/install/setup.bash" >> /root/.bashrc && \
    printf '%s\n' "export PS1='\\[\\033[1;34m\\]driver_cont: \\[\\033[0m\\]'" >> /root/.bashrc

# Start driver; exit with non-zero on failure so Docker can restart the container
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && source /ros2_ws/install/setup.bash && ros2 launch rplidar_ros rplidar_a1_launch.py"]
