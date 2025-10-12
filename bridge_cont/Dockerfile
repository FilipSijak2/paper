FROM ros:humble

# Install dependencies (pyserial for serial comms, optional colorlog)
RUN apt-get update && apt-get install -y \
    python3-pip \
    ros-humble-rmw-cyclonedds-cpp \ 
    && rm -rf /var/lib/apt/lists/*

# Environment (ROS + nice prompt)
RUN echo "export AMENT_TRACE_SETUP_FILES=\${AMENT_TRACE_SETUP_FILES:-}" >> /root/.bashrc && \
    echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "export PS1='\[\033[1;34m\]bridge_cont: \[\033[0m\]'" >> /root/.bashrc

WORKDIR /app

# Copy bridge script (local copy placed in this directory)
COPY robot_serial_bridge.py /app/robot_serial_bridge.py
COPY run_bridge.sh /app/run_bridge.sh
RUN chmod +x /app/run_bridge.sh

# Install Python deps (only what's needed; rclpy already in base image)
RUN pip3 install --no-cache-dir pyserial colorlog

# Default env (can be overridden in compose)
ENV SERIAL_PORT=/dev/ttyUSB0 \
    SERIAL_BAUD=115200 \
    RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
    AMENT_TRACE_SETUP_FILES=""

# Healthcheck: simple ROS topic list (non-fatal if first seconds fail)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD bash -c 'source /opt/ros/humble/setup.bash && ros2 topic list >/dev/null 2>&1 || exit 1'

# Entry point runs the bridge with env-based config
CMD ["/app/run_bridge.sh"]
