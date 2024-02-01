# Use the official Ubuntu base image
FROM ubuntu:jammy-20240111

ARG PYTHON_VERSION
ENV PYTHON_VERSION=${PYTHON_VERSION}

# Set the working directory in the container
WORKDIR /tmp

# Copy the script into the container
COPY install-docker-prereqs-inside.sh .

# Give execution rights on the script
RUN chmod +x install-docker-prereqs-inside.sh

# Run the script to install the prerequisites
RUN bash install-docker-prereqs-inside.sh

# Command to run when starting the container
CMD ["bash"]
