<div align="center">

# 🛰️ ZTE Router Integration for Home Assistant

**Sensors, diagnostics, and control for ZTE 5G routers — SMS, device tracking, data usage, and more.**

[![GitHub release](https://img.shields.io/github/release/Kajkac/ZTE-MC-Home-assistant-repo.svg)](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/releases/)
[![HACS Default](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/github/license/Kajkac/ZTE-MC-Home-assistant-repo)](LICENSE)
[![Installs](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=active%20installs&suffix=%20&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.zte_router.total)](https://analytics.home-assistant.io/custom_integrations.json)

[Install via HACS](#-installation) · [Supported devices](#-supported-devices) · [Beta versions](#-beta-versions) · [Services](#-services) · [Logging](#-logging) · [Known issues](#-known-issues)

</div>

---

> [!NOTE]
> This integration is in **beta**. It's stable enough for daily use and actively maintained, but expect some rough edges — see [Known Issues](#-known-issues) below.

## 🚀 Overview

A custom Home Assistant integration for ZTE 5G routers/CPEs — MC-series and G5-series. It polls your router locally (no cloud, no external services) for signal, connectivity, and SMS data, and exposes controls back to it.

### ✨ Features

- 📶 Signal, connectivity, and diagnostic sensors — auto-discovered per model
- 📱 Wi-Fi and LAN client tracking (device tracker)
- 📊 FLUX usage monitoring — TX/RX rates, data plan limits, usage alerts (newer firmware)
- 💬 SMS inbox access, diagnostics, and sending (predefined or custom, via service)
- 🖱️ Buttons and switches for reboot, Wi-Fi toggle, SMS actions, and more
- ⚙️ Guided config flow — pick your model, enter IP/password, done
- 🧩 Works with or without a router username, depending on model

## 📋 Supported Devices

| Model family | Config flow selection | Username required? |
| --- | :---: | :---: |
| ZTE MC801 / **MC801A** | `MC801` | No |
| ZTE MC888 / **MC888A** | `MC888` | Yes |
| ZTE MC889 / **MC889A** | `MC889` | Yes |
| ZTE **G5 Ultra** and related G5-series units (e.g. MC8512, MC8830 profile) | `G5 Ultra` | No |

Similar/rebadged variants of these chassis families are generally expected to work. If your model isn't listed and something doesn't work, please [open an issue](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/issues) with your firmware version.

## 📦 Installation

### Via HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Kajkac&repository=ZTE-MC-Home-assistant-repo&category=integration)

<details>
<summary>Manual HACS steps</summary>

1. `HACS` → `Integrations` → `⋮` → `Custom Repositories`
2. **Repository:** paste this repo's URL
3. **Category:** Integration
4. Click `Add`, close the dialog
5. `+ EXPLORE & DOWNLOAD REPOSITORIES` → search `ZTE router` → `Download`
6. Restart Home Assistant
7. Add the integration:

   [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=zte_router)

8. Select your model, enter the router's IP and password, and wait for setup to finish.

</details>

### Manual install

<details>
<summary>Steps</summary>

1. Download the latest [`zte_router.zip`](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/releases/latest/download/zte_router.zip)
2. Extract it into your Home Assistant config root (it should land in `/config/custom_components/zte_router`)
3. Restart Home Assistant
4. `Settings` → `Devices & Services` → add **ZTE Router**
5. Select your model, enter the router's IP and password, and wait for setup to finish

</details>

![Screenshot](https://raw.githubusercontent.com/Kajkac/ZTE-MC-Home-assistant-repo/main/zte.png)

## 🧪 Beta Versions

New features land in **beta releases first** — versions tagged like `1.0.56b1`, `1.0.56b2`, etc. — before being promoted to a stable release. This is where things like new sensors, switches, or services get real-world testing before everyone gets them by default.

> [!IMPORTANT]
> Beta versions are for **testing, not production**. They may contain bugs, incomplete features, or ubus/API calls that haven't been verified across all router models yet. Don't rely on a beta build for anything critical (e.g. don't test firewall/NAT changes on a router you can't physically access if something goes wrong).

**What's typically still in beta:**

- Newly-added G5 Ultra controls (band/cell locking, network mode, USSD, router-level settings like firewall/NAT/UPnP/DMZ/DNS/DDNS/APN) — these were reverse-engineered from ubus calls and validated on specific hardware, but may behave differently on other G5-series firmware
- Anything explicitly marked `(beta)` in its service/entity name or description

**How to opt in:**

<details>
<summary>Install a beta build from HACS</summary>

1. `HACS` → `Integrations` → `ZTE Router` → `⋮` → `Redownload`
2. Toggle **"Show beta versions"** and pick the latest `bN` build
3. Restart Home Assistant

</details>

Found something broken in a beta? [Open an issue](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/issues) with your router model, firmware version, and what you tried — that's exactly what the beta cycle is for.

## 🔧 Services

### `zte_router.send_custom_sms`

Send an SMS to any phone number with any message, independent of the phone numbers configured during setup — useful from your own automations/scripts.

| Field | Required | Description |
| --- | :---: | --- |
| `message` | ✅ | Text to send |
| `phone_number` / `phone` | ✅ (one of) | Destination number |
| `entry_id` | — | Only needed with multiple ZTE Router entries |

```yaml
action: zte_router.send_custom_sms
data:
  phone_number: "+15555550100"
  message: "Garage door left open for 10 minutes"
```

Works on every supported model (MC801, MC888, MC889, G5 Ultra) — it reuses the same underlying send-SMS command as the built-in "Send SMS" buttons, so it's purely additive and doesn't touch your existing automations.

### `zte_router.ubus_call`

Advanced/debug service, **G5 Ultra only** — invokes an arbitrary ubus module/method directly, for exploring endpoints not yet exposed as sensors.

| Field | Required | Description |
| --- | :---: | --- |
| `module` | ✅ | ubus object name |
| `method` | ✅ | Method to call |
| `params` | — | JSON object of call parameters |
| `entry_id` | — | Only needed with multiple entries |

Not needed for normal use.

## 📝 Logging

The integration logs through Home Assistant and writes no log files of its own, so `logger:` and the **Enable debug logging** button on the integration page control everything it emits.

Routine polling is logged at `debug`; `info` is reserved for actions you triggered (sending an SMS, rebooting, toggling a switch). To go quieter still, or to trace requests for a bug report:

```yaml
logger:
  logs:
    custom_components.zte_router: warning  # or: debug
```

> [!NOTE]
> Versions up to 1.0.55 wrote their own `mc.log` / `ultra.log` next to the integration, at `debug` level and with broken rotation ([#40](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/issues/40)). They're no longer created, but existing files aren't removed — delete any leftovers from `config/custom_components/zte_router/`.

Session tokens, auth hashes, phone numbers and SMS bodies are redacted, but `debug` still contains your router's IP and full API responses — skim before pasting into an issue.

## 🐞 Known Issues

- Some sensors may briefly show `unknown` until the next refresh
- SMS parsing can behave differently across router models/firmware
- Found something else? [Open an issue](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/issues) — reports drive what gets fixed next

## 🤝 Contributing

Pull requests welcome. If you're adding a feature or fix, bump the version in `manifest.json` — merges to `main` automatically cut a GitHub release for that version.

[![Hassfest](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/hassfest.yml/badge.svg)](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/hassfest.yml)
[![HACS Validation](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/validate.yml/badge.svg)](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/validate.yml)
[![CodeQL](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/codeql.yml/badge.svg)](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo/actions/workflows/codeql.yml)
![Last Commit](https://img.shields.io/github/last-commit/Kajkac/ZTE-MC-Home-assistant-repo)

### 🙏 Thanks

Huge thanks to **[@rosenrot00](https://github.com/rosenrot00)** for helping rewrite major portions of the code and improving overall quality.

---

<div align="center">

If this integration is useful to you, consider ⭐ starring the repo — it helps others find it.

</div>
