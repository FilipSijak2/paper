FROM ros:humble

# `ros-humble-imu-tools` is intentionally omitted because it pulls in RViz
# plugins and a large GUI dependency chain that is not needed here and has been
# causing container build failures on ARM images.
ARG DEBIAN_FRONTEND=noninteractive
RUN set -e; \
    apt-get update -y; \
    apt-get install -y --no-install-recommends \
        python3-colcon-common-extensions \
        python3-yaml \
        tzdata \
        ros-humble-rmw-cyclonedds-cpp \
        ros-humble-rclpy \
        ros-humble-imu-filter-madgwick \
        ros-humble-robot-localization \
        ros-humble-diagnostic-msgs \
    ; \
    rm -rf /var/lib/apt/lists/*

# Optional: install editors (nano) only when explicitly requested.
# Use at build time: docker build --build-arg INSTALL_EDITORS=true -t your_tag .
ARG INSTALL_EDITORS=false
RUN if [ "$INSTALL_EDITORS" = "true" ]; then \
            echo "Installing editors (nano) for debugging..." && \
            apt-get update && apt-get install -y --no-install-recommends nano && \
            rm -rf /var/lib/apt/lists/*; \
        else \
            echo "Skipping editor installation (set INSTALL_EDITORS=true to enable)."; \
        fi

ENV TZ=Europe/Zagreb

# Configure the ROS environment.
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc \
    && printf '%s\n' "export PS1='\\[\\033[1;34m\\]sensor_fusion: \\[\\033[0m\\]'" >> /root/.bashrc

# Workspace setup
WORKDIR /app/ws
COPY ws/src ./src
COPY sensor_fusion.yaml /app/sensor_fusion.yaml

# Place config inside package tree so setup.py can install it
RUN mkdir -p src/sensor_fusion_pkg/config \
    && cp /app/sensor_fusion.yaml src/sensor_fusion_pkg/config/sensor_fusion.yaml \
    && bash -c "set -euo pipefail; \
    echo '[DEBUG] Python version:'; python3 --version; \
    echo '[DEBUG] Listing src tree:'; find src -maxdepth 4 -type f -print; \
    export AMENT_TRACE_SETUP_FILES=\${AMENT_TRACE_SETUP_FILES:-}; \
    export AMENT_PYTHON_EXECUTABLE=\${AMENT_PYTHON_EXECUTABLE:-}; \
    set +u; \
    source /opt/ros/humble/setup.bash; \
    set -u; \
    echo '[DEBUG] Running colcon build'; \
    colcon build --symlink-install --event-handlers console_cohesion+ console_direct+ --merge-install --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    || { RC=$?; echo '[COLCON_FAILED] Dumping first 120 lines of each log file:'; if [ -d log ]; then find log -maxdepth 4 -type f -print -exec sed -n '1,120p' {} \\; ; fi; exit \"$RC\"; }"

# Runtime wrapper (self-healing build if image tag mismatch or cache issue)
COPY run_sensor_fusion.sh /app/run_sensor_fusion.sh
RUN chmod +x /app/run_sensor_fusion.sh

# Version tag (can be overridden at run time)
ENV SF_VERSION_TAG=unset \
    SF_IMU_SOURCE=realsense \
    SF_IMU_INPUT_TOPIC=/camera/realsense/imu \
    SF_IMU_OUTPUT_TOPIC=/imu/data \
    SF_IMU_BASE_TOPIC=/imu/base_link \
    SF_EKF_CONFIG=/app/robot_localization.yaml

# Use wrapper script that ensures workspace is built & sourced before launching
CMD ["bash", "/app/run_sensor_fusion.sh"]
