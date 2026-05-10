FROM ros:humble

# Install necessary tools and ROS 2 packages
RUN apt-get update && apt-get install -y \
    apt-utils \
    python3-pip \
    python3-psycopg2 \
    python3-yaml \
    python3-pil \
    libpq-dev \
    ros-humble-nav2-msgs \
    ros-humble-nav2-map-server \
    ros-humble-slam-toolbox \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-rosbag2-storage-mcap \
    imagemagick \
    git \
    && rm -rf /var/lib/apt/lists/*

# Build rf2o_laser_odometry from source (no arm64 binary available for Humble)
RUN mkdir -p /opt/rf2o_ws/src \
    && cd /opt/rf2o_ws/src \
    && git clone --depth 1 https://github.com/MAPIRlab/rf2o_laser_odometry.git \
    && cd /opt/rf2o_ws \
    && . /opt/ros/humble/setup.sh \
    && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release \
    && rm -rf build log

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

# Service environment setup (guard against unbound AMENT_TRACE_SETUP_FILES when interactive shell uses set -u)
ENV AMENT_TRACE_SETUP_FILES=""
RUN echo ": \"\${AMENT_TRACE_SETUP_FILES:=}\"" >> /root/.bashrc && \
    echo 'source /opt/ros/humble/setup.bash' >> /root/.bashrc && \
    echo 'source /opt/rf2o_ws/install/setup.bash' >> /root/.bashrc && \
    printf '%s\n' "export PS1='\\[\\033[1;34m\\]slam_cont: \\[\\033[0m\\]'" >> /root/.bashrc

# Copy Python script into container
WORKDIR /app
COPY slam_manager.py /app/slam_manager.py
COPY run_mapping.sh /app/run_mapping.sh
RUN chmod +x /app/run_mapping.sh

# Unique operation mode: always runs slam_manager (slam_toolbox for localization),
# while mapping + recording can be manually started with the command: bash /app/run_mapping.sh
CMD ["bash", "-c", ": \"${AMENT_TRACE_SETUP_FILES:=}\"; source /opt/ros/humble/setup.bash && source /opt/rf2o_ws/install/setup.bash && python3 /app/slam_manager.py"]
