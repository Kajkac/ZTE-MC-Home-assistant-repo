#!/usr/bin/with-contenv bashio

# Copy custom integration to the appropriate Home Assistant directory
mkdir -p /config/custom_components/zte_router
cp -r /custom_components/zte_router/* /config/custom_components/zte_router/

echo "Custom integration copied successfully."
