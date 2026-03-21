FROM ros:humble-ros-base

WORKDIR /root

ENV DEBIAN_FRONTEND=noninteractive
ARG HAILO_TAPPAS_CORE_VERSION=3.28.2

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
  python3-gst-1.0 \
  ffmpeg \
  x11-utils \
  build-essential \
  gcc-12 \
  g++-12 \
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

# Install pinned Hailo TAPPAS core package for Raspberry Pi AI Kit.
# This step is strict by design: if Hailo cannot be installed the build fails.
# GitHub Actions builds for linux/arm64 via QEMU; local builds must also use
# --platform linux/arm64 (docker buildx build --platform linux/arm64 ...).
RUN set -e; \
  if [ "$(dpkg --print-architecture)" != "arm64" ]; then \
  echo "ERROR: Hailo package is arm64-only. Build with --platform linux/arm64." >&2; \
  exit 1; \
  fi; \
  mkdir -p /tmp/python-gi-dev-compat/DEBIAN; \
  printf '%s\n' \
  'Package: python-gi-dev' \
  'Version: 0.0.1' \
  'Section: misc' \
  'Priority: optional' \
  'Architecture: all' \
  'Depends: python3-gi' \
  'Description: Compatibility package mapping python-gi-dev to python3-gi on Ubuntu' \
  > /tmp/python-gi-dev-compat/DEBIAN/control; \
  dpkg-deb --build /tmp/python-gi-dev-compat /tmp/python-gi-dev-compat.deb; \
  apt-get update; \
  apt-get install -y --no-install-recommends /tmp/python-gi-dev-compat.deb; \
  rm -rf /tmp/python-gi-dev-compat /tmp/python-gi-dev-compat.deb; \
  mkdir -p /etc/apt/keyrings; \
  wget --tries=5 --waitretry=10 --timeout=30 -qO- https://archive.raspberrypi.com/debian/raspberrypi.gpg.key | gpg --dearmor > /etc/apt/keyrings/raspberrypi-archive-keyring.gpg; \
  echo "deb [signed-by=/etc/apt/keyrings/raspberrypi-archive-keyring.gpg] http://archive.raspberrypi.com/debian/ bookworm main" > /etc/apt/sources.list.d/raspi.list; \
  printf '%s\n' \
  'Package: *' \
  'Pin: origin "archive.raspberrypi.com"' \
  'Pin-Priority: 100' \
  '' \
  'Package: hailo-*' \
  'Pin: origin "archive.raspberrypi.com"' \
  'Pin-Priority: 1001' \
  > /etc/apt/preferences.d/raspi-hailo.pref; \
  apt-get update; \
  echo "[hailo] Installing hailo-tappas-core-${HAILO_TAPPAS_CORE_VERSION} from Raspberry Pi archive"; \
  apt-get install -y --no-install-recommends "hailo-tappas-core-${HAILO_TAPPAS_CORE_VERSION}" \
  || { \
  echo "[ERROR] hailo-tappas-core-${HAILO_TAPPAS_CORE_VERSION} could not be installed." >&2; \
  echo "Packages available in the Raspberry Pi archive matching 'hailo':" >&2; \
  apt-cache search hailo 2>/dev/null >&2 || true; \
  exit 1; \
  }; \
  rm -f /etc/apt/sources.list.d/raspi.list; \
  rm -f /etc/apt/preferences.d/raspi-hailo.pref; \
  rm -rf /var/lib/apt/lists/*
# hailort daemon/kernel module is not available during build; it is provided
# by the host RPi OS at runtime. gst-inspect-1.0 hailonet is therefore NOT
# validated here — hailonet will be functional at container runtime on the Pi.

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
  AI_KIT_REQUIRE_HAILO=1 \
  AI_KIT_RUN_NODE=1

CMD ["/app/start_ai_kit.sh"]
