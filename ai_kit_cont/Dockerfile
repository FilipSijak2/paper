FROM ros:jazzy-ros-base

WORKDIR /root
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive
# Hailo runtime (hailort + hailo-tappas-core) is NOT installed in the image.
# The host Pi provides the libraries via bind-mounts in docker-compose.yaml.
# Prerequisite on the host: sudo apt install hailo-all

# Ensure 'universe' is enabled.
# Ubuntu 24.04 uses DEB822 .sources files; append 'universe' to the Components
# line if it is missing. Fall back to the legacy sources.list modification for
# any image that still uses the old format.
RUN if find /etc/apt/sources.list.d -maxdepth 1 -name '*.sources' -print -quit | grep -q .; then \
  sed -i '/^Components:/ { /universe/! s/$/ universe/ }' /etc/apt/sources.list.d/*.sources; \
  else \
  sed -i 's/^# \(.*universe\)$/\1/' /etc/apt/sources.list 2>/dev/null || true; \
  grep -q "^deb.*universe" /etc/apt/sources.list 2>/dev/null \
  || echo "deb http://ports.ubuntu.com/ubuntu-ports noble universe" >> /etc/apt/sources.list; \
  fi

# Generic build/runtime dependencies used by Hailo examples.
RUN apt-get update -o Acquire::Retries=3 && \
  apt-get install -y --no-install-recommends \
  wget \
  curl \
  gnupg2 \
  python3 \
  python3-dev \
  python3-pip \
  python3-setuptools \
  python3-venv \
  python3-gi \
  python3-gst-1.0 \
  ffmpeg \
  build-essential \
  gcc \
  g++ \
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
  ros-jazzy-rmw-cyclonedds-cpp \
  ros-jazzy-cv-bridge \
  ros-jazzy-image-transport \
  ros-jazzy-image-transport-plugins \
  ros-jazzy-compressed-image-transport \
  ros-jazzy-vision-msgs && \
  rm -rf /var/lib/apt/lists/*

# NOTE: hailo-tappas-core is NOT installed during image build.
# TAPPAS 5.x is distributed as a pip wheel targeting Ubuntu 24.04 (Noble).
# The wheel requires hailort which in turn requires the HailoRT kernel module
# provided by the host Pi OS — unavailable in a QEMU CI build environment.
# start_ai_kit.sh installs it via pip at first container startup on the Pi.

# Clone Hailo examples (shallow). Models are downloaded at container first startup
# via start_ai_kit.sh to avoid bloating the image and slowing CI builds.
RUN git clone --depth 1 https://github.com/hailo-ai/hailo-rpi5-examples.git

COPY start_ai_kit.sh /app/start_ai_kit.sh
COPY realsense_hailo_node.py /app/realsense_hailo_node.py
RUN chmod +x /app/start_ai_kit.sh /app/realsense_hailo_node.py

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
  ROS_DOMAIN_ID=0 \
  RS_IMAGE_TOPIC=/camera/realsense/color/image_raw \
  RS_CAMERA_INFO_TOPIC=/camera/realsense/color/camera_info \
  RS_WAIT_TIMEOUT=30 \
  AI_KIT_REQUIRE_HAILO=1 \
  AI_KIT_RUN_NODE=1

CMD ["/app/start_ai_kit.sh"]
