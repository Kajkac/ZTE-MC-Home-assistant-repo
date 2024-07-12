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

Enter Router IP , password and select the model you have and waitz for integration to install all the device sensors

Bugs: 

1. Username currently not supported
2. Errors in Home assistant log are for now present until i polish the addon 
3. Any sugestion you have please open the bug 
4. If u wanna donate for beer let me know :P 

## HACS installation

When i polish the addon i will try to push it to HACS, but for now its only manual
