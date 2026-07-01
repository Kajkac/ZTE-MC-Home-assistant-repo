import gzip
import hashlib
import json
import logging
import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
import urllib3
from logging.handlers import TimedRotatingFileHandler
from requests.exceptions import RequestException

ZERO_TOKEN = "0" * 32

LOGGER = logging.getLogger("homeassistant.components.zte_router.g5_ultra")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOG_FILE = os.path.join(os.path.dirname(__file__), "ultra.log")


def _setup_file_logger():
    if getattr(_setup_file_logger, "configured", False):
        return
    LOGGER.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler = TimedRotatingFileHandler(
        LOG_FILE,
        when="midnight",
        interval=1,
        backupCount=1,
        encoding="utf-8",
        utc=False,
    )
    handler.setFormatter(formatter)

    def _compress_old_logs(handler):
        log_dir = os.path.dirname(handler.baseFilename)
        for filename in os.listdir(log_dir):
            if filename.startswith("ultra.log.") and not filename.endswith(".gz"):
                full_path = os.path.join(log_dir, filename)
                gz_path = f"{full_path}.gz"
                if not os.path.exists(gz_path):
                    with open(full_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    os.remove(full_path)

    handler.rotator = lambda source, dest: shutil.copy2(source, dest)
    handler.namer = lambda name: name
    LOGGER.addHandler(handler)

    original_doRollover = handler.doRollover

    def rollover_with_compress(*args, **kwargs):
        original_doRollover(*args, **kwargs)
        _compress_old_logs(handler)

    handler.doRollover = rollover_with_compress  # type: ignore
    _setup_file_logger.configured = True


_setup_file_logger()

CALLS = [
    ("router_status", "zwrt_router.api", "router_get_status", {}),
    ("user_list_counts", "zwrt_router.api", "router_get_user_list_num", {}),
    ("sim_info", "zwrt_zte_mdm.api", "get_sim_info", {}),
    ("device_info", "zwrt_mc.device.manager", "get_device_info", {"deviceInfoList": ["deviceinfo"]}),
    ("wwan_iface", "zwrt_data", "get_wwaniface", {"source_module": "web", "cid": 1}),
    ("wifi_ifaces", "zwrt_wlan", "iface_report", {}),
    ("wifi_global", "zwrt_wireless", "zte_mbb", {}),
    ("common_config", "uci", "get", {"config": "zwrt_common_info", "section": "common_config"}),
    ("firewall_config", "zwrt_router", "firewall", {}),
    ("dhcp_config", "zwrt_router", "dhcp", {}),
    ("network_config", "zwrt_router", "network", {}),
    ("syslog_config", "zwrt_router", "syslog", {}),
    ("sms_settings", "zwrt_wms", "zte_wms_get_parameter", {}),
    ("signal_info", "zte_nwinfo_api", "nwinfo_get_netinfo", {}),
    ("flux_monthlimit", "zwrt_data", "get_wwandst_monthlimit", {"source_module": "web", "cid": 1}),
    ("flux_stats", "zwrt_data", "get_wwandst", {"source_module": "web", "cid": 1, "type": 4}),
    ("flux_clearday", "zwrt_data", "get_wwandst_clearday", {"source_module": "web", "cid": 1}),
    ("night_mode", "zwrt_led", "get_nightmode_state", {}),
    ("wifi_status", "zwrt_wlan", "report", {}),
    ("fota_status", "zwrt_zte_dm", "dm_update", {}),
]

DYNAMIC_SECTIONS = (
    ("router_status", ""),
    ("wwan_iface", ""),
    ("signal_info", ""),
    ("sim_info", ""),
    ("night_mode", "night_mode_"),
    ("wifi_status", "wifi_status_"),
    ("fota_status", "fota_"),
    ("user_list_counts", "user_count_"),
)

SUMMARY_MAP = {
    "wan_ipv4_address": "wan_ipaddr",
    "wan_ipv6_address": "ipv6_wan_ipaddr",
    "gateway_ip_address": "lan_ipaddr",
    "software_version": "wa_inner_version",
    "hardware_version": "hardware_version",
    "imei": "imei",
    "imsi": "imsi",
    "sim_card_number": "sim_card_number",
    "sms_center": "sms_center",
    "model_name": "model_name",
}


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def get_current_time_string() -> str:
    now = datetime.now(timezone.utc).astimezone()
    tz_offset = int(now.utcoffset().total_seconds() / 3600)
    parts = [
        str(now.year)[2:],
        f"{now.month:02d}",
        f"{now.day:02d}",
        f"{now.hour:02d}",
        f"{now.minute:02d}",
        f"{now.second:02d}",
        f"{tz_offset:+d}",
    ]
    return ";".join(parts) + ";"


def encode_message_hex(message: str) -> str:
    return "".join(f"{ord(ch):04X}" for ch in message)


def decode_message_hex(hex_string: Optional[str]) -> str:
    if not hex_string:
        return ""
    try:
        raw = bytes.fromhex(hex_string)
    except ValueError:
        return hex_string
    for encoding in ("utf-16-be", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_router_timestamp(timestamp: str) -> str:
    if not timestamp:
        return timestamp
    parts = timestamp.split(",")
    if len(parts) < 7:
        return timestamp
    try:
        year = 2000 + int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        hour = int(parts[3])
        minute = int(parts[4])
        second = int(parts[5])
        offset_hours = int(parts[6])
    except ValueError:
        return timestamp
    tz = timezone(timedelta(hours=offset_hours))
    dt_value = datetime(year, month, day, hour, minute, second, tzinfo=tz)
    return dt_value.isoformat()


def normalize_mem_store_arg(value: Any) -> int:
    if value is None:
        return 1
    if isinstance(value, int):
        return value
    value_str = str(value).strip().lower()
    if value_str.isdigit():
        return int(value_str)
    aliases = {"nv": 1, "device": 1, "flash": 1, "sim": 0, "card": 0}
    return aliases.get(value_str, 1)


def describe_mem_store(value: Any) -> str:
    if value is None:
        return "unknown"
    value_str = str(value).lower()
    labels = {"0": "sim", "1": "device", "2": "draft"}
    return labels.get(value_str, value_str)


def format_sms_record(record: Dict[str, Any]) -> Dict[str, Any]:
    record = record or {}
    body = record.get("content", "")
    decoded = decode_message_hex(body)
    timestamp = parse_router_timestamp(record.get("date", ""))
    mem_store = record.get("mem_store")
    return {
        "id": record.get("id"),
        "number": record.get("number"),
        "content": decoded,
        "raw_content": body,
        "timestamp": timestamp,
        "date": record.get("date"),
        "raw_date": record.get("date"),
        "storage": describe_mem_store(mem_store),
        "tag": record.get("tag"),
        "is_new": str(record.get("tag", "")) == "0",
        "group_id": record.get("draft_group_id"),
        "mem_store": mem_store,
    }


def extract_device_values(device_info: Any) -> Dict[str, Any]:
    if isinstance(device_info, dict):
        if "values" in device_info and isinstance(device_info["values"], dict):
            return device_info["values"]
        device_list = device_info.get("deviceInfoList")
        if isinstance(device_list, dict):
            if "deviceinfo" in device_list and isinstance(device_list["deviceinfo"], dict):
                return device_list["deviceinfo"]
            return device_list
        return device_info
    if isinstance(device_info, list):
        for entry in device_info:
            if isinstance(entry, dict):
                values = entry.get("values")
                if isinstance(values, dict):
                    return values
                result = entry.get("result")
                if isinstance(result, dict):
                    inner = result.get("values")
                    if isinstance(inner, dict):
                        return inner
    return {}


COMMON_VALUE_KEYS = {
    "manufacturer",
    "hardware_version",
    "wa_inner_version",
    "wa_module_version",
    "model_name",
    "GUI_version",
    "Boot_version",
    "integrate_version",
    "wireless_name",
    "device_alias_name",
}


def extract_values(section: Any) -> Dict[str, Any]:
    if isinstance(section, dict):
        values = section.get("values")
        if isinstance(values, dict):
            return values
        if any(key in section for key in COMMON_VALUE_KEYS):
            return section
        for value in section.values():
            nested = extract_values(value)
            if nested:
                return nested
    elif isinstance(section, list):
        for item in section:
            nested = extract_values(item)
            if nested:
                return nested
    return {}


class G5UltraRouterRunner:
    """HTTP client for the G5 Ultra router family."""

    def __init__(self, ip: str, password: str) -> None:
        self.ip = ip
        self.password = password
        self.session = requests.Session()
        self.scheme = "https"
        self.session.verify = False
        self._configure_urls()
        self.session_token: Optional[str] = None

    def _configure_urls(self) -> None:
        self.base_url = f"{self.scheme}://{self.ip}"
        self.referer = f"{self.base_url}/index.html"
        self.router_url = f"{self.base_url}/ubus/"

    def _enable_https(self) -> bool:
        return False

    def run_commands(self, command_string: str, phone: Optional[str] = None, message: Optional[str] = None) -> str:
        commands = [cmd.strip() for cmd in str(command_string).split(",") if cmd.strip()]
        if not commands:
            return "{}"

        results: Dict[str, Any] = {}
        gather_cache: Optional[Dict[str, Any]] = None

        for command in commands:
            try:
                cmd_id = int(command)
            except ValueError:
                results[command] = {"error": f"Invalid command: {command}"}
                continue

            try:
                LOGGER.info("G5 Ultra executing command %s", cmd_id)
                if cmd_id in (3, 7, 16) and gather_cache is None:
                    gather_cache = self.gather_all_data()

                if cmd_id == 3 and gather_cache is not None:
                    results[str(cmd_id)] = self._build_dynamic_section(gather_cache)
                elif cmd_id == 7 and gather_cache is not None:
                    results[str(cmd_id)] = self._build_status_section(gather_cache)
                elif cmd_id == 16 and gather_cache is not None:
                    results[str(cmd_id)] = self._build_client_section(gather_cache)
                elif cmd_id == 4:
                    results[str(cmd_id)] = self.reboot_router()
                elif cmd_id == 5:
                    results[str(cmd_id)] = self.delete_all_sms()
                elif cmd_id == 6:
                    results[str(cmd_id)] = self.fetch_last_sms()
                elif cmd_id == 8:
                    if not phone or not message:
                        results[str(cmd_id)] = {"error": "Phone number or message missing"}
                    else:
                        results[str(cmd_id)] = self.send_sms(phone, message)
                else:
                    results[str(cmd_id)] = {"error": f"G5 Ultra does not support command {cmd_id}"}
                LOGGER.debug("Command %s result preview: %s", cmd_id, str(results[str(cmd_id)])[:500])
            except Exception as exc:
                LOGGER.error("Failed to execute G5 Ultra command %s: %s", command, exc)
                results[str(cmd_id)] = {"error": str(exc)}

        return json.dumps(results)

    def call_module_method(
        self,
        module: str,
        func: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Expose direct ubus method invocation for advanced integrations."""
        token = self._ensure_token()
        payload = params or {}
        response = self._ubus_call(module, func, payload, token)
        safe = self._safe_result(response)
        return {
            "module": module,
            "method": func,
            "params": payload,
            "result": safe,
            "raw": response,
        }

    def _ensure_token(self) -> str:
        if self.session_token:
            return self.session_token
        LOGGER.debug("Requesting login salt (web_login_info)")
        info = self._ubus_call("zwrt_web", "web_login_info", {}, ZERO_TOKEN)
        salt = self._safe_result(info).get("zte_web_sault")
        if not salt:
            raise RuntimeError("Failed to obtain login salt from router")
        h1 = sha256_hex(self.password)
        h2 = sha256_hex(h1 + salt)
        LOGGER.debug("Performing login with salted hash")
        login_resp = self._ubus_call(
            "zwrt_web",
            "web_login",
            {"password": h2},
            ZERO_TOKEN,
        )
        token = self._safe_result(login_resp).get("ubus_rpc_session")
        if not token:
            raise RuntimeError("Unable to retrieve session token during login")
        self.session_token = token
        LOGGER.info("Obtained new G5 Ultra session token")
        return token

    def gather_all_data(self) -> Dict[str, Any]:
        token = self._ensure_token()
        results: Dict[str, Any] = {}
        LOGGER.info("Starting G5 Ultra gather_all_data sequence")
        sms_capacity_flat: Dict[str, Any] = {}
        for name, module, func, params in CALLS:
            try:
                response = self._ubus_call(module, func, params, token)
                results[name] = self._safe_result(response)
                LOGGER.debug("Call %s succeeded with keys: %s", name, list(results[name].keys()) if isinstance(results[name], dict) else type(results[name]))
            except Exception as exc:
                LOGGER.warning("G5 Ultra call %s failed: %s", name, exc)
                results[name] = {"error": str(exc)}

        counts = results.get("user_list_counts") or {}
        if isinstance(counts, dict):
            results["wireless_clients"] = self.collect_wireless_clients(token, counts)
            results["lan_clients"] = self.collect_lan_clients(token)
            results["offline_clients"] = self.collect_offline_clients(token, counts)

        sms_capacity_data = self._fetch_sms_capacity(token)
        if sms_capacity_data:
            sms_capacity_flat = self._flatten_sms_capacity_data(sms_capacity_data)
            results["sms_capacity_raw"] = sms_capacity_data
            results["sms_capacity_flat"] = sms_capacity_flat

        for name, getter in (
            ("upnp_status", self.get_upnp_status),
            ("dmz_status", self.get_dmz_status),
            ("nat_status", self.get_nat_status),
            ("ddns_status", self.get_ddns_status),
        ):
            try:
                results[name] = getter()
            except Exception as exc:
                LOGGER.warning("G5 Ultra call %s failed: %s", name, exc)
                results[name] = {"error": str(exc)}

        results["summary"] = self.build_gather_summary(results)
        if sms_capacity_flat:
            results["summary"].update(sms_capacity_flat)
        flux_fields = self._merge_flux_metrics(results)
        if flux_fields:
            results["summary"].update({k: v for k, v in flux_fields.items() if v is not None})
            results["flux_flat"] = flux_fields
        LOGGER.info(
            "Completed gather_all_data: summary keys=%s wireless=%s lan=%s",
            list((results.get("summary") or {}).keys()),
            len(results.get("wireless_clients") or []),
            len(results.get("lan_clients") or []),
        )
        return results

    def collect_wireless_clients(self, token: str, counts: Dict[str, Any]) -> List[Dict[str, Any]]:
        total = int(counts.get("wireless_num", 0) or 0)
        if total <= 0:
            # Some firmware revisions report wrong counters; probe one page anyway.
            resp = self._ubus_call(
                "zwrt_router.api",
                "router_wireless_access_list",
                {"start_id": 1, "end_id": 64},
                token,
            )
            data = self._safe_result(resp)
            info = data.get("wireless_access_list_info") if isinstance(data, dict) else None
            records = info if isinstance(info, list) else []
            LOGGER.debug("Collected %s wireless clients via fallback", len(records))
            return records
        page_size = 64
        start = 1
        records: List[Dict[str, Any]] = []
        while start <= total:
            end = min(start + page_size - 1, total)
            resp = self._ubus_call(
                "zwrt_router.api",
                "router_wireless_access_list",
                {"start_id": start, "end_id": end},
                token,
            )
            data = self._safe_result(resp)
            info = data.get("wireless_access_list_info") if isinstance(data, dict) else None
            if info:
                records.extend(info)
            start = end + 1
        LOGGER.debug("Collected %s wireless clients", len(records))
        return records

    def collect_lan_clients(self, token: str) -> List[Dict[str, Any]]:
        resp = self._ubus_call(
            "zwrt_router.api",
            "router_lan_access_list",
            {},
            token,
        )
        data = self._safe_result(resp)
        lan_clients = data.get("lan_access_list_info", []) if isinstance(data, dict) else []
        LOGGER.debug("Collected %s LAN clients", len(lan_clients))
        return lan_clients

    def collect_offline_clients(self, token: str, counts: Dict[str, Any]) -> List[Dict[str, Any]]:
        total = int(counts.get("offline_num", 0) or 0)
        if total <= 0:
            return []
        page_size = 64
        start = 1
        records: List[Dict[str, Any]] = []
        while start <= total:
            end = min(start + page_size - 1, total)
            resp = self._ubus_call(
                "zwrt_router.api",
                "router_offline_list",
                {"start_id": start, "end_id": end},
                token,
            )
            data = self._safe_result(resp)
            info = data.get("offline_list_info") if isinstance(data, dict) else None
            if info:
                records.extend(info)
            start = end + 1
        LOGGER.debug("Collected %s offline clients", len(records))
        return records

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        """Coerce a gather-results entry to a dict.

        _safe_result() falls back to returning the raw ubus envelope (a
        list) when a call errors out (e.g. "Object not found" on
        firmware that doesn't expose that module), so callers must not
        assume dict-shaped results just because the key is present.
        """
        return value if isinstance(value, dict) else {}

    def build_gather_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        sim_info = self._as_dict(results.get("sim_info"))
        router_status = self._as_dict(results.get("router_status"))
        wwan = self._as_dict(results.get("wwan_iface"))
        sms_settings = self._as_dict(results.get("sms_settings"))
        device_values = extract_device_values(results.get("device_info"))
        common_values = extract_values(results.get("common_config"))
        signal_info = self._as_dict(results.get("signal_info"))
        wifi_global = self._as_dict(results.get("wifi_global"))
        wifi_status = self._as_dict(results.get("wifi_status"))
        upnp_status = self._as_dict(results.get("upnp_status"))
        dmz_status = self._as_dict(results.get("dmz_status"))
        nat_status = self._as_dict(results.get("nat_status"))
        ddns_status = self._as_dict(results.get("ddns_status"))

        summary = {
            "sim_card_number": sim_info.get("msisdn"),
            "imei": device_values.get("imei"),
            "imsi": sim_info.get("sim_imsi"),
            "gateway_ip_address": router_status.get("lan_ipaddr") or f"192.168.0.1",
            "wan_ipv4_address": wwan.get("ipv4_address"),
            "wan_ipv6_address": wwan.get("ipv6_address"),
            "software_version": (
                device_values.get("wa_inner_version")
                or common_values.get("wa_inner_version")
                or router_status.get("integrate_version")
            ),
            "hardware_version": device_values.get("hardware_version") or common_values.get("hardware_version"),
            "wa_inner_version": device_values.get("wa_inner_version") or common_values.get("wa_inner_version"),
            "wa_module_version": device_values.get("wa_module_version") or common_values.get("wa_module_version"),
            "manufacturer": common_values.get("manufacturer"),
            "model_name": common_values.get("model_name"),
            "gui_version": common_values.get("GUI_version"),
            "boot_version": common_values.get("Boot_version"),
            "integrate_version": common_values.get("integrate_version"),
            "wireless_name": common_values.get("wireless_name"),
            "device_alias_name": common_values.get("device_alias_name"),
            "sms_center": sms_settings.get("sca"),
            "signal_info": signal_info,
            "wifi_onoff": wifi_status.get("wifi_onoff", wifi_global.get("wifi_onoff")),
            "mobile_data_enable": wwan.get("enable"),
            "upnp_enabled": upnp_status.get("enabled"),
            "dmz_enabled": dmz_status.get("enabled"),
            "dmz_ip": dmz_status.get("dest_ip"),
            "nat_enabled": nat_status.get("enabled"),
            "ddns_enabled": ddns_status.get("enable") == 1 or ddns_status.get("enable") is True,
            "ddns_service": ddns_status.get("service"),
            "ddns_domain": ddns_status.get("domain"),
            "ddns_status_text": ddns_status.get("status"),
        }
        LOGGER.debug(
            "Summary built: wa_inner_version=%s wan_ip=%s signal_keys=%s",
            summary.get("wa_inner_version"),
            summary.get("wan_ipv4_address"),
            list((signal_info or {}).keys()),
        )
        return summary

    def _fetch_sms_capacity(self, token: str) -> Dict[str, Any]:
        try:
            response = self._ubus_call(
                "zwrt_wms",
                "zwrt_wms_get_wms_capacity",
                {},
                token,
            )
            data = self._safe_result(response)
            if isinstance(data, dict):
                return data
        except Exception as exc:
            LOGGER.warning("Failed to fetch SMS capacity: %s", exc)
        return {}

    def _flatten_sms_capacity_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        fields: Dict[str, Any] = {}

        def as_int(value: Any) -> Optional[int]:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        mapping = [
            "sms_nv_total",
            "sms_nv_rev_total",
            "sms_nv_send_total",
            "sms_nv_draftbox_total",
            "sms_sim_total",
            "sms_sim_rev_total",
            "sms_sim_send_total",
            "sms_sim_draftbox_total",
        ]
        for key in mapping:
            raw_value = data.get(key)
            converted = as_int(raw_value)
            fields[key] = converted if converted is not None else raw_value

        # Duplicate fields with *_received_* naming for compatibility
        if "sms_nv_rev_total" in fields:
            fields["sms_nv_received_total"] = fields["sms_nv_rev_total"]
        if "sms_sim_rev_total" in fields:
            fields["sms_sim_received_total"] = fields["sms_sim_rev_total"]

        nv_total = as_int(data.get("sms_nv_total"))
        nv_rev = as_int(data.get("sms_nv_rev_total")) or 0
        nv_send = as_int(data.get("sms_nv_send_total")) or 0
        nv_draft = as_int(data.get("sms_nv_draftbox_total")) or 0
        if nv_total is not None:
            used = nv_rev + nv_send + nv_draft
            fields["sms_capacity_left"] = max(nv_total - used, 0)
        return fields

    def _merge_flux_metrics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        flux_fields: Dict[str, Any] = {}
        stats = results.get("flux_stats")
        if isinstance(stats, dict):
            def grab_int(key: str) -> Optional[int]:
                return self._coerce_int(stats.get(key))

            mapping = {
                "flux_monthly_tx_bytes": "month_tx_bytes",
                "flux_monthly_rx_bytes": "month_rx_bytes",
                "flux_monthly_time": "month_time",
                "flux_monthly_tx_packets": "month_tx_packets",
                "flux_monthly_rx_packets": "month_rx_packets",
                "flux_monthly_tx_drop_packets": "month_tx_drop_packets",
                "flux_monthly_rx_drop_packets": "month_rx_drop_packets",
                "flux_monthly_tx_error_packets": "month_tx_error_packets",
                "flux_monthly_rx_error_packets": "month_rx_error_packets",
                "flux_realtime_tx_bytes": "real_tx_bytes",
                "flux_realtime_rx_bytes": "real_rx_bytes",
                "flux_realtime_time": "real_time",
                "flux_realtime_tx_packets": "real_tx_packets",
                "flux_realtime_rx_packets": "real_rx_packets",
                "flux_realtime_tx_drop_packets": "real_tx_drop_packets",
                "flux_realtime_rx_drop_packets": "real_rx_drop_packets",
                "flux_realtime_tx_error_packets": "real_tx_error_packets",
                "flux_realtime_rx_error_packets": "real_rx_error_packets",
                "flux_realtime_tx_thrpt": "real_tx_speed",
                "flux_realtime_rx_thrpt": "real_rx_speed",
                "flux_realtime_max_tx_thrpt": "real_max_tx_speed",
                "flux_realtime_max_rx_thrpt": "real_max_rx_speed",
                "flux_total_time": "total_time",
                "flux_total_tx_bytes": "total_tx_bytes",
                "flux_total_rx_bytes": "total_rx_bytes",
                "flux_total_tx_packets": "total_tx_packets",
                "flux_total_rx_packets": "total_rx_packets",
                "flux_total_tx_drop_packets": "total_tx_drop_packets",
                "flux_total_rx_drop_packets": "total_rx_drop_packets",
                "flux_total_tx_error_packets": "total_tx_error_packets",
                "flux_total_rx_error_packets": "total_rx_error_packets",
            }
            for target, source in mapping.items():
                flux_fields[target] = grab_int(source)

            tx_bytes = flux_fields.get("flux_monthly_tx_bytes")
            rx_bytes = flux_fields.get("flux_monthly_rx_bytes")
            if tx_bytes is not None and rx_bytes is not None:
                flux_fields["flux_total_usage"] = tx_bytes + rx_bytes

        month_limit = results.get("flux_monthlimit")
        if isinstance(month_limit, dict):
            enable = month_limit.get("enable")
            limit_type = month_limit.get("type")
            limit_value = month_limit.get("value")
            ratio = month_limit.get("ratio")
            overflow = month_limit.get("overflow")

            flux_fields["flux_data_volume_limit_enable"] = enable
            flux_fields["flux_data_volume_limit_type"] = limit_type
            flux_fields["flux_data_volume_limit_size"] = self._coerce_int(limit_value)
            flux_fields["flux_data_volume_alert_percent"] = self._coerce_int(ratio)
            flux_fields["flux_data_volume_overflow"] = self._coerce_int(overflow)
            flux_fields["flux_data_volume_limit_unit"] = self._derive_flux_unit(limit_type)

        clear_day = results.get("flux_clearday")
        if isinstance(clear_day, dict):
            flux_fields["flux_data_volume_auto_clear_enable"] = clear_day.get("enable")
            flux_fields["flux_data_volume_clearday"] = clear_day.get("clearday")
        return flux_fields

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _derive_flux_unit(limit_type: Any) -> str:
        mapping = {
            "1": "MB",
            "2": "GB",
            1: "MB",
            2: "GB",
        }
        return mapping.get(limit_type, str(limit_type) if limit_type is not None else "")

    def _build_dynamic_section(self, gather: Dict[str, Any]) -> Dict[str, Any]:
        dynamic: Dict[str, Any] = {}
        for key, prefix in DYNAMIC_SECTIONS:
            section = gather.get(key)
            if isinstance(section, dict):
                if prefix:
                    for inner_key, value in section.items():
                        dynamic[f"{prefix}{inner_key}"] = value
                else:
                    dynamic.update(section)
        capacity_flat = gather.get("sms_capacity_flat")
        if isinstance(capacity_flat, dict):
            dynamic.update(capacity_flat)
        flux_flat = gather.get("flux_flat")
        if isinstance(flux_flat, dict):
            for key, value in flux_flat.items():
                if value is not None:
                    dynamic[key] = value
        summary = gather.get("summary") or {}
        for source, target in SUMMARY_MAP.items():
            value = summary.get(source)
            if value is not None and target not in dynamic:
                dynamic[target] = value
        if "wa_inner_version" not in dynamic:
            dynamic["wa_inner_version"] = summary.get("wa_inner_version")
        return dynamic

    def _build_status_section(self, gather: Dict[str, Any]) -> Dict[str, Any]:
        status: Dict[str, Any] = {}
        summary = gather.get("summary") or {}
        status.update(summary)
        status.update(gather.get("signal_info") or {})
        return status

    def _build_client_section(self, gather: Dict[str, Any]) -> Dict[str, Any]:
        wireless = gather.get("wireless_clients") or []
        lan = gather.get("lan_clients") or []
        offline = gather.get("offline_clients") or []
        LOGGER.debug(
            "Client section counts wireless=%s lan=%s offline=%s",
            len(wireless),
            len(lan),
            len(offline),
        )
        return {
            "station_list": wireless,
            "lan_station_list": lan,
            "offline_devices": offline,
            "all_devices": wireless + lan + offline,
        }

    def fetch_last_sms(self) -> Dict[str, Any]:
        sms = self.list_sms_messages(page=0, per_page=1)
        messages = sms.get("messages") or []
        LOGGER.debug("Fetched %s SMS messages for last SMS lookup", len(messages))
        return messages[0] if messages else {}

    def delete_all_sms(self) -> Dict[str, Any]:
        page = 0
        collected_ids: List[str] = []
        per_page = 100
        while True:
            batch = self.list_sms_messages(page=page, per_page=per_page)
            msgs = batch.get("messages") or []
            batch_ids = [msg.get("id") for msg in msgs if msg.get("id")]
            collected_ids.extend(batch_ids)
            if len(msgs) < per_page:
                break
            page += 1
        if not collected_ids:
            return {"deleted_ids": [], "status": "No SMS"}
        LOGGER.info("Deleting %s SMS entries", len(collected_ids))
        delete_result = self.delete_sms_messages(collected_ids)
        return {"deleted_ids": collected_ids, "status": delete_result}

    def reboot_router(self) -> Dict[str, Any]:
        token = self._ensure_token()
        response = self._ubus_call(
            "zwrt_mc.device.manager",
            "device_reboot",
            {"moduleName": "web"},
            token,
        )
        return self._safe_result(response)

    def set_mobile_data(self, enable: bool) -> Dict[str, Any]:
        token = self._ensure_token()
        response = self._ubus_call(
            "zwrt_data",
            "set_wwaniface",
            {"source_module": "web", "cid": 1, "enable": 1 if enable else 0},
            token,
        )
        return self._safe_result(response)

    def set_wifi(self, enable: bool) -> Dict[str, Any]:
        token = self._ensure_token()
        params = {"zte_mbb": {"wifi_onoff": "1" if enable else "0"}}
        if enable:
            params["zte_mbb"]["lbd"] = "1"
            params["zte_mbb"]["mlo"] = "0"
        response = self._ubus_call("zwrt_wlan", "set", params, token)
        return self._safe_result(response)

    def set_network_mode(self, mode: str) -> Dict[str, Any]:
        """mode: one of ONLY_3G, ONLY_4G, ONLY_5G, 4G_AND_5G."""
        token = self._ensure_token()
        response = self._ubus_call(
            "zte_nwinfo_api",
            "nwinfo_set_netselect",
            {"net_select": mode},
            token,
        )
        return self._safe_result(response)

    def lock_lte_cell(self, pci: str, earfcn: str) -> Dict[str, Any]:
        token = self._ensure_token()
        response = self._ubus_call(
            "zte_nwinfo_api",
            "nwinfo_lock_lte_cell",
            {"lock_lte_pci": pci, "lock_lte_earfcn": earfcn},
            token,
        )
        return self._safe_result(response)

    def lock_nr_cell(self, pci: str, arfcn: str, band: str) -> Dict[str, Any]:
        token = self._ensure_token()
        response = self._ubus_call(
            "zte_nwinfo_api",
            "nwinfo_lock_nr_cell",
            {"lock_nr_pci": pci, "lock_nr_earfcn": arfcn, "lock_nr_cell_band": band},
            token,
        )
        return self._safe_result(response)

    def set_lte_band_lock(self, band_mask: str) -> Dict[str, Any]:
        token = self._ensure_token()
        response = self._ubus_call(
            "zte_nwinfo_api",
            "nwinfo_set_gwl_bandlock",
            {
                "is_lte_band": "1",
                "lte_band_mask": band_mask,
                "is_gw_band": "0",
                "gw_band_mask": "0",
            },
            token,
        )
        return self._safe_result(response)

    def set_nr_band_lock(self, nr_type: str, bands: str) -> Dict[str, Any]:
        """nr_type: 'nsa' or 'sa'. bands: comma-separated band numbers, e.g. '78,3,1'."""
        token = self._ensure_token()
        response = self._ubus_call(
            "zte_nwinfo_api",
            "nwinfo_set_nrbandlock",
            {"nr5g_type": nr_type, "nr5g_band": bands},
            token,
        )
        return self._safe_result(response)

    def reset_band_cell_locks(self) -> Dict[str, Any]:
        token = self._ensure_token()
        response = self._ubus_call(
            "zte_nwinfo_api",
            "nwinfo_reset_band_cell_setting",
            {},
            token,
        )
        return self._safe_result(response)

    def send_ussd(self, code: str) -> Dict[str, Any]:
        token = self._ensure_token()
        response = self._ubus_call(
            "zwrt_ussd",
            "libzte_ussd_web_process",
            {"ussd_data": code},
            token,
        )
        return self._safe_result(response)

    def set_firewall(self, enable: bool) -> Dict[str, Any]:
        token = self._ensure_token()
        response = self._ubus_call(
            "zwrt_router.api",
            "router_set_firewall_switch",
            {"enable": 1 if enable else 0},
            token,
        )
        return self._safe_result(response)

    def set_nat(self, enable: bool) -> Dict[str, Any]:
        token = self._ensure_token()
        response = self._ubus_call(
            "zwrt_router.api",
            "router_set_nat_switch",
            {"enable": 1 if enable else 0},
            token,
        )
        return self._safe_result(response)

    def set_upnp(self, enable: bool) -> Dict[str, Any]:
        token = self._ensure_token()
        response = self._ubus_call(
            "zwrt_router.api",
            "router_set_upnp_switch",
            {"enable_upnp": 1 if enable else 0},
            token,
        )
        return self._safe_result(response)

    def set_dmz(self, enable: bool, dmz_ip: str = "") -> Dict[str, Any]:
        token = self._ensure_token()
        response = self._ubus_call(
            "zwrt_router.api",
            "router_set_dmz",
            {"dmz_enable": 1 if enable else 0, "dmz_ip": dmz_ip},
            token,
        )
        return self._safe_result(response)

    def set_wan_dns(self, mode: str, prefer_dns: str = "", standby_dns: str = "") -> Dict[str, Any]:
        """mode: 'auto' or 'manual'."""
        token = self._ensure_token()
        response = self._ubus_call(
            "zwrt_router.api",
            "router_set_wan_dns",
            {
                "dns_mode": mode,
                "prefer_dns_manual": prefer_dns,
                "standby_dns_manual": standby_dns,
            },
            token,
        )
        return self._safe_result(response)

    def set_wan_mtu(self, mtu: int) -> Dict[str, Any]:
        token = self._ensure_token()
        response = self._ubus_call(
            "zwrt_router.api",
            "router_set_wan_mtu",
            {"mtu": mtu},
            token,
        )
        return self._safe_result(response)

    def set_ddns(
        self,
        enable: bool,
        service: str = "",
        domain: str = "",
        account: str = "",
        password: str = "",
    ) -> Dict[str, Any]:
        token = self._ensure_token()
        response = self._ubus_call(
            "zwrt_router.api",
            "router_set_ddns",
            {
                "enable": 1 if enable else 0,
                "service": service,
                "domain": domain,
                # Upstream ubus method itself uses this misspelled key name.
                "accout": account,
                "password": password,
            },
            token,
        )
        return self._safe_result(response)

    def set_apn_mode(self, mode: str) -> Dict[str, Any]:
        """mode: '0' (auto) or '1' (manual)."""
        token = self._ensure_token()
        response = self._ubus_call(
            "zwrt_apn_object",
            "set_apn_mode",
            {"apn_mode": mode},
            token,
        )
        return self._safe_result(response)

    def add_apn_profile(
        self,
        profile_name: str,
        apn: str,
        username: str = "",
        password: str = "",
        pdp_type: int = 0,
        auth_mode: int = 0,
    ) -> Dict[str, Any]:
        """pdp_type: 0=IPv4, 1=IPv6, 2=both. auth_mode: 0=none, 1=PAP, 2=CHAP."""
        token = self._ensure_token()
        response = self._ubus_call(
            "zwrt_apn_object",
            "add_manu_apn",
            {
                "profilename": profile_name,
                "wanapn": apn,
                "username": username,
                "password": password,
                "pdpType": pdp_type,
                "pppAuthMode": auth_mode,
            },
            token,
        )
        return self._safe_result(response)

    def _get_uci_config(self, config_name: str) -> Dict[str, Any]:
        token = self._ensure_token()
        response = self._ubus_call("uci", "get", {"config": config_name}, token)
        result = self._safe_result(response)
        return result if isinstance(result, dict) else {}

    def get_upnp_status(self) -> Dict[str, Any]:
        """Read UPnP status. No vendor 'get' API exists for this; read from
        the underlying UCI config instead (uci.get config=upnpd)."""
        values = self._get_uci_config("upnpd").get("values") or {}
        config = values.get("config") if isinstance(values, dict) else None
        config = config if isinstance(config, dict) else {}
        return {"enabled": config.get("enable_upnp") == "1"}

    def _get_firewall_uci(self) -> Dict[str, Any]:
        values = self._get_uci_config("firewall").get("values")
        return values if isinstance(values, dict) else {}

    def get_dmz_status(self) -> Dict[str, Any]:
        """Read DMZ status. No vendor 'get' API exists; DMZ shows up as a
        firewall redirect rule named "DMZ" in the UCI firewall config."""
        for section in self._get_firewall_uci().values():
            if isinstance(section, dict) and section.get(".type") == "redirect" and section.get("name") == "DMZ":
                return {"enabled": section.get("enabled") == "1", "dest_ip": section.get("dest_ip", "")}
        return {"enabled": False, "dest_ip": ""}

    def get_nat_status(self) -> Dict[str, Any]:
        """Read NAT status via the WAN zone's masquerade flag. No vendor
        'get' API exists for this. Not fully confirmed to correspond to
        what router_set_nat_switch actually toggles -- best effort."""
        for section in self._get_firewall_uci().values():
            if isinstance(section, dict) and section.get(".type") == "zone" and section.get("name") == "wan":
                return {"enabled": section.get("masq") == "1"}
        return {"enabled": False}

    def get_ddns_status(self) -> Dict[str, Any]:
        """Read DDNS status. Unlike the others, a real vendor 'get' method
        exists for this (router_get_ddns). Note: it never returns the
        configured password, so this must stay read-only/informational."""
        token = self._ensure_token()
        response = self._ubus_call("zwrt_router.api", "router_get_ddns", {}, token)
        result = self._safe_result(response)
        return result if isinstance(result, dict) else {}

    def send_sms(self, number: str, message: str) -> Dict[str, Any]:
        token = self._ensure_token()
        payload = {
            "number": number,
            "sms_time": get_current_time_string(),
            "message_body": encode_message_hex(message),
            "id": "0",
            "encode_type": "UNICODE",
        }
        response = self._ubus_call(
            "zwrt_wms",
            "zte_libwms_send_sms",
            payload,
            token,
        )
        result = self._safe_result(response)
        command_status = self.wait_for_sms_command(token, sms_cmd=4)
        LOGGER.info("Sent SMS to %s with status %s", number, command_status.get("status"))
        return {"request": result, "command_status": command_status}

    def list_sms_messages(
        self,
        page: int = 0,
        per_page: int = 100,
        mem_store: Any = 1,
        tags: Any = 10,
        order_by: str = "order by id desc",
    ) -> Dict[str, Any]:
        token = self._ensure_token()
        normalized_store = normalize_mem_store_arg(mem_store)
        payload = {
            "page": page,
            "data_per_page": per_page,
            "mem_store": normalized_store,
            "tags": tags,
            "order_by": order_by,
        }
        response = self._ubus_call(
            "zwrt_wms",
            "zte_libwms_get_sms_data",
            payload,
            token,
        )
        data = self._safe_result(response)
        raw_messages = data.get("messages", []) if isinstance(data, dict) else []
        formatted = [format_sms_record(item) for item in raw_messages or []]
        LOGGER.debug(
            "Listed SMS messages page=%s count=%s raw_preview=%s",
            page,
            len(formatted),
            repr(raw_messages[:1]) if raw_messages else "[]",
        )
        return {
            "page": page,
            "per_page": per_page,
            "mem_store": normalized_store,
            "mem_store_label": describe_mem_store(normalized_store),
            "tags": tags,
            "order_by": order_by,
            "messages": formatted,
        }

    def delete_sms_messages(self, ids: List[str]) -> Dict[str, Any]:
        token = self._ensure_token()
        ids = [str(i) for i in ids if str(i)]
        if not ids:
            return {"status": "no_ids"}
        payload = {"id": ";".join(ids) + ";"}
        response = self._ubus_call(
            "zwrt_wms",
            "zwrt_wms_delete_sms",
            payload,
            token,
        )
        delete_result = self._safe_result(response)
        command_status = self.wait_for_sms_command(token, sms_cmd=6)
        LOGGER.info("Delete SMS command result: %s", command_status.get("status"))
        return {"request": delete_result, "command_status": command_status}

    def wait_for_sms_command(self, token: str, sms_cmd: int, timeout: int = 30, poll_interval: float = 1.0) -> Dict[str, Any]:
        deadline = time.time() + timeout
        last_payload = None
        while time.time() < deadline:
            resp = self._ubus_call(
                "zwrt_wms",
                "zwrt_wms_get_cmd_status",
                {"sms_cmd": sms_cmd},
                token,
            )
            data = self._safe_result(resp)
            if isinstance(data, dict):
                last_payload = data
                LOGGER.debug("SMS cmd %s status payload: %s", sms_cmd, data)
                status = str(data.get("sms_cmd_status_result", ""))
                if status == "3":
                    return {"status": "success", "details": data}
                if status == "2":
                    return {"status": "failed", "details": data}
            time.sleep(poll_interval)
        return {"status": "timeout", "details": last_payload}

    def _make_headers(self, token: str, module: str, func: str, params: Dict[str, Any]) -> Dict[str, str]:
        logged_in = token != ZERO_TOKEN
        z_tag = func
        if module == "uci":
            z_tag = params.get("config", "")
        return {
            "Z-Mode": "1" if logged_in else "0",
            "Z-Tag": z_tag,
            "Referer": self.referer,
            "Origin": self.base_url,
            "X-Requested-With": "XMLHttpRequest",
        }

    def _ubus_call(self, module: str, func: str, params: Dict[str, Any], token: Optional[str]) -> Dict[str, Any]:
        url = f"{self.router_url}?t={int(time.time() * 1000)}"
        headers = self._make_headers(token or ZERO_TOKEN, module, func, params)
        payload = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "call",
                "params": [token or ZERO_TOKEN, module, func, params],
            }
        ]
        LOGGER.debug(
            "ULTRA REQUEST %s.%s params=%s url=%s",
            module,
            func,
            params,
            url,
        )
        try:
            response = self.session.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            LOGGER.debug(
                "ULTRA RESPONSE %s.%s status=%s body=%s",
                module,
                func,
                response.status_code,
                response.text[:1500],
            )
            return response.json()
        except RequestException as exc:
            if self._enable_https():
                LOGGER.warning("Retrying G5 Ultra request over HTTPS due to: %s", exc)
                return self._ubus_call(module, func, params, token)
            raise

    @staticmethod
    def _safe_result(response: Dict[str, Any]) -> Dict[str, Any]:
        try:
            entry = response[0]
            if isinstance(entry, dict):
                if "error" in entry:
                    error = entry.get("error") or {}
                    message = error.get("message", "Unknown ubus error")
                    code = error.get("code")
                    raise RuntimeError(f"ubus error ({code}): {message}")
                if "result" in entry and isinstance(entry["result"], list) and len(entry["result"]) > 1:
                    return entry["result"][1]
        except Exception:
            pass
        return response
