"""Constants for the ZTE Router integration."""

DOMAIN = "zte_tracker"
DEFAULT_USERNAME = "admin"
DEVICE_NAME = "ZTE MC Series"
MANUFACTURER = "ZTE"
MODEL = "MC Series"

# Define friendly names for the sensors
SENSOR_NAMES = {
    "wa_inner_version": "Firmware Version",
    "cr_version": "CR Version",
    "network_type": "Network Type",
    "rssi": "RSSI",
    "rscp": "RSCP",
    "rmcc": "RMCC",
    "rmnc": "RMNC",
    "enodeb_id": "eNodeB ID",
    "lte_rsrq": "LTE RSRQ",
    "lte_rsrp": "LTE RSRP",
    "Z5g_snr": "5G SNR",
    "Z5g_rsrp": "5G RSRP",
    "ZCELLINFO_band": "Cell Info Band",
    "Z5g_dlEarfcn": "5G DL EARFCN",
    "lte_ca_pcell_arfcn": "LTE CA PCell ARFCN",
    "lte_ca_pcell_band": "LTE CA PCell Band",
    "lte_ca_scell_band": "LTE CA SCell Band",
    "lte_ca_pcell_bandwidth": "LTE CA PCell Bandwidth",
    "lte_ca_scell_info": "LTE CA SCell Info",
    "lte_ca_scell_bandwidth": "LTE CA SCell Bandwidth",
    "wan_lte_ca": "WAN LTE CA",
    "lte_pci": "LTE PCI",
    "Z5g_CELL_ID": "5G Cell ID",
    "Z5g_SINR": "5G SINR",
    "cell_id": "Cell ID",
    "wan_active_band": "WAN Active Band",
    "nr5g_pci": "NR 5G PCI",
    "nr5g_action_band": "NR 5G Action Band",
    "nr5g_cell_id": "NR 5G Cell ID",
    "lte_snr": "LTE SNR",
    "ecio": "EC/IO",
    "wan_active_channel": "WAN Active Channel",
    "nr5g_action_channel": "NR 5G Action Channel",
    "ngbr_cell_info": "Neighbor Cell Info",
    "monthly_tx_bytes": "Monthly TX Bytes",
    "monthly_rx_bytes": "Monthly RX Bytes",
    "wan_ipaddr": "WAN IP Address",
    "wan_apn": "WAN APN",
    "pm_sensor_mdm": "PM Sensor MDM",
    "pm_modem_5g": "PM Modem 5G",
    "dns_mode": "DNS Mode",
    "prefer_dns_manual": "Preferred DNS Manual",
    "standby_dns_manual": "Standby DNS Manual",
    "static_wan_ipaddr": "Static WAN IP Address",
    "opms_wan_mode": "OPMS WAN Mode",
    "opms_wan_auto_mode": "OPMS WAN Auto Mode",
    "ppp_status": "PPP Status",
    "loginfo": "Log Info",
    "realtime_time": "Realtime Time",
    "signalbar": "Signal Bar",
    "modem_main_state": "Modem Main State",
    "pin_status": "PIN Status",
    "new_version_state": "New Version State",
    "current_upgrade_state": "Current Upgrade State",
    "is_mandatory": "Is Mandatory",
    "wifi_dfs_status": "WiFi DFS Status",
    "battery_value": "Battery Value",
    "ppp_dial_conn_fail_counter": "PPP Dial Conn Fail Counter",
    "wifi_chip1_ssid1_auth_mode": "WiFi Chip1 SSID1 Auth Mode",
    "wifi_chip2_ssid1_auth_mode": "WiFi Chip2 SSID1 Auth Mode",
    "network_provider": "Network Provider",
    "simcard_roam": "Simcard Roam",
    "spn_name_data": "SPN Name Data",
    "spn_b1_flag": "SPN B1 Flag",
    "spn_b2_flag": "SPN B2 Flag",
    "wifi_onoff_state": "WiFi On/Off State",
    "wifi_chip1_ssid1_ssid": "WiFi Chip1 SSID1 SSID",
    "wifi_chip2_ssid1_ssid": "WiFi Chip2 SSID1 SSID",
    "pppoe_status": "PPPoE Status",
    "dhcp_wan_status": "DHCP WAN Status",
    "static_wan_status": "Static WAN Status",
    "mdm_mcc": "MDM MCC",
    "mdm_mnc": "MDM MNC",
    "EX_SSID1": "EX SSID1",
    "sta_ip_status": "STA IP Status",
    "EX_wifi_profile": "EX WiFi Profile",
    "m_ssid_enable": "M SSID Enable",
    "RadioOff": "Radio Off",
    "wifi_chip1_ssid1_access_sta_num": "WiFi Chip1 SSID1 Access STA Num",
    "wifi_chip2_ssid1_access_sta_num": "WiFi Chip2 SSID1 Access STA Num",
    "lan_ipaddr": "LAN IP Address",
    "station_mac": "Station MAC",
    "wifi_access_sta_num": "WiFi Access STA Num",
    "battery_charging": "Battery Charging",
    "battery_vol_percent": "Battery Vol Percent",
    "battery_pers": "Battery Percent",
    "realtime_tx_bytes": "Realtime TX Bytes",
    "realtime_rx_bytes": "Realtime RX Bytes",
    "realtime_tx_thrpt": "Realtime TX Throughput",
    "realtime_rx_thrpt": "Realtime RX Throughput",
    "monthly_time": "Monthly Time",
    "date_month": "Date Month",
    "data_volume_limit_switch": "Data Volume Limit Switch",
    "data_volume_limit_size": "Data Volume Limit Size",
    "data_volume_alert_percent": "Data Volume Alert Percent",
    "data_volume_limit_unit": "Data Volume Limit Unit",
    "roam_setting_option": "Roam Setting Option",
    "upg_roam_switch": "Upgrade Roam Switch",
    "ssid": "SSID",
    "wifi_enable": "WiFi Enable",
    "wifi_5g_enable": "WiFi 5G Enable",
    "check_web_conflict": "Check Web Conflict",
    "dial_mode": "Dial Mode",
    "privacy_read_flag": "Privacy Read Flag",
    "is_night_mode": "Is Night Mode",
    "vpn_conn_status": "VPN Connection Status",
    "wan_connect_status": "WAN Connection Status",
    "sms_received_flag": "SMS Received Flag",
    "sts_received_flag": "STS Received Flag",
    "sms_unread_num": "SMS Unread Number",
    "wifi_chip1_ssid2_access_sta_num": "WiFi Chip1 SSID2 Access STA Num",
    "wifi_chip2_ssid2_access_sta_num": "WiFi Chip2 SSID2 Access STA Num",
    "static_wan_ipaddr": "Static WAN IP Address",
    "dns_mode": "DNS Mode",
    "prefer_dns_manual": "Preferred DNS Manual",
    "standby_dns_manual": "Standby DNS Manual",
    "signalbar": "Signal Bar",
    "ppp_status": "PPP Status",
    # New SMS related sensors
    "sms_nv_total": "SMS Capacity device",
    "sms_capacity_left": "SMS Capacity left",
    "sms_sim_total": "SMS Capacity SIM",
    "sms_nv_rev_total": "Recieved SMS-s",
    "sms_nv_send_total": "Sent SMS-s",
    "sms_nv_draftbox_total": "SMS NV Draftbox Total",
    "sms_sim_received_total": "SMS SIM Received Total",
    "sms_sim_sent_total": "SMS SIM Sent Total",
    "sms_sim_draftbox_total": "SMS SIM Draftbox Total"
}

