#!/usr/bin/with-contenv bashio

# Copy custom components to the Home Assistant config directory
mkdir -p /config/custom_components/zte_router
cp -r /custom_components/zte_router/* /config/custom_components/zte_router/

echo "Custom integration has been installed."
