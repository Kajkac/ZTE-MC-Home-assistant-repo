![GitHub](https://img.shields.io/github/license/Kajkac/ZTE-MC-Home-assistant-repo)
![GitHub Repo stars](https://img.shields.io/github/stars/Kajkac/ZTE-MC-Home-assistant-repo)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/Kajkac/ZTE-MC-Home-assistant-repo)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
<!-- ![Pytest](https://github.com/juacas/zte_tracker/workflows/Pytest/badge.svg?branch=master)
![CodeQL](https://github.com/juacas/zte_tracker/workflows/CodeQL/badge.svg?branch=master) -->
![Validate with hassfest](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/workflows/Validate%20with%20hassfest/badge.svg?branch=master)

![GitHub contributors](https://img.shields.io/github/contributors/Kajkac/ZTE-MC-Home-assistant-repo)
![Maintenance](https://img.shields.io/maintenance/yes/2025)
![GitHub commit activity](https://img.shields.io/github/commit-activity/y/Kajkac/ZTE-MC-Home-assistant-repo)
![GitHub last commit](https://img.shields.io/github/last-commit/Kajkac/ZTE-MC-Home-assistant-repo)
<!-- ![Codecov branch](https://img.shields.io/codecov/c/github/juacas/zte_tracker/master) -->

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



## Installation

### Manual Installation

1. Download the [zte-router](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/releases/latest/download/zte_router.zip)
2. Place the files of the .zip in your `root directory of homeassistant` (That should only effectivly place files into /custom_components/zte/router)
3. Restart Homeassistant
4. Search in "integration" for the ZTE_Router integration and add it to Homeassistant
5. Configure your integration.

### Installation with HACS

1. Make sure the [HACS](https://github.com/custom-components/hacs) component is installed and working.
2. Click on integration, "3 dots menu", custom repositories and add 'https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/' to your repositories.
3. Search for the ZTE Router integration (blue button on lower page) 
4. Restart homeassistant.
5. Add ZTE Router Integration to your integrations and configure it.

