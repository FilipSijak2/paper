FROM ros:humble-ros-base

############################################################
# Stage: Install dependencies & build rpicam-ros from source
############################################################
# The binary package ros-humble-rpicam-ros is not available, so we build it.
# This Dockerfile assumes ARM64 build on Raspberry Pi host. Cross-building on x86
# will not work unless you enable qemu / multi-arch emulation.

RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential python3-colcon-common-extensions \
    libcamera-dev libepoxy-dev libjpeg-dev libdrm-dev pkg-config \
    ros-humble-image-transport-plugins \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Optional: tools for debugging (comment out if image size critical)
# RUN apt-get update && apt-get install -y vim curl && rm -rf /var/lib/apt/lists/*

WORKDIR /ws/src
# Robust fetch: try shallow git clone (5 retries), fallback to tarball
ARG RPICAM_ROS_REF=main
ARG RPICAM_ROS_TARBALL_URL=https://codeload.github.com/raspberrypi/rpicam-ros/tar.gz/refs/heads/${RPICAM_ROS_REF}
RUN set -e; \
        echo "[rpicam-ros] Trying shallow git clone for ref ${RPICAM_ROS_REF}"; \
        if git clone --depth 1 --branch ${RPICAM_ROS_REF} https://github.com/raspberrypi/rpicam-ros.git; then \
                echo "[rpicam-ros] Git clone succeeded."; \
        else \
                echo "[rpicam-ros] Git clone failed. Falling back to tarball: ${RPICAM_ROS_TARBALL_URL}"; \
                curl -fsSL -o rpicam-ros.tar.gz ${RPICAM_ROS_TARBALL_URL}; \
                tar -xzf rpicam-ros.tar.gz; \
                mv rpicam-ros-${RPICAM_ROS_REF} rpicam-ros || mv rpicam-ros-* rpicam-ros; \
                rm rpicam-ros.tar.gz; \
        fi

WORKDIR /ws
RUN bash -c "source /opt/ros/humble/setup.sh && colcon build --symlink-install"

# Add video group (future non-root usage) - currently run as root
RUN groupadd -f video && usermod -aG video root

#############################################
# Runtime setup
#############################################
ENV ROS_WS=/ws
WORKDIR /app
COPY camera_launch.py /app/camera_launch.py

# Environment variables for dynamic resolution/FPS (can be overridden in compose)
ENV CAMERA_WIDTH=1280 \
    CAMERA_HEIGHT=720 \
    CAMERA_FPS=30

# Entry script: source both ROS and workspace overlays then launch
ENTRYPOINT ["bash","-c","source /opt/ros/humble/setup.sh && source /ws/install/setup.sh && ros2 launch /app/camera_launch.py width:=${CAMERA_WIDTH} height:=${CAMERA_HEIGHT} fps:=${CAMERA_FPS}"]