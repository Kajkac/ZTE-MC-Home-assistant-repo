#!/bin/bash
set -e

# Copy custom components to Home Assistant configuration directory
mkdir -p /config/custom_components/zte_router
cp -r /custom_components/zte_router/* /config/custom_components/zte_router/

# Log the deployment
echo "ZTE Router custom integration has been deployed!"