# Define which sensors should be included in the Diagnostics section
DIAGNOSTICS_SENSORS = {
    "sms_capacity_left",
    "last_sms",
    "signalbar",
    "connected_bands",
    # Add other sensors you want to include in Diagnostics
}

# Define units of measurement for the sensors
UNITS = {
    "wa_inner_version": None,
    "cr_version": None,
    "network_type": None,
    "rssi": "dBm",
    "rscp": "dBm",
    "rmcc": None,
    "rmnc": None,
    "enodeb_id": None,
    "lte_rsrq": "dB",
    "lte_rsrp": "dBm",
    "Z5g_snr": "dB",
    "Z5g_rsrp": "dBm",
    "ZCELLINFO_band": None,
    "Z5g_dlEarfcn": None,
    "lte_ca_pcell_arfcn": None,
    "lte_ca_pcell_band": None,
    "lte_ca_scell_band": None,
    "lte_ca_pcell_bandwidth": "MHz",
    "lte_ca_scell_info": None,
    "lte_ca_scell_bandwidth": "MHz",
    "wan_lte_ca": None,
    "lte_pci": None,
    "Z5g_CELL_ID": None,
    "Z5g_SINR": "dB",
    "cell_id": None,
    "wan_active_band": None,
    "nr5g_pci": None,
    "nr5g_action_band": None,
    "nr5g_cell_id": None,
    "lte_snr": "dB",
    "ecio": "dB",
    "wan_active_channel": None,
    "nr5g_action_channel": None,
    "ngbr_cell_info": None,
    "monthly_tx_bytes": "B",
    "monthly_rx_bytes": "B",
    "wan_ipaddr": None,
    "wan_apn": None,
    "pm_sensor_mdm": "°C",
    "pm_modem_5g": "°C",
    "dns_mode": None,
    "prefer_dns_manual": None,
    "standby_dns_manual": None,
    "static_wan_ipaddr": None,
    "opms_wan_mode": None,
    "opms_wan_auto_mode": None,
    "ppp_status": None,
    "loginfo": None,
    "realtime_time": "seconds",
    "signalbar": None,
    "modem_main_state": None,
    "pin_status": None,
    "new_version_state": None,
    "current_upgrade_state": None,
    "is_mandatory": None,
    "wifi_dfs_status": None,
    "battery_value": "%",
    "ppp_dial_conn_fail_counter": None,
    "wifi_chip1_ssid1_auth_mode": None,
    "wifi_chip2_ssid1_auth_mode": None,
    "network_provider": None,
    "simcard_roam": None,
    "spn_name_data": None,
    "spn_b1_flag": None,
    "spn_b2_flag": None,
    "wifi_onoff_state": None,
    "wifi_chip1_ssid1_ssid": None,
    "wifi_chip2_ssid1_ssid": None,
    "pppoe_status": None,
    "dhcp_wan_status": None,
    "static_wan_status": None,
    "mdm_mcc": None,
    "mdm_mnc": None,
    "EX_SSID1": None,
    "sta_ip_status": None,
    "EX_wifi_profile": None,
    "m_ssid_enable": None,
    "RadioOff": None,
    "wifi_chip1_ssid1_access_sta_num": None,
    "wifi_chip2_ssid1_access_sta_num": None,
    "lan_ipaddr": None,
    "station_mac": None,
    "wifi_access_sta_num": None,
    "battery_charging": None,
    "battery_vol_percent": "%",
    "battery_pers": "%",
    "realtime_tx_bytes": "bytes",
    "realtime_rx_bytes": "bytes",
    "realtime_tx_thrpt": "bps",
    "realtime_rx_thrpt": "bps",
    "monthly_time": "seconds",
    "date_month": None,
    "data_volume_limit_switch": None,
    "data_volume_limit_size": None,
    "data_volume_alert_percent": "%",
    "data_volume_limit_unit": None,
    "roam_setting_option": None,
    "upg_roam_switch": None,
    "ssid": None,
    "wifi_enable": None,
    "wifi_5g_enable": None,
    "check_web_conflict": None,
    "dial_mode": None,
    "privacy_read_flag": None,
    "is_night_mode": None,
    "vpn_conn_status": None,
    "wan_connect_status": None,
    "sms_received_flag": None,
    "sts_received_flag": None,
    "sms_unread_num": None,
    "wifi_chip1_ssid2_access_sta_num": None,
    "wifi_chip2_ssid2_access_sta_num": None,
    "static_wan_ipaddr": None,
    "dns_mode": None,
    "prefer_dns_manual": None,
    "standby_dns_manual": None,
    "signalbar": None,
    "ppp_status": None,
    "sms_nv_total": None,
    "sms_sim_total": None,
    "sms_nv_received_total": None,
    "sms_nv_sent_total": None,
    "sms_nv_draftbox_total": None,
    "sms_sim_received_total": None,
    "sms_sim_sent_total": None,
    "sms_sim_draftbox_total": None
}

