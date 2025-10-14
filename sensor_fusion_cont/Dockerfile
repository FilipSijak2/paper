FROM ros:humble

# Napomena: uklonjen paket 'ros-humble-serial' (nije službeni paket); koristimo pyserial iz pip-a.
RUN set -e; \
    apt-get update -y; \
    apt-get install -y --no-install-recommends \
        python3-pip \
        python3-colcon-common-extensions \
        python3-yaml \
        ros-humble-rmw-cyclonedds-cpp \
        ros-humble-rclpy \
        ros-humble-robot-localization \
        ros-humble-imu-tools \
        ros-humble-tf2-ros \
        ros-humble-geometry-msgs \
        ros-humble-nav-msgs \
        ros-humble-diagnostic-msgs \
    ; \
    rm -rf /var/lib/apt/lists/*

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

# Python dependencies (colcon via apt now)
RUN pip3 install --no-cache-dir pyserial numpy

RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Europe/Zagreb

# Postavi ROS okruženje
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc
RUN echo "export PS1='\[\033[1;34m\]sensor_fusion: \[\033[0m\]'" >> /root/.bashrc

# Workspace setup
WORKDIR /app/ws
COPY ws/src ./src
COPY sensor_fusion.yaml /app/sensor_fusion.yaml

# Place config inside package tree so setup.py can install it
RUN mkdir -p src/sensor_fusion_pkg/config \
    && cp /app/sensor_fusion.yaml src/sensor_fusion_pkg/config/sensor_fusion.yaml

# Build the workspace (verbose diagnostics)
RUN bash -c "set -euo pipefail; echo '[DEBUG] Python version:'; python3 --version; echo '[DEBUG] Listing src tree:'; find src -maxdepth 4 -type f -print"
RUN bash -c "set -e; source /opt/ros/humble/setup.bash; echo '[DEBUG] Running colcon build'; \
    colcon build --symlink-install --event-handlers console_cohesion+ console_direct+ --merge-install --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    || { code=$?; echo '[ERROR] Colcon failed; dumping first 120 lines of each log file:'; if [ -d log ]; then find log -type f -maxdepth 4 -print -exec sed -n '1,120p' {} \; ; fi; exit $code; }"

# Runtime wrapper (self-healing build if image tag mismatch or cache issue)
COPY run_sensor_fusion.sh /app/run_sensor_fusion.sh
RUN chmod +x /app/run_sensor_fusion.sh

# Version tag (can be overridden at run time)
ENV SF_VERSION_TAG=unset

# Use wrapper script that ensures workspace is built & sourced before launching
CMD ["bash", "/app/run_sensor_fusion.sh"]
