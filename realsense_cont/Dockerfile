FROM ros:humble
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN set -e; \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    apt-transport-https \
    && rm -rf /var/lib/apt/lists/*

# Install librealsense from RealSense apt repo (userspace libs + tools)
RUN set -e; \
    . /etc/os-release; \
    codename="${VERSION_CODENAME}"; \
    mkdir -p /etc/apt/keyrings; \
    curl -sSf https://librealsense.realsenseai.com/Debian/librealsenseai.asc | gpg --dearmor > /etc/apt/keyrings/librealsenseai.gpg; \
    printf 'deb [signed-by=/etc/apt/keyrings/librealsenseai.gpg] https://librealsense.realsenseai.com/Debian/apt-repo %s main\n' "$codename" > /etc/apt/sources.list.d/librealsense.list; \
    apt-get update && apt-get install -y --no-install-recommends \
    librealsense2-utils \
    librealsense2-dev \
    usbutils \
    ros-humble-realsense2-camera \
    ros-humble-realsense2-description \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-image-transport-plugins \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Europe/Zagreb
WORKDIR /app

COPY start_realsense.sh /app/start_realsense.sh
RUN chmod +x /app/start_realsense.sh

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
    RS_CAMERA_NAME=realsense \
    RS_SERIAL= \
    RS_USB_PORT_ID= \
    RS_ENABLE_DEPTH=true \
    RS_ENABLE_COLOR=true \
    RS_ENABLE_INFRA1=false \
    RS_ENABLE_INFRA2=false \
    RS_ENABLE_GYRO=true \
    RS_ENABLE_ACCEL=true \
    RS_UNITE_IMU_METHOD=linear_interpolation \
    RS_BASE_FRAME_ID= \
    RS_DEPTH_PROFILE=640x480x15 \
    RS_COLOR_PROFILE=640x480x15 \
    RS_GYRO_FPS=200 \
    RS_ACCEL_FPS=100 \
    RS_ALIGN_DEPTH=true \
    RS_ENABLE_POINTCLOUD=true

CMD ["/app/start_realsense.sh"]
