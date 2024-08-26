![GitHub](https://img.shields.io/github/license/Kajkac/ZTE-MC-Home-assistant-repo)
![GitHub Repo stars](https://img.shields.io/github/stars/Kajkac/ZTE-MC-Home-assistant-repo)
[![GitHub release](https://img.shields.io/github/release/Kajkac/ZTE-MC-Home-assistant-repo.svg)](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/releases/)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)

[![CodeQL](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/workflows/CodeQL/badge.svg)](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/codeql.yaml)

![example workflow](https://github.com/github/docs/actions/workflows/main.yml/badge.svg)
![Validate with hassfest](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/workflows/Validate/badge.svg?branch=master)

![GitHub contributors](https://img.shields.io/github/contributors/Kajkac/ZTE-MC-Home-assistant-repo)
![Maintenance](https://img.shields.io/maintenance/yes/2025)
![GitHub commit activity](https://img.shields.io/github/commit-activity/y/Kajkac/ZTE-MC-Home-assistant-repo)
![GitHub commits since tagged version](https://img.shields.io/github/commits-since/juacas/zte_tracker/v1.0.0)
![GitHub last commit](https://img.shields.io/github/last-commit/Kajkac/ZTE-MC-Home-assistant-repo)
![Codecov branch](https://img.shields.io/codecov/c/github/Kajkac/ZTE-MC-Home-assistant-repo/master)
![installation_badge](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.zte_router.total)

# ZTE Router Integration for Home Assistant
Component to integrate some ZTE routers as a device trackers in home assistant.


## Installation

### Manual Installation

1. Download the [zte-router](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/releases/latest/download/zte_router.zip)
2. Place the files of the .zip in your `root directory of homeassistant` (That should only effectivly place files into /custom_components/zte/router)
3. Restart Homeassistant
4. Search in "integration" for the ZTE_Router integration and add it to Homeassistant
5. Enter the Router IP, password and select the model you have and wait for the integration to install all the device sensors.

### Installation with HACS

1. Or `HACS` > `Integrations` > `⋮` > `Custom Repositories`
2. `Repository`: paste the url of this repo
3. `Category`: Integration
4. Click `Add`
5. Close `Custom Repositories` modal
6. Click `+ EXPLORE & DOWNLOAD REPOSITORIES`
7. Search for `ZTE router`
8. Click `Download`
9. Restart _Home Assistant_
    

###  Configuration

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


## Bugs: 

1. Username currently not supported
2. Errors in Home assistant log - They are for now present until i polish the addon 
2. Various errors in sensors etc. - This integration is classified as beta right now but can be tested by anyone. 
4. Any suggestion you have please open the issues tab
5. I will push new builds as soon i will have more time. Make sure you "star" this integration. 
6. If u wanna donate for beer let me know :P 

## Contributors

If u have any sugestion or you are doing pull requests and adding new features, increment version number by 1 in manifest.json, so that github automation automaticly create a new release.
