#!/bin/bash
set -e

# Copy custom components to Home Assistant configuration directory
mkdir -p /config/custom_components/your_custom_component
cp -r /custom_components/your_custom_component/* /config/custom_components/your_custom_component/

# Log the deployment
echo "My custom integration has been deployed!"
