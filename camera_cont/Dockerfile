# ========= Stage 1: Build libcamera (RPi fork + PiSP for Pi5) =========
FROM ubuntu:22.04 AS libcamera_build
ENV DEBIAN_FRONTEND=noninteractive

# Commit koji si naveo da radi (PiSP OK)
ARG LIBCAMERA_REF=83cb8101

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential meson ninja-build cmake git pkg-config \
    python3 python3-pip python3-ply python3-yaml python3-jinja2 \
    pybind11-dev libevent-dev \
    libboost-dev libgnutls28-dev libssl-dev libtiff-dev \
    libjpeg-dev libepoxy-dev libdrm-dev libudev-dev libglib2.0-dev \
    curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /src
# brži tarball + fallback git
RUN set -e; \
  if curl -fsSL -o libcamera.tar.gz https://codeload.github.com/raspberrypi/libcamera/tar.gz/${LIBCAMERA_REF}; then \
    tar -xzf libcamera.tar.gz; mv libcamera-* libcamera; rm libcamera.tar.gz; \
  else \
    git clone https://github.com/raspberrypi/libcamera.git libcamera; \
    cd libcamera; git checkout ${LIBCAMERA_REF}; cd ..; \
  fi

WORKDIR /src/libcamera
RUN meson setup build --buildtype=release \
    -Dpipelines=rpi/vc4,rpi/pisp \
    -Dipas=rpi/vc4,rpi/pisp \
    -Dv4l2=enabled \
    -Dgstreamer=disabled \
    -Dtest=false \
    -Dlc-compliance=disabled \
    -Dcam=enabled \
    -Dqcam=disabled \
    -Ddocumentation=disabled \
    -Dpycamera=enabled && \
    ninja -C build && ninja -C build install && ldconfig

# spremi /usr/local artefakte
RUN mkdir -p /artifact/usr_local && cp -R /usr/local/* /artifact/usr_local/

# ========= Stage 2: Build rpicam-ros na ROS Humble =========
FROM ros:humble-ros-base AS rpicam_ros_build
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    git python3-colcon-common-extensions \
    ros-humble-image-transport-plugins && \
    rm -rf /var/lib/apt/lists/*

# libcamera iz stage1
COPY --from=libcamera_build /artifact/usr_local/ /usr/local/
ENV LD_LIBRARY_PATH=/usr/local/lib/aarch64-linux-gnu:/usr/local/lib:$LD_LIBRARY_PATH

# rpicam-ros source + build
WORKDIR /ws/src
RUN git clone --depth 1 https://github.com/raspberrypi/rpicam-ros.git
WORKDIR /ws
RUN bash -lc "set -e; source /opt/ros/humble/setup.sh && colcon build --symlink-install"

# ========= Stage 3: Runtime (minimal) =========
FROM ros:humble-ros-base AS runtime
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    v4l-utils ros-humble-image-transport-plugins && \
    rm -rf /var/lib/apt/lists/*

# libcamera + rpicam-ros
COPY --from=libcamera_build /artifact/usr_local/ /usr/local/
COPY --from=rpicam_ros_build /ws/install /ws/install

# start skripta
WORKDIR /app
COPY start_camera.sh /app/start_camera.sh
RUN chmod +x /app/start_camera.sh

ENV LD_LIBRARY_PATH=/usr/local/lib/aarch64-linux-gnu:/usr/local/lib:$LD_LIBRARY_PATH
RUN groupadd -f video && usermod -aG video root

# Default ENV (možeš prebrisati kroz compose)
ENV CAMERA_WIDTH=1280 \
    CAMERA_HEIGHT=720 \
    CAMERA_FPS=30 \
    CAMERA_FRAME_ID=camera_optical_frame \
    CAMERA_NAME=camera \
    CAMERA_INFO_URL=file:///data/camera_info.yaml \
    RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
    ROS_DOMAIN_ID=0

ENTRYPOINT ["/bin/bash","-lc","source /opt/ros/humble/setup.bash && source /ws/install/setup.bash && /app/start_camera.sh"]

