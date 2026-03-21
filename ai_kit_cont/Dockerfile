FROM ros:humble-ros-base

WORKDIR /root

ENV DEBIAN_FRONTEND=noninteractive
ARG HAILO_TAPPAS_CORE_VERSION=3.28.2
ARG HAILO_TAPPAS_CORE_DEB_URL=

# Generic build/runtime dependencies used by Hailo examples.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    software-properties-common \
    wget \
    curl \
    ca-certificates \
    gnupg2 \
    python3 \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-venv \
    python3-gi \
    ffmpeg \
    x11-utils \
    build-essential \
    meson \
    pkg-config \
    cmake \
    rsync \
    git \
    libzmq3-dev \
    libcairo2-dev \
    libgirepository1.0-dev \
    gobject-introspection \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-libav \
    gstreamer1.0-tools \
    gstreamer1.0-x \
    gir1.2-gstreamer-1.0 \
    libopencv-dev \
    python3-opencv \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    ros-humble-image-transport-plugins \
    ros-humble-compressed-image-transport && \
    rm -rf /var/lib/apt/lists/*

# Install pinned Hailo TAPPAS package directly from the archive.
# This avoids mixing Ubuntu base repositories with Debian Bookworm metadata.
RUN set -e; \
    HAILO_DEB_URL="${HAILO_TAPPAS_CORE_DEB_URL:-https://archive.raspberrypi.com/debian/pool/main/h/hailo-tappas-core-${HAILO_TAPPAS_CORE_VERSION}/hailo-tappas-core-${HAILO_TAPPAS_CORE_VERSION}_${HAILO_TAPPAS_CORE_VERSION}_arm64.deb}"; \
    if [ "$(dpkg --print-architecture)" != "arm64" ]; then \
      echo "Hailo package is arm64-only; current arch is $(dpkg --print-architecture)" >&2; \
      exit 1; \
    fi; \
    apt-get update; \
    wget -O /tmp/hailo-tappas-core.deb "${HAILO_DEB_URL}"; \
    apt-get install -y --no-install-recommends /tmp/hailo-tappas-core.deb; \
    rm -f /tmp/hailo-tappas-core.deb; \
    rm -rf /var/lib/apt/lists/*
# Excludes hailort as it fails to install during build stage.

# Download Hailo examples/resources.
RUN git clone https://github.com/hailo-ai/hailo-rpi5-examples.git && \
    cd hailo-rpi5-examples && ./download_resources.sh

COPY start_ai_kit.sh /app/start_ai_kit.sh
COPY realsense_hailo_node.py /app/realsense_hailo_node.py
RUN chmod +x /app/start_ai_kit.sh /app/realsense_hailo_node.py

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
    ROS_DOMAIN_ID=0 \
    RS_IMAGE_TOPIC=/realsense/color/image_raw \
    RS_CAMERA_INFO_TOPIC=/realsense/color/camera_info \
    RS_WAIT_TIMEOUT=30 \
    AI_KIT_RUN_NODE=1

CMD ["/app/start_ai_kit.sh"]
