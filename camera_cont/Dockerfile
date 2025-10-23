# Dockerfile.rpi-camera
FROM ubuntu:24.10

# --- ARGs to configure build ---
ARG ENABLE_PISP=false
ARG V4L2=enabled

# --- Install build dependencies ---
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential \
    meson \
    ninja-build \
    git \
    pkg-config \
    libv4l-dev \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# --- Set working directory ---
WORKDIR /src

# --- Clone Raspberry Pi camera driver (example repo, prilagodi po potrebi) ---
RUN git clone https://github.com/raspberrypi/libcamera.git .

# --- Build & install ---
RUN set -e; \
    if [ "${ENABLE_PISP}" = "true" ]; then \
        PIPELINES="rpi/vc4,rpi/pisp"; \
        IPAS="rpi/vc4,rpi/pisp"; \
    else \
        PIPELINES="rpi/vc4"; \
        IPAS="rpi/vc4"; \
    fi; \
    meson setup build --buildtype=release \
        -Dpipelines=$PIPELINES \
        -Dipas=$IPAS \
        -Dv4l2=$V4L2 \
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

# --- Expose mount for testing (npr. for ROS) ---
VOLUME ["/dev"]  

CMD ["bash"]