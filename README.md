![GitHub](https://img.shields.io/github/license/juacas/zte_tracker)
![GitHub Repo stars](https://img.shields.io/github/stars/juacas/zte_tracker)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/juacas/zte_tracker)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
<!-- ![Pytest](https://github.com/juacas/zte_tracker/workflows/Pytest/badge.svg?branch=master)
![CodeQL](https://github.com/juacas/zte_tracker/workflows/CodeQL/badge.svg?branch=master) -->
![Validate with hassfest](https://github.com/juacas/zte_tracker/workflows/Validate%20with%20hassfest/badge.svg?branch=master)

![GitHub contributors](https://img.shields.io/github/contributors/juacas/zte_tracker)
![Maintenance](https://img.shields.io/maintenance/yes/2025)
![GitHub commit activity](https://img.shields.io/github/commit-activity/y/juacas/zte_tracker)
![GitHub commits since tagged version](https://img.shields.io/github/commits-since/juacas/zte_tracker/v1.0.0)
![GitHub last commit](https://img.shields.io/github/last-commit/juacas/zte_tracker)
<!-- ![Codecov branch](https://img.shields.io/codecov/c/github/juacas/zte_tracker/master) -->
![installation_badge](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.zte_tracker.total)

# ZTE Router Integration for Home Assistant
Component to integrate some ZTE routers as a device trackers in home assistant.

# ZTE Home assistant addon
**ZTE Home assistant addon**

Supported models : 

```
MC801A
MC889
MC888
```
![enter image description here](https://raw.githubusercontent.com/Kajkac/ZTE-MC-Home-assistant-repo/main/zte.png)

This repository contains the ZTE Router custom integration and an add-on to deploy it in Home Assistant.

## Custom Integration

The custom integration is located in the `custom_components/zte_router` directory.

## Manual installation

Copy the custom_components/zte_router of this repo into the path /config/custom_components/zte_router of your HA installation.

Restart Home Assistant go to Settings -> integrations -> Add integration 
Find integration ZTE Router 

Enter Router IP , password and select the model you have and wait for integration to install all the device sensors

## Bugs: 

1. Username currently not supported
2. Errors in Home assistant log - They are for now present until i polish the addon 
2. Various errors in sensors etc. - This integration is classified as beta right now but can be tested by anyone. 
4. Any suggestion you have please open the issues tab
5. I will push new builds as soon i will have more time. Make sure you "star" this integration. 
6. If u wanna donate for beer let me know :P 

## HACS installation

When i polish the addon i will try to push it to HACS, but for now its only manual
