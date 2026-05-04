FROM ros:humble

# Install dependencies (pyserial for serial comms, optional colorlog)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-colorlog \
    python3-serial \
    python3-smbus2 \
    python3-pip \
    python3-lgpio \
    ros-humble-rmw-cyclonedds-cpp \
    && (apt-cache show python3-rpi-lgpio >/dev/null 2>&1 \
        && apt-get install -y --no-install-recommends python3-rpi-lgpio \
        || (python3 -m pip help install | grep -q -- '--break-system-packages' \
            && python3 -m pip install --no-cache-dir --break-system-packages rpi-lgpio \
            || python3 -m pip install --no-cache-dir rpi-lgpio)) \
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

# Environment (ROS + nice prompt)
RUN echo "export AMENT_TRACE_SETUP_FILES=\${AMENT_TRACE_SETUP_FILES:-}" >> /root/.bashrc && \
    echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    printf '%s\n' "export PS1='\\[\\033[1;34m\\]bridge_cont: \\[\\033[0m\\]'" >> /root/.bashrc

RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Europe/Zagreb

WORKDIR /app

# Copy bridge script (local copy placed in this directory)
COPY robot_serial_bridge.py /app/robot_serial_bridge.py
COPY robot_rpi_direct_bridge.py /app/robot_rpi_direct_bridge.py
COPY run_bridge.sh /app/run_bridge.sh
RUN chmod +x /app/run_bridge.sh

# Default env (can be overridden in compose)
ENV SERIAL_PORT=/dev/ttyUSB0 \
    SERIAL_BAUD=115200 \
    BRIDGE_MODE=serial_legacy \
    RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
    AMENT_TRACE_SETUP_FILES=""

# Healthcheck: simple ROS topic list (non-fatal if first seconds fail)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD bash -c 'source /opt/ros/humble/setup.bash && ros2 topic list >/dev/null 2>&1 || exit 1'

# Entry point runs the bridge with env-based config
CMD ["/app/run_bridge.sh"]
