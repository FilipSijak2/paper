FROM ros:humble

# Install necessary tools and ROS 2 packages
RUN apt-get update && apt-get install -y \
    apt-utils \
    python3-pip \
    libpq-dev \
    ros-humble-nav2-msgs \
    ros-humble-slam-toolbox \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Service environment setup
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

# Set custom prompt (just 'slam_cont:' in blue)
RUN echo "export PS1='\[\033[1;34m\]slam_cont: \[\033[0m\]'" >> /root/.bashrc

# Install necessary Python dependencies
RUN pip3 install psycopg2 pyyaml pillow

# Copy Python script into container
WORKDIR /app
COPY slam_manager.py /app/slam_manager.py
COPY run_mapping.sh /app/run_mapping.sh
RUN chmod +x /app/run_mapping.sh

# Unique operation mode: always runs slam_manager (slam_toolbox for localization),
# while mapping + recording can be manually started with the command: bash /app/run_mapping.sh
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && python3 /app/slam_manager.py"]