[![Whiskey or beer :)](https://img.buymeacoffee.com/button-api/?text=Whiskey or beer :)&emoji=🥤&slug=kajkac&button_colour=5F7FFF&font_colour=ffffff&font_family=Poppins&outline_colour=000000&coffee_colour=FFDD00)](https://www.buymeacoffee.com/kajkac)


# ZTE Home assistant addon
**ZTE Home assistant addon**

### Option 1: [HACS](https://hacs.xyz/)

1. Or `HACS` > `Integrations` > `⋮` > `Custom Repositories`
2. `Repository`: paste the url of this repo
3. `Category`: Integration
4. Click `Add`
5. Close `Custom Repositories` modal
6. Click `+ EXPLORE & DOWNLOAD REPOSITORIES`
7. Search for `ZTE router`
8. Click `Download`
9. Restart _Home Assistant_

### Option 2: Manual copy

Copy the `custom_components/zte_router` of this repo into the path `/config/custom_components/zte_router` of your HA installation.

Restart Home Assistant go to Settings -> integrations -> Add integration 
Find integration ZTE Router 

Enter the Router IP, password and select the model you have and wait for the integration to install all the device sensors.

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
2. Errors in Home assistant log are for now present until i polish the addon 
2. There are errors for sure but whoever wanna test it let me know
4. Any sugestion you have please open the bug 
5. I will push new builds as soon i will have more time
6. If u wanna donate for beer let me know :P 

## HACS installation

When i polish the addon i will try to push it to HACS, but for now its only manual
