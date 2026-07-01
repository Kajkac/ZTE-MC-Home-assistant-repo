# ZTE Router Integration for Home Assistant

[![GitHub release](https://img.shields.io/github/release/Kajkac/ZTE-MC-Home-assistant-repo.svg)](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/releases/)
[![HACS Default](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
[![HACS Beta](https://img.shields.io/badge/HACS-Beta-blue.svg)](https://hacs.xyz/)
![GitHub License](https://img.shields.io/github/license/Kajkac/ZTE-MC-Home-assistant-repo)
![GitHub Stars](https://img.shields.io/github/stars/Kajkac/ZTE-MC-Home-assistant-repo)

![Validate with Hassfest](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/hassfest.yml/badge.svg)
![Validate with HACS](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/validate.yml/badge.svg)
![CodeQL](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/codeql.yml/badge.svg)
![Main Build](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/main.yml/badge.svg)

![Contributors](https://img.shields.io/github/contributors/Kajkac/ZTE-MC-Home-assistant-repo)
![Maintenance](https://img.shields.io/maintenance/yes/2025)
![Last Commit](https://img.shields.io/github/last-commit/Kajkac/ZTE-MC-Home-assistant-repo)
![Commit Activity](https://img.shields.io/github/commit-activity/y/Kajkac/ZTE-MC-Home-assistant-repo)
![Installation Count](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.zte_router.total)

# ZTE Router Integration for Home Assistant
Component to integrate some ZTE routers as a device tracker in Home Assistant. 
This repository contains the ZTE Router custom integration and an add-on to deploy it in Home Assistant. The custom integration is located in the `custom_components/zte_router` directory.

## 🚀 Overview

This is a custom Home Assistant integration for several ZTE 5G routers. It adds full sensor tracking, diagnostics, and control over supported devices.

### ✅ Features

- Support for **MC801A, MC889, MC888, MC889A, MC888A**, and similar models with or without username
- Automatically discovers devices and sensors
- Wi-Fi and LAN client tracking
- FLUX usage monitoring (TX/RX rates, data limit, usage alerts) - for newer versions of routers
- SMS inbox access and diagnostics + sending predefined sms
- Auto-config flow setup
- Multiple sensor categories and diagnostic grouping

> **Note:** This integration is in **beta**. It is stable enough for testing and general use, but expect some features to evolve.

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

## 🧪 Beta Features

To install beta versions from HACS:

1. In HACS → Integrations → ZTE Router → `⋮` → Redownload
2. Toggle **"Show beta versions"** or Need a different version
3. Select the latest `-b1` or `-beta.x` version
4. Restart Home Assistant


![SCreenshot](https://raw.githubusercontent.com/Kajkac/ZTE-MC-Home-assistant-repo/main/zte.png)

## 📡 Services

### `zte_router.send_custom_sms`

Send an SMS with any phone number and message, independent of the phone numbers configured during setup. Useful for calling from your own automations/scripts.

**Fields:**
- `message` (required) — the text to send.
- `phone_number` or `phone` (required, provide either one) — destination number.
- `entry_id` (optional) — only needed if you have more than one ZTE Router entry configured; omit it if you only have one.

Example, in an automation action or a script:

```yaml
action: zte_router.send_custom_sms
data:
  phone_number: "0989072702"
  message: "Garage door left open for 10 minutes"
```

Or from Developer Tools → Actions, call `zte_router.send_custom_sms` with the same fields.

This works on all supported router types (MC801, MC888, MC889, G5 Ultra) and reuses the same underlying send-SMS command as the built-in "Send SMS" buttons — it does not affect or replace your configured automations, it's just another way to trigger an SMS with content you choose at call time.

### `zte_router.ubus_call`

Advanced/debug service for G5 Ultra routers only — invokes an arbitrary ubus module/method directly (e.g. for exploring endpoints not yet exposed as sensors). Fields: `module`, `method`, optional `params` (JSON object) and `entry_id`. Not needed for normal use.

## 🐞 Known Issues

- Some sensors may occasionally show `unknown` until refreshed
- SMS parsing may behave differently between router models
- Occasional log errors (under investigation)
- Errors in Home Assistant log - They are for now present until I polish the addon
- Various errors in sensors etc. - This integration is classified as beta right now but can be tested by anyone. 
- For suggestions, please open a new issue
- I will push new builds as soon I will have more time. Make sure you "star" this integration. 

## Contributors
If u have any suggestion, or you are doing pull requests and adding new features, increment the version number by 1 in manifest.json, so that GitHub automation automatically creates a new release.

🙏 Special Thanks

Huge thanks to @rosenrot00 for helping rewrite major portions of the code and improving overall quality!
