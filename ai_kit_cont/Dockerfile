FROM ros:humble-ros-base

WORKDIR /root

ENV DEBIAN_FRONTEND=noninteractive
# HAILO_TAPPAS_CORE_VERSION is consumed by start_ai_kit.sh at runtime, not
# during the image build (see comment below for why).
ENV HAILO_TAPPAS_CORE_VERSION=3.31.0+1-1

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

# NOTE: hailo-tappas-core is NOT installed during image build.
# The RPi binary packages (3.31.0+1-1) depend on Debian Bookworm libraries
# (libopencv-core406, libpython3.11, gstreamer1.0-libcamera) that are not
# available in Ubuntu Jammy (this base image). Building from GitHub source
# has the same problem since it links against hailort dev headers which
# themselves ship as Bookworm-only .debs.
#
# Solution: install hailo-tappas-core at first container startup on the real
# Raspberry Pi (which runs Raspberry Pi OS Bookworm and has all deps natively).
# start_ai_kit.sh handles this automatically.

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
