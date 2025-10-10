FROM ros:humble

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Copy project into Docker container
WORKDIR /app
COPY . /app

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Set custom prompt (just 'nav_cont:' in blue)
RUN echo "export PS1='\[\033[1;34m\]nav_cont: \[\033[0m\]'" >> /root/.bashrc

# Set entrypoint for launching ROS 2 nodes
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && python3 move.py & python3 path_planner.py"]