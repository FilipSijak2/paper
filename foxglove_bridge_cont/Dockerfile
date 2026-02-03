FROM ros:humble

ENV DEBIAN_FRONTEND=noninteractive \
    ROS_DISTRO=humble \
    RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

ARG INSTALL_EDITORS=false

RUN set -e; \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    ros-${ROS_DISTRO}-foxglove-bridge \
    ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
    curl \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

RUN if [ "$INSTALL_EDITORS" = "true" ]; then \
    apt-get update && apt-get install -y --no-install-recommends nano && \
    rm -rf /var/lib/apt/lists/*; \
    else \
    echo "[foxglove_bridge] Skipping editor installation"; \
    fi

RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Europe/Zagreb

WORKDIR /foxglove_bridge

COPY start_bridge.sh /foxglove_bridge/start_bridge.sh
RUN chmod +x /foxglove_bridge/start_bridge.sh

RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> /root/.bashrc && \
    echo "export PS1='\[\033[1;34m\]foxglove_bridge: \[\033[0m\]'" >> /root/.bashrc

ENV FOXGLOVE_PORT=8765 \
    FOXGLOVE_ADDRESS=0.0.0.0 \
    FOXGLOVE_TLS=0 \
    FOXGLOVE_TLS_CERT=/etc/ssl/certs/foxglove_bridge.crt \
    FOXGLOVE_TLS_KEY=/etc/ssl/private/foxglove_bridge.key

CMD ["/foxglove_bridge/start_bridge.sh"]
# End of Dockerfile
