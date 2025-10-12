FROM ros:humble

# Install necessary tools and ROS 2 packages
RUN apt-get update && apt-get install -y \
    apt-utils \
    python3-pip \
    libpq-dev \
    ros-humble-nav2-msgs \
    ros-humble-nav2-map-server \
    ros-humble-slam-toolbox \
    ros-humble-rosbag2-storage-mcap \
    imagemagick \
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

# Service environment setup (guard against unbound AMENT_TRACE_SETUP_FILES when interactive shell uses set -u)
ENV AMENT_TRACE_SETUP_FILES=""
RUN echo ': "${AMENT_TRACE_SETUP_FILES:=}"' >> /root/.bashrc && \
    echo 'source /opt/ros/humble/setup.bash' >> /root/.bashrc

# Set custom prompt (just 'slam_cont:' in blue)
RUN echo "export PS1='\[\033[1;34m\]slam_cont: \[\033[0m\]'" >> /root/.bashrc

# Install necessary Python dependencies
RUN pip3 install psycopg2 pyyaml pillow

# Copy Python script into container
WORKDIR /app
COPY slam_manager.py /app/slam_manager.py
COPY run_mapping.sh /app/run_mapping.sh
RUN chmod +x /app/run_mapping.sh

# Unique operation mode: always runs slam_manager (slam_toolbox for localization),
# while mapping + recording can be manually started with the command: bash /app/run_mapping.sh
CMD ["bash", "-c", ": \"${AMENT_TRACE_SETUP_FILES:=}\"; source /opt/ros/humble/setup.bash && python3 /app/slam_manager.py"]