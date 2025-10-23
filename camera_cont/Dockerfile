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
    && rm -rf /var/lib/apt/lists/*

# Optional: tools for debugging (comment out if image size critical)
# RUN apt-get update && apt-get install -y vim curl && rm -rf /var/lib/apt/lists/*

WORKDIR /ws/src
# Robust fetch: try shallow git clone (5 retries), fallback to tarball
RUN set -e; \
        for i in 1 2 3 4 5; do \
            echo "[rpicam-ros] Attempt $i git clone"; \
            git clone --depth 1 https://github.com/raspberrypi/rpicam-ros.git && break || sleep 3; \
            if [ $i -eq 5 ]; then \
                echo "[rpicam-ros] Git clone failed after retries, falling back to tarball"; \
                curl -L -o rpicam-ros.tar.gz https://github.com/raspberrypi/rpicam-ros/archive/refs/heads/main.tar.gz; \
                tar -xzf rpicam-ros.tar.gz; \
                mv rpicam-ros-main rpicam-ros; \
            fi; \
        done

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