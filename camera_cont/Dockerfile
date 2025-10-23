############################################################
# Multi-stage build: libcamera + rpicam-ros + minimal runtime
############################################################

# ---------- Stage 1: Build latest libcamera (pinned) ----------
FROM ubuntu:24.04 AS libcamera_build
ENV DEBIAN_FRONTEND=noninteractive
ARG LIBCAMERA_REF=v0.4.0
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential meson ninja-build pkg-config cmake git \
        python3-ply python3-yaml \
        libboost-dev libgnutls28-dev libssl-dev libtiff-dev pybind11-dev \
        libjpeg-dev libepoxy-dev libdrm-dev curl ca-certificates && \
        rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git clone --depth 1 --branch ${LIBCAMERA_REF} https://github.com/raspberrypi/libcamera.git
WORKDIR /src/libcamera
RUN meson setup build --buildtype=release \
        -Dpipelines=rpi/vc4,rpi/pisp \
        -Dipas=rpi/vc4,rpi/pisp \
        -Dv4l2=true \
        -Dgstreamer=disabled \
        -Dtest=false \
        -Dlc-compliance=disabled \
        -Dcam=enabled \
        -Dqcam=disabled \
        -Ddocumentation=disabled \
        -Dpycamera=enabled
RUN ninja -C build
RUN ninja -C build install
# Export artifacts (avoid copying build tree)
RUN mkdir -p /artifact/usr_local && cp -R /usr/local/* /artifact/usr_local/

# ---------- Stage 2: Build rpicam-ros against libcamera ----------
FROM ros:humble-ros-base AS rpicam_ros_build
ENV DEBIAN_FRONTEND=noninteractive
ARG RPICAM_ROS_REF=main
RUN apt-get update && apt-get install -y --no-install-recommends \
        git build-essential python3-colcon-common-extensions \
        ros-humble-image-transport-plugins curl ca-certificates && \
        rm -rf /var/lib/apt/lists/*
COPY --from=libcamera_build /artifact/usr_local/ /usr/local/
ENV LD_LIBRARY_PATH=/usr/local/lib/aarch64-linux-gnu:/usr/local/lib:${LD_LIBRARY_PATH}
WORKDIR /ws/src
RUN set -e; \
        echo "[rpicam-ros] Fetching ref ${RPICAM_ROS_REF}"; \
        if git clone --depth 1 --branch ${RPICAM_ROS_REF} https://github.com/raspberrypi/rpicam-ros.git; then \
          echo "[rpicam-ros] Clone OK"; \
        else \
          echo "[rpicam-ros] Clone failed, fallback tarball"; \
          curl -fsSL -o rpicam-ros.tar.gz https://codeload.github.com/raspberrypi/rpicam-ros/tar.gz/refs/heads/${RPICAM_ROS_REF}; \
          tar -xzf rpicam-ros.tar.gz; mv rpicam-ros-* rpicam-ros; rm rpicam-ros.tar.gz; \
        fi
WORKDIR /ws
RUN bash -c "set -e; source /opt/ros/humble/setup.sh && colcon build --symlink-install"

# ---------- Stage 3: Runtime image ----------
FROM ros:humble-ros-base AS runtime
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-humble-image-transport-plugins curl ca-certificates && \
        rm -rf /var/lib/apt/lists/*
COPY --from=libcamera_build /artifact/usr_local/ /usr/local/
COPY --from=rpicam_ros_build /ws/install /ws/install
ENV LD_LIBRARY_PATH=/usr/local/lib/aarch64-linux-gnu:/usr/local/lib:${LD_LIBRARY_PATH}
RUN groupadd -f video && usermod -aG video root
WORKDIR /app
COPY camera_launch.py /app/camera_launch.py
ENV CAMERA_WIDTH=1280 CAMERA_HEIGHT=720 CAMERA_FPS=30
ENTRYPOINT ["bash","-c","source /opt/ros/humble/setup.sh && source /ws/install/setup.sh && ros2 launch /app/camera_launch.py width:=${CAMERA_WIDTH} height:=${CAMERA_HEIGHT} fps:=${CAMERA_FPS}"]