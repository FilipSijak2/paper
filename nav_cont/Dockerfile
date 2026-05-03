FROM ros:humble

# Install Nav2 and supporting dependencies
RUN set -e; apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-navigation2 \
    ros-humble-nav2-bringup \
    ros-humble-nav2-map-server \
    ros-humble-nav2-amcl \
    ros-humble-nav2-lifecycle-manager \
    ros-humble-tf2-tools \
    ros-humble-tf2-geometry-msgs \
    ros-humble-xacro \
    ros-humble-diagnostic-updater \
    ros-humble-joy \
    ros-humble-teleop-twist-joy \
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

# Copy project into Docker container
WORKDIR /app
COPY . /app

# Add start script & goal forwarder (copied below by patch if not present)

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Europe/Zagreb

# Set custom prompt (just 'nav_cont:' in blue)
RUN printf '%s\n' "export PS1='\\[\\033[1;34m\\]nav_cont: \\[\\033[0m\\]'" >> /root/.bashrc

# Provide convenience for interactive shells
RUN echo 'source /opt/ros/humble/setup.bash' >> /root/.bashrc && \
    echo 'alias rl="ros2 lifecycle"' >> /root/.bashrc && \
    echo 'alias rtopics="ros2 topic list"' >> /root/.bashrc

# Default map file path can be overridden at runtime (must be mounted via compose)
ENV MAP_FILE=/srv/maps/active/map.yaml
ENV NAV2_PARAMS_FILE=/app/nav2_params.yaml
ENV GOAL_TOPIC=/move_base_simple/goal
ENV FORCE_MAP_WAIT=1

# Copy start script (added via patch) and make executable
COPY start_nav.sh /app/start_nav.sh
RUN chmod +x /app/start_nav.sh

# Entry: start nav2 bringup + goal forwarder + optional move script
CMD ["/app/start_nav.sh"]