# Define which sensors should be disabled by default for each router type
DISABLED_SENSORS_MC889 = {
    "concat_sms_received": True,
    "concat_sms_total": True,
    "content": True,
    "cr_version": True,
    "date": True,
    "id": True,
    "is_mandatory": True,
    "is_night_mode": True,
    "lte_ca_scell_arfcn": True,
    "lte_earfcn_lock": True,
    "lte_pci_lock": True,
    "sms_nv_draftbox_total": True,
    "sms_sim_total": True,
    "sms_class": True,
    "sms_dev_unread_num": True,
    "sms_sim_rev_total": True,
    "sms_sim_send_total": True,
    "sms_sim_unread_num": True,
    "sms_nv_received_total":True,
    "sms_received_flag":True,
    "tag": True,
    "wifi_5g_enable": True,
    "wifi_access_sta_num": True,
    "wifi_chip1_ssid1_access_sta_num": True,
    "wifi_chip1_ssid1_auth_mode": True,
    "wifi_chip1_ssid1_ssid": True,
    "wifi_chip1_ssid2_access_sta_num": True,
    "wifi_chip2_ssid1_access_sta_num": True,
    "wifi_chip2_ssid1_auth_mode": True,
    "wifi_chip2_ssid1_auth_mode": True,
    "wifi_chip2_ssid1_ssid": True,
    "wifi_chip2_ssid2_access_sta_num": True,
    "wifi_dfs_status": True,
    "wifi_enable": True,
    "wifi_on_off_state": True,
    "m_ssid_enable": True,
    "ex_wifi_profile": True,
    "ex_ssid1": True,
    "draft_group_id": True,
    #MC889
    "5g_cell_id": True,
    "5g_dl_earfcn": True,
    "cell_info_band": True,
    "data_volume_limit_size": True,
    "ex_ssid1": True,
    "ex_wifi_profile": True,
    "nr_5g_cell_id": True,
    "preferred_dns_manual": True,
    "ssid": True,
    "sta_ip_status": True,
    "standby_dns_manual": True,
    "static_wan_ip_address": True,
    "static_wan_status": True,
    "station_mac": True,
    "sts_received_flag": True,
    "wifi_on_off_state": True,
}

