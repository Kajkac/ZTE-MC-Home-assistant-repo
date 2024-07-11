FROM homeassistant/amd64-base:latest

# Download and install s6-overlay
ADD https://github.com/just-containers/s6-overlay/releases/download/v2.2.0.3/s6-overlay-amd64.tar.gz /tmp/
RUN tar xzf /tmp/s6-overlay-amd64.tar.gz -C / && \
    rm /tmp/s6-overlay-amd64.tar.gz

# Copy your custom files
COPY run.sh /etc/cont-init.d/01-run.sh
RUN chmod +x /etc/cont-init.d/01-run.sh

# Use the s6-overlay init system
ENTRYPOINT ["/init"]
