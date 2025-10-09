FROM ros:humble

# OS dependencies + ROS 2 paketi
# Napomena: uklonjen paket 'ros-humble-serial' (nije službeni paket); koristimo pyserial iz pip-a.
RUN set -e; \
        apt-get update -y; \
        apt-get install -y --no-install-recommends \
            python3-pip \
            python3-yaml \
            ros-humble-robot-localization \
            ros-humble-imu-tools \
            ros-humble-tf2-ros \
            ros-humble-geometry-msgs \
            ros-humble-nav-msgs \
            ros-humble-diagnostic-msgs \
        ; \
        rm -rf /var/lib/apt/lists/*

# Python dependencies & build tools
RUN pip3 install --no-cache-dir pyserial numpy colcon-common-extensions

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
RUN bash -c 'set -euo pipefail \ 
    && echo "[DEBUG] Python version: $(python3 --version)" \ 
    && echo "[DEBUG] Listing src tree:" \ 
    && find src -maxdepth 4 -type f -print \ 
    && echo "[DEBUG] Launching colcon build (verbose)" \ 
    && source /opt/ros/humble/setup.bash \ 
    && colcon build --symlink-install --event-handlers console_cohesion+ console_direct+ --merge-install --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo || { echo "[ERROR] Colcon failed; dumping logs"; ls -R log || true; exit 1; }'

# Source overlay and launch package
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && source /app/ws/install/setup.bash && ros2 launch sensor_fusion_pkg sensor_fusion.launch.py"]