DISABLED_SENSORS_MC888 = {
    "concat_sms_received": True,
    "concat_sms_total": True,
    "content": True,
    "cr_version": True,
    "date": True,
    "id": True,
    "is_mandatory": True,
    "is_night_mode": True,
    "lte_ca_scell_arfcn": True,
    "lte_earfcn_lock": True,
    "lte_pci_lock": True,
    "sms_nv_draftbox_total": True,
    "sms_sim_total": True,
    "sms_class": True,
    "sms_dev_unread_num": True,
    "sms_sim_rev_total": True,
    "sms_sim_send_total": True,
    "sms_sim_unread_num": True,
    "sms_nv_received_total":True,
    "sms_received_flag":True,
    "tag": True,
}

DISABLED_SENSORS_MC801A = {
    "concat_sms_received": True,
    "concat_sms_total": True,
    "content": True,
    "cr_version": True,
    "date": True,
    "id": True,
    "is_mandatory": True,
    "is_night_mode": True,
    "lte_ca_scell_arfcn": True,
    "lte_earfcn_lock": True,
    "lte_pci_lock": True,
    "sms_nv_draftbox_total": True,
    "sms_sim_total": True,
    "sms_class": True,
    "sms_dev_unread_num": True,
    "sms_sim_rev_total": True,
    "sms_sim_send_total": True,
    "sms_sim_unread_num": True,
    "sms_nv_received_total":True,
    "sms_received_flag":True,
    "tag": True,
}
