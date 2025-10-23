############################################################
# RPi Camera ROS2 Plug & Play Docker
############################################################

# ---------- Stage 1: Build libcamera ----------
FROM ubuntu:24.04 AS libcamera_build
ENV DEBIAN_FRONTEND=noninteractive
ARG LIBCAMERA_REF=83cb8101
ARG ENABLE_PISP=true

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential meson ninja-build pkg-config cmake git \
    python3-ply python3-yaml python3-jinja2 \
    libboost-dev libgnutls28-dev libssl-dev libtiff-dev pybind11-dev \
    libjpeg-dev libepoxy-dev libdrm-dev libudev-dev libglib2.0-dev \
    curl ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone https://github.com/raspberrypi/libcamera.git libcamera && \
    cd libcamera && git checkout ${LIBCAMERA_REF}

WORKDIR /src/libcamera
RUN set -e; \
    if [ "${ENABLE_PISP}" = "true" ]; then \
        PIPELINES="rpi/vc4,rpi/pisp"; IPAS="rpi/vc4,rpi/pisp"; \
    else \
        PIPELINES="rpi/vc4"; IPAS="rpi/vc4"; \
    fi; \
    meson setup build --buildtype=release \
        -Dpipelines=$PIPELINES \
        -Dipas=$IPAS \
        -Dv4l2=true \
        -Dgstreamer=disabled \
        -Dtest=false \
        -Dlc-compliance=disabled \
        -Dcam=enabled \
        -Dqcam=disabled \
        -Ddocumentation=disabled \
        -Dpycamera=enabled; \
    ninja -C build; \
    ninja -C build install; \
    ldconfig; \
    mkdir -p /artifact/usr_local && cp -R /usr/local/* /artifact/usr_local/

# ---------- Stage 2: Build rpicam-ros ----------
FROM ros:humble-ros-base AS rpicam_ros_build
ENV DEBIAN_FRONTEND=noninteractive
ARG RPICAM_ROS_REF=main

RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential python3-colcon-common-extensions \
    ros-humble-image-transport-plugins curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=libcamera_build /artifact/usr_local/ /usr/local/
ENV LD_LIBRARY_PATH=/usr/local/lib/aarch64-linux-gnu:/usr/local/lib

WORKDIR /ws/src
RUN git clone --depth 1 --branch ${RPICAM_ROS_REF} https://github.com/raspberrypi/rpicam-ros.git

WORKDIR /ws
RUN bash -c "source /opt/ros/humble/setup.sh && colcon build --symlink-install"

# ---------- Stage 3: Runtime image ----------
FROM ros:humble-ros-base AS runtime
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-image-transport-plugins curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=libcamera_build /artifact/usr_local/ /usr/local/
COPY --from=rpicam_ros_build /ws/install /ws/install
ENV LD_LIBRARY_PATH=/usr/local/lib/aarch64-linux-gnu:/usr/local/lib
RUN groupadd -f video && usermod -aG video root

WORKDIR /app

# ----- Integrirani launch file direktno u container -----
RUN mkdir -p /app/launch
RUN echo "\
from launch import LaunchDescription\n\
from launch_ros.actions import Node\n\
\ndef generate_launch_description():\n\
    return LaunchDescription([\n\
        Node(\n\
            package='rpicam_ros',\n\
            executable='rpicam_node',\n\
            name='rpicam',\n\
            output='screen',\n\
            parameters=[{\n\
                'width': 1280,\n\
                'height': 720,\n\
                'fps': 30\n\
            }]\n\
        )\n\
    ])\n" > /app/launch/camera_launch.py

ENV CAMERA_WIDTH=1280 CAMERA_HEIGHT=720 CAMERA_FPS=30

ENTRYPOINT ["bash","-c","source /opt/ros/humble/setup.sh && source /ws/install/setup.sh && ros2 launch /app/launch/camera_launch.py"]

