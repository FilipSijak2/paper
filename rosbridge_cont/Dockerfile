# Koristi službeni ROS 2 Humble image kao osnovu
FROM ros:humble

# ------------------------------------------------------------
# ROSBridge container
# Pojednostavljeni Dockerfile – uklonjeno ručno mijenjanje ROS repozitorija
# jer bazni image već sadrži ispravno podešen keyring i source liste.
# Dodani su dijagnostički koraci u slučaju da apt zakaže (exit code 100).
# ------------------------------------------------------------

ENV DEBIAN_FRONTEND=noninteractive \
    ROS_DISTRO=humble

## Opcionalni argumenti
ARG ROS_EXTRA_PACKAGES=""
ARG DEBUG_APT="false"

# Instalacija potrebnih ROS paketa + osnovnih alata; uz robustniji apt update
RUN set -eu; \
        echo "[rosbridge] Updating APT metadata..."; \
        apt-get update -o Acquire::Retries=3; \
        echo "[rosbridge] Installing base & ROS packages..."; \
        if [ "$DEBUG_APT" = "true" ]; then set -x; fi; \
        apt-get install -y --no-install-recommends \
                ros-${ROS_DISTRO}-rosbridge-server \
                ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
                python3-colcon-common-extensions \
                curl ca-certificates \
                $ROS_EXTRA_PACKAGES \
                && echo "[rosbridge] Packages installed." \
                || { \
                    rc=$?; echo "[rosbridge][ERROR] apt install failed (rc=$rc)" >&2; \
                    echo '---- /etc/apt/sources.list:' >&2; sed -n '1,120p' /etc/apt/sources.list >&2 || true; \
                    echo '---- /etc/apt/sources.list.d listing:' >&2; ls -1 /etc/apt/sources.list.d/ >&2 || true; \
                    echo '---- ROS related entries:' >&2; grep -R "ros2/ubuntu" -n /etc/apt/sources.list.d/ || true; \
                    echo '---- /var/log/apt/term.log (tail):' >&2; tail -n 60 /var/log/apt/term.log 2>/dev/null || echo '[no term.log]'; \
                    exit $rc; \
                }; \
        rm -rf /var/lib/apt/lists/*; \
        if [ "$DEBUG_APT" = "true" ]; then set +x; fi

# Postavi radni direktorij na /ros_ws
WORKDIR /ros_ws

# Kopiraj samo manifest datoteke prvo (bolje keširanje) pa ostatak izvornog koda
COPY ./src /ros_ws/src

# Build radnog prostora
RUN bash -c "set -e; source /opt/ros/${ROS_DISTRO}/setup.bash && colcon build --symlink-install"

# Pokreni rosbridge automatski koristeći XML launch datoteku
CMD ["bash", "-c", "source /opt/ros/${ROS_DISTRO}/setup.bash && source /ros_ws/install/setup.bash && ros2 launch rosbridge_server rosbridge_websocket_launch.xml"]