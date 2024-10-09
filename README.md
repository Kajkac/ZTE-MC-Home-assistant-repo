![GitHub](https://img.shields.io/github/license/Kajkac/ZTE-MC-Home-assistant-repo?cacheSeconds=1)
![GitHub Repo stars](https://img.shields.io/github/stars/Kajkac/ZTE-MC-Home-assistant-repo)
[![GitHub release](https://img.shields.io/github/release/Kajkac/ZTE-MC-Home-assistant-repo.svg)](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/releases/)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)

![CodeQL](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/codeql.yml/badge.svg?cacheSeconds=60)
[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/Kajkac/ZTE-MC-Home-assistant-repo/codeql.yml?branch=main&label=checks)](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/codeql.yml)
![Main Build](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/main.yml/badge.svg?cacheSeconds=60)
![Validate with hassfest](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/hassfest.yml/badge.svg?cacheSeconds=60)
![Validate with Hass Action](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/validate.yml/badge.svg?cacheSeconds=60)


![GitHub contributors](https://img.shields.io/github/contributors/Kajkac/ZTE-MC-Home-assistant-repo)
![Maintenance](https://img.shields.io/maintenance/yes/2025)
![GitHub commit activity](https://img.shields.io/github/commit-activity/y/Kajkac/ZTE-MC-Home-assistant-repo)
![GitHub commits since tagged version](https://img.shields.io/github/commits-since/juacas/zte_tracker/v1.0.0)
![GitHub last commit](https://img.shields.io/github/last-commit/Kajkac/ZTE-MC-Home-assistant-repo)
![Codecov branch](https://img.shields.io/codecov/c/github/Kajkac/ZTE-MC-Home-assistant-repo/master?cacheSeconds=3600)
![installation_badge](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.zte_router.total)

# ZTE Router Integration for Home Assistant
Component to integrate some ZTE routers as a device tracker in Home Assistant. 
This repository contains the ZTE Router custom integration and an add-on to deploy it in Home Assistant. The custom integration is located in the `custom_components/zte_router` directory.

## Installation
### Manual Installation

1. Download the latest [zte-router](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/releases/latest/download/zte_router.zip) release
2. Place the files of the .zip in your **root directory of Home Assistant** (That should only effectively place files into `/custom_components/zte_router`)
3. Restart Home Assistant
4. Go to `Settings` > `Devices and Services` to search and add the ZTE Router integration
5. Select the model you have and enter the Router IP, password and wait for the integration to install all the device sensors.

### Installation with HACS

**Method 1**

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Kajkac&repository=ZTE-MC-Home-assistant-repo&category=integration) 
- Work in Progress (waiting for [this](https://github.com/hacs/default/pull/2662) HACS PR to be completed)

**Method 2**
1. `HACS` > `Integrations` > `⋮` > `Custom Repositories`
2. `Repository`: paste the URL of this repo
3. `Category`: Integration
4. Click `Add`
5. Close `Custom Repositories` modal
6. Click `+ EXPLORE & DOWNLOAD REPOSITORIES`
7. Search for `ZTE router`
8. Click `Download`
9. Restart Home Assistant
10. Search for "integration" in the ZTE Router integration and add it to Home Assistant or click on this link:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=zte_router)

11. Select the model and enter the router's IP and password.
12. Wait for the integration to install all the device sensors.

###  Configuration
Supported models:
- MC801A
- MC889
- MC889A
- MC888
- MC888A

![SCreenshot](https://raw.githubusercontent.com/Kajkac/ZTE-MC-Home-assistant-repo/main/zte.png)

## Bugs: 
1. Username currently not supported
2. Errors in Home Assistant log - They are for now present until I polish the addon
2. Various errors in sensors etc. - This integration is classified as beta right now but can be tested by anyone. 
4. For suggestions, please open a new issue
5. I will push new builds as soon I will have more time. Make sure you "star" this integration. 
6. If u wanna donate for beer, let me know :P 

## Contributors
If u have any suggestion, or you are doing pull requests and adding new features, increment the version number by 1 in manifest.json, so that GitHub automation automatically creates a new release.
