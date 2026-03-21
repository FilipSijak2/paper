FROM ros:humble-ros-base

WORKDIR /root

ENV DEBIAN_FRONTEND=noninteractive
ARG HAILO_TAPPAS_CORE_VERSION=3.31.0+1-1

# Enable the Ubuntu 'universe' repository before the main install.
# Many packages required here (ffmpeg, gstreamer codecs, OpenCV, etc.) live in
# universe, which is NOT always active in the ros:humble-ros-base arm64 image.
# We use sed directly instead of add-apt-repository to avoid installing
# software-properties-common, whose libc-bin post-install script triggers a
# QEMU arm64 segfault (signal 11) under GitHub Actions cross-compilation.
RUN sed -i 's/^# \(.*universe\)$/\1/' /etc/apt/sources.list && \
  grep -q "^deb.*universe" /etc/apt/sources.list \
  || echo "deb http://ports.ubuntu.com/ubuntu-ports $(. /etc/os-release; echo $VERSION_CODENAME) universe" \
  >> /etc/apt/sources.list

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
  ros-humble-rmw-cyclonedds-cpp \
  ros-humble-cv-bridge \
  ros-humble-image-transport \
  ros-humble-image-transport-plugins \
  ros-humble-compressed-image-transport && \
  rm -rf /var/lib/apt/lists/*

# Install Hailo TAPPAS Core for Raspberry Pi AI Kit.
# Package naming convention changed in 3.31+: the binary package is now just
# 'hailo-tappas-core' (version 3.31.0+1-1 in the RPi stable/bookworm repo).
# Older 3.28.x embeds the version in the package name — not used here.
# python-gi-dev: obsolete Python 2-era package that hailo depends on;
# satisfied with a dummy .deb that re-maps it to Depends: python3-gi.
RUN set -e; \
  if [ "$(dpkg --print-architecture)" != "arm64" ]; then \
  echo "ERROR: Hailo packages are arm64-only. Build with --platform linux/arm64." >&2; \
  exit 1; \
  fi; \
  \
  mkdir -p /tmp/python-gi-dev-compat/DEBIAN; \
  printf '%s\n' \
  'Package: python-gi-dev' \
  'Version: 99.0~dummy' \
  'Section: misc' \
  'Priority: optional' \
  'Architecture: all' \
  'Depends: python3-gi' \
  'Maintainer: dummy' \
  'Description: Dummy package mapping python-gi-dev to python3-gi' \
  > /tmp/python-gi-dev-compat/DEBIAN/control; \
  dpkg-deb --build /tmp/python-gi-dev-compat /tmp/python-gi-dev-compat.deb; \
  dpkg -i /tmp/python-gi-dev-compat.deb; \
  rm -rf /tmp/python-gi-dev-compat /tmp/python-gi-dev-compat.deb; \
  \
  mkdir -p /etc/apt/keyrings; \
  wget --tries=5 --waitretry=15 --timeout=60 -qO- \
  https://archive.raspberrypi.com/debian/raspberrypi.gpg.key \
  | gpg --dearmor > /etc/apt/keyrings/raspberrypi-archive-keyring.gpg; \
  echo "deb [signed-by=/etc/apt/keyrings/raspberrypi-archive-keyring.gpg] http://archive.raspberrypi.com/debian/ bookworm main" \
  > /etc/apt/sources.list.d/raspi.list; \
  printf '%s\n' \
  'Package: *' \
  'Pin: origin "archive.raspberrypi.com"' \
  'Pin-Priority: 100' \
  '' \
  'Package: hailo-*' \
  'Pin: origin "archive.raspberrypi.com"' \
  'Pin-Priority: 1001' \
  > /etc/apt/preferences.d/raspi-hailo.pref; \
  apt-get update -o Acquire::Retries=3; \
  \
  echo "[hailo] Installing hailo-tappas-core (=${HAILO_TAPPAS_CORE_VERSION}) from RPi archive"; \
  apt-get install -y --no-install-recommends \
  "hailo-tappas-core=${HAILO_TAPPAS_CORE_VERSION}" \
  || { \
  echo "[hailo][ERROR] Could not install hailo-tappas-core=${HAILO_TAPPAS_CORE_VERSION}" >&2; \
  echo "[hailo]        Versions available in RPi archive:" >&2; \
  apt-cache policy hailo-tappas-core 2>/dev/null >&2 || true; \
  apt-cache search hailo 2>/dev/null >&2 || true; \
  exit 1; \
  }; \
  \
  rm -f /etc/apt/sources.list.d/raspi.list \
  /etc/apt/preferences.d/raspi-hailo.pref; \
  rm -rf /var/lib/apt/lists/*
# hailort daemon/kernel module is not available during build; it is provided
# by the host RPi OS at runtime. gst-inspect-1.0 hailonet is therefore NOT
# validated here — hailonet will be functional at container runtime on the Pi.

# Clone Hailo examples (shallow). Models are downloaded at container first startup
# via start_ai_kit.sh to avoid bloating the image and slowing CI builds.
RUN git clone --depth 1 https://github.com/hailo-ai/hailo-rpi5-examples.git

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
