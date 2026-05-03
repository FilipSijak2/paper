FROM ros:humble

# ---------------------------------------------------------
# ROSBridge container
# Simplified Dockerfile – removed manual ROS repository changes
# since the base image already contains a correctly configured keyring and source lists.
# Diagnostic steps have been added in case apt fails (exit code 100).
# ------------------------------------------------------------

ENV DEBIAN_FRONTEND=noninteractive \
    ROS_DISTRO=humble

# Optional arguments
ARG ROS_EXTRA_PACKAGES=""
ARG DEBUG_APT="false"

# Install necessary ROS packages + basic tools; with more robust apt update
RUN set -eu; \
        echo "[rosbridge] Updating APT metadata..."; \
        apt-get update -o Acquire::Retries=3; \
        echo "[rosbridge] Installing base & ROS packages..."; \
        if [ "$DEBUG_APT" = "true" ]; then set -x; fi; \
        if ! apt-get install -y --no-install-recommends \
                ros-${ROS_DISTRO}-rosbridge-server \
                ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
                python3-colcon-common-extensions \
                curl ca-certificates \
                $ROS_EXTRA_PACKAGES; then \
                    rc=$?; echo "[rosbridge][ERROR] apt install failed (rc=$rc)" >&2; \
                    echo '---- /etc/apt/sources.list:' >&2; sed -n '1,120p' /etc/apt/sources.list >&2 || true; \
                    echo '---- /etc/apt/sources.list.d listing:' >&2; ls -1 /etc/apt/sources.list.d/ >&2 || true; \
                    echo '---- ROS related entries:' >&2; grep -R "ros2/ubuntu" -n /etc/apt/sources.list.d/ || true; \
                    echo '---- /var/log/apt/term.log (tail):' >&2; tail -n 60 /var/log/apt/term.log 2>/dev/null || echo '[no term.log]'; \
                    exit $rc; \
                fi; \
        echo "[rosbridge] Packages installed."; \
        rm -rf /var/lib/apt/lists/*; \
        if [ "$DEBUG_APT" = "true" ]; then set +x; fi

# Set working directory to /ros_ws
RUN printf '%s\n' "source /opt/ros/${ROS_DISTRO}/setup.bash" >> /root/.bashrc \
    && printf '%s\n' "export PS1='\\[\\033[1;34m\\]rosbridge: \\[\\033[0m\\]'" >> /root/.bashrc
WORKDIR /ros_ws

RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Europe/Zagreb

# Copy only manifest files first (better caching) then the rest of the source code
COPY ./src /ros_ws/src

# Build workspace with colcon
RUN bash -c "set -e; source /opt/ros/${ROS_DISTRO}/setup.bash && colcon build --symlink-install"

# Start rosbridge automatically using XML launch file
CMD ["bash", "-c", "source /opt/ros/${ROS_DISTRO}/setup.bash && source /ros_ws/install/setup.bash && ros2 launch rosbridge_server rosbridge_websocket_launch.xml"]
