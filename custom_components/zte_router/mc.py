global_stok = None
global_AD = None
import hashlib
from datetime import datetime, timedelta
import json
import sys
import os
import time
import secrets
import base64
import urllib3
import urllib
from urllib.parse import quote
import logging
from http.cookies import SimpleCookie
import ssl
import socket
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import re
from pygsm7 import encodeMessage, decodeMessage
import traceback  # <-- add this at the top if not already
from logging.handlers import TimedRotatingFileHandler
import gzip
import shutil

# Disable warnings for insecure connections
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log_certificate_details = False  # Set to True if you want to see certificate details in logs
# Configure the logger
logger = logging.getLogger('homeassistant.components.zte_router')

from logging.handlers import TimedRotatingFileHandler
import gzip
import shutil

if __name__ == "__main__":
    # Configure logging when run directly
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # Common formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler for mc.log in same directory as script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(script_dir, "mc.log")

        # Timed Rotating Handler: Rotate every 24h, keep 7 backups
        rotating_handler = TimedRotatingFileHandler(
            log_path,
            when='midnight',
            interval=1,
            backupCount=1,
            encoding='utf-8',
            utc=False
        )
        rotating_handler.setFormatter(formatter)
        rotating_handler.suffix = "%Y-%m-%d"

        # Optional: Compress old logs after rotation
        def compress_old_logs(handler):
            log_dir = os.path.dirname(handler.baseFilename)
            for filename in os.listdir(log_dir):
                if filename.startswith("mc.log.") and not filename.endswith(".gz"):
                    full_path = os.path.join(log_dir, filename)
                    gz_path = full_path + ".gz"
                    if not os.path.exists(gz_path):  # Only compress if not already
                        with open(full_path, 'rb') as f_in, gzip.open(gz_path, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                        os.remove(full_path)
                        logger.info(f"Compressed log file: {gz_path}")

        # Hook into the handler’s rotation
        def doRolloverAndCompress():
            rotating_handler.doRollover()
            compress_old_logs(rotating_handler)

        # Optional override: copy on rotate + keep filename format
        rotating_handler.rotator = lambda source, dest: shutil.copy2(source, dest)
        rotating_handler.namer = lambda name: name

        # Add the handler
        logger.addHandler(rotating_handler)

        # Optional: trigger rollover + compress manually at startup
        # doRolloverAndCompress()

else:
    # Suppress logging when imported
    logger.setLevel(logging.WARNING)

# Create a PoolManager instance with permissive TLS settings for router self-signed/weak certs.
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
try:
    # Some router certs use weak key params and fail default security level.
    ssl_context.set_ciphers("DEFAULT:@SECLEVEL=0")
except Exception:
    pass

s = urllib3.PoolManager(cert_reqs='CERT_NONE', ssl_context=ssl_context)

def get_sms_time():
    logger.debug("Generating SMS time")
    return datetime.now().strftime("%y;%m;%d;%H;%M;%S;+2")

def clean_control_chars(s):
        """Remove control characters from a string (except newline and tab)."""
        return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', s)

def hex2utf(string):
        """Convert UCS-2 hex string to UTF-8."""
        result = ''
        try:
            for i in range(len(string) // 4):
                result += chr(int(string[i * 4:i * 4 + 4], 16))
        except Exception as e:
            logger.warning(f"Failed to decode UCS2 string: {string} - Error: {e}")
        return result

class zteRouter:

    def authenticate(self):
        """Authenticate and store credentials (stok and AD) in instance fields."""
        LD = self.get_LD()
        AD = self.get_AD()
        stok = self.getCookie(self.username, self.password, LD, AD)
        self._zte_auth_stok = stok
        self._zte_auth_AD = AD
        self._zte_auth_LD = LD
        logger.info("Authentication credentials stored in object instance")

    def __init__(self, ip, username, password):
        self.ip = ip
        self.protocol = "http"
        self.username = username
        self.password = password
        self.cookies = {}
        self.stok = None
        self.uses_stok = False
        logger.info(f"Initializing ZTE Router with IP {ip}, Username: {username}, Password: {password}")

        self.try_set_protocol()
        self.referer = f"{self.protocol}://{self.ip}/"

    CERT_FILE = "/tmp/zte_router_cert.pem"

    def request_with_session(self, method, url, headers=None, body=None):
        if headers is None:
            headers = {}
        if self.stok:
            headers['Cookie'] = f'stok={self.stok}'
        # Remove cookie header logic, always use instance cookies set at authentication
        # No build_cookie_header, but still allow for legacy compatibility if needed
        # (In future, could remove all cookie logic)
        start_time = time.perf_counter()
        response = s.request(method, url, headers=headers, body=body)
        latency = int((time.perf_counter() - start_time) * 1000)

        if response.status in [502, 503, 504] or response.status >= 520:
            logger.error(f"Router unavailable (status {response.status})")
            raise ConnectionError(f"Router unavailable (status {response.status})")
        return response

        
    def get_certificate_info(self, hostname, port=443):
        logger.debug(f"Checking for existing SSL certificate file: {self.CERT_FILE}")
        if os.path.exists(self.CERT_FILE):
            with open(self.CERT_FILE, 'r') as cert_file:
                pem_cert = cert_file.read()
            logger.info(f"Loaded SSL certificate from disk: {self.CERT_FILE}")
            self.parse_certificate(pem_cert)
            return pem_cert

        logger.debug(f"Retrieving SSL certificate for {hostname}:{port}")
        context = ssl._create_unverified_context()
        context.check_hostname = False
        try:
            with socket.create_connection((hostname, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    der_cert = ssock.getpeercert(binary_form=True)
                    if der_cert is None:
                        logger.error("No certificate received")
                        return None
                    pem_cert = ssl.DER_cert_to_PEM_cert(der_cert)
                    with open(self.CERT_FILE, 'w') as cert_file:
                        cert_file.write(pem_cert)
                    logger.info(f"SSL certificate for {hostname}:{port} retrieved and stored successfully")
                    self.parse_certificate(pem_cert)
                    return pem_cert
        except Exception as e:
            logger.error(f"Failed to retrieve SSL certificate for {hostname}:{port}: {e}")
            return None
        
    def parse_certificate(self, pem_cert):
        logger.debug("Parsing PEM certificate")
        try:
            cert = x509.load_pem_x509_certificate(pem_cert.encode('utf-8'), default_backend())

            def get_attribute(name, oid):
                try:
                    return name.get_attributes_for_oid(oid)[0].value
                except IndexError:
                    return "N/A"

            subject = cert.subject
            issuer = cert.issuer

            subject_info = {
                "Common Name": get_attribute(subject, x509.NameOID.COMMON_NAME),
                "Organization": get_attribute(subject, x509.NameOID.ORGANIZATION_NAME),
                "Organizational Unit": get_attribute(subject, x509.NameOID.ORGANIZATIONAL_UNIT_NAME),
                "Country": get_attribute(subject, x509.NameOID.COUNTRY_NAME),
                "State/Province": get_attribute(subject, x509.NameOID.STATE_OR_PROVINCE_NAME),
                "Email Address": get_attribute(subject, x509.NameOID.EMAIL_ADDRESS),
            }

            issuer_info = {
                "Common Name": get_attribute(issuer, x509.NameOID.COMMON_NAME),
                "Organization": get_attribute(issuer, x509.NameOID.ORGANIZATION_NAME),
                "Organizational Unit": get_attribute(issuer, x509.NameOID.ORGANIZATIONAL_UNIT_NAME),
                "Country": get_attribute(issuer, x509.NameOID.COUNTRY_NAME),
                "State/Province": get_attribute(issuer, x509.NameOID.STATE_OR_PROVINCE_NAME),
                "Email Address": get_attribute(issuer, x509.NameOID.EMAIL_ADDRESS),
            }

            validity = {
                "Not Before": cert.not_valid_before_utc,
                "Not After": cert.not_valid_after_utc,
            }

            serial_number = cert.serial_number

            if log_certificate_details:
                cert_info = "\nCertificate Information:\n========================"
                cert_info += "\nSubject:"
                for key, value in subject_info.items():
                    cert_info += f"\n    {key:22}: {value}"

                cert_info += "\n\nIssuer:"
                for key, value in issuer_info.items():
                    cert_info += f"\n    {key:22}: {value}"

                cert_info += "\n\nValidity:"
                for key, value in validity.items():
                    cert_info += f"\n    {key:22}: {value}"

                cert_info += f"\n\nSerial Number:            {serial_number}"
                logger.info(cert_info)
            else:
                logger.debug("Certificate parsed successfully, logging is disabled.")

        except Exception as e:
            logger.error(f"Failed to parse certificate: {e}")


    # Remove update_cookies and build_cookie_header (no longer needed)

    def try_set_protocol(self):
        protocols = ["https", "http"]
        for protocol in protocols:
            url = f"{protocol}://{self.ip}/index.html"
            try:
                response = s.request('GET', url, timeout=2, retries=2)  # reduced timeout and retries
                if response.status in [200, 302, 301]:
                    self.protocol = protocol
                    logger.info(f"Protocol set to {protocol}")
                    if protocol == "https":
                        self.get_certificate_info(self.ip)
                    return
            except Exception as e:
                logger.info(f"Failed to connect using {protocol}: {e}, trying next protocol.")

        # Instead of raising, handle router unavailability gracefully:
        logger.warning("Router is unavailable, protocol not set.")
        self.protocol = None


    def hash(self, str):
        hashed = hashlib.sha256(str.encode()).hexdigest()
        logger.debug(f"Hashed string: {hashed}")
        return hashed

    def getVersion(self):
        logger.debug("Fetching router version")
        header = {"Referer": self.referer}
        payload = "isTest=false&cmd=wa_inner_version"
        url = self.referer + f"goform/goform_get_cmd_process?{payload}"
        try:
            r = self.request_with_session('GET', url, headers=header)
            data = r.data.decode('utf-8')
            version = json.loads(data)["wa_inner_version"]
            logger.info(f"Router version: {version}")
            return version
        except Exception as e:
            logger.error(f"Failed to fetch version: {e}")
            return ""

    def get_LD(self):
        logger.debug("Fetching LD value")
        header = {"Referer": self.referer}
        payload = "isTest=false&cmd=LD"
        url = self.referer + f"goform/goform_get_cmd_process?{payload}"
        try:
            r = self.request_with_session('GET', url, headers=header)
            data = r.data.decode('utf-8')
            ld = json.loads(data)["LD"].upper()
            logger.info(f"LD: {ld}")
            return ld
        except Exception as e:
            logger.error(f"Failed to fetch LD: {e}")
            return ""

    def getCookie(self, username, password, LD, AD):
        logger.debug(f"Getting cookie for username: {username}, password: {password}, LD: {LD}")
        header = {"Referer": self.referer}

        hashPassword = self.hash(password).upper()
        ztePass = self.hash(hashPassword + LD).upper()

        #AD = self.get_AD()

        if username:
            goform_id = 'LOGIN_MULTI_USER'
            payload = {
                'isTest': 'false',
                'goformId': goform_id,
                'user': username,
                'password': ztePass,
                'AD': AD
            }
        else:
            goform_id = 'LOGIN'
            payload = {
                'isTest': 'false',
                'goformId': goform_id,
                'password': ztePass
            }

        url = self.referer + "goform/goform_set_cmd_process"
        encoded_payload = urllib.parse.urlencode(payload)
        body = encoded_payload.encode('utf-8')

        try:
            r = self.request_with_session('POST', url, headers=header, body=body)
            # Parse cookies from response for session storage
            cookie = SimpleCookie()
            set_cookie_header = r.headers.get('Set-Cookie', '')
            if set_cookie_header:
                cookie.load(set_cookie_header)
            stok = cookie.get('stok')
            if stok:
                self.uses_stok = True
                self.stok = stok.value
                logger.info(f"🔐 Router uses stok: {self.stok}")
            else:
                self.uses_stok = False
                self.stok = None
                logger.info("🔓 Router does NOT use stok (cookie-based only login)")
            # Save cookies for use in subsequent requests
            self.cookies = {}
            for key, morsel in cookie.items():
                self.cookies[key] = morsel.value
            logger.info(f"Obtained new session cookie: stok={self.stok}")
            return self.stok
        except Exception as e:
            logger.error(f"Failed to obtain cookie: {e}")
            raise


    def get_RD(self):
        logger.debug("Fetching RD value")
        header = {"Referer": self.referer}
        payload = "isTest=false&cmd=RD"
        url = self.referer + f"goform/goform_get_cmd_process?{payload}"
        try:
            r = self.request_with_session('POST', url, headers=header)
            data = r.data.decode('utf-8')
            rd = json.loads(data)["RD"]
            logger.info(f"RD: {rd}")
            return rd
        except Exception as e:
            logger.error(f"Failed to fetch RD: {e}")
            return ""

    def get_AD(self):
        logger.debug("Calculating AD value")
        def md5(s):
            m = hashlib.md5()
            m.update(s.encode("utf-8"))
            return m.hexdigest()

        def sha256(s):
            m = hashlib.sha256()
            m.update(s.encode("utf-8"))
            return m.hexdigest().upper()  # .upper() to match your example hash

        wa_inner_version = self.getVersion()
        if wa_inner_version == "":
            return ""

        is_mc888 = "MC888" in wa_inner_version
        is_mc889 = "MC889" in wa_inner_version

        hash_function = sha256 if is_mc888 or is_mc889 else md5

        cr_version = ""  # You need to define or get cr_version value as it's not provided in the given code

        a = hash_function(wa_inner_version + cr_version)

        header = {"Referer": self.referer}
        try:
            rd_url = self.referer + "goform/goform_get_cmd_process?isTest=false&cmd=RD"
            rd_response = self.request_with_session('GET', rd_url, headers=header)
            data = rd_response.data.decode('utf-8')
            rd_json = json.loads(data)
            u = rd_json.get("RD", "")

            result = hash_function(a + u)
            logger.info(f"AD: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to calculate AD: {e}")
            return ""



    def sendsms(self, phone_number, message):
        logger.debug(f"Sending SMS to {phone_number} with message: {message}")
        try:
            # MC888 firmware expects a fresh AD for protected write actions.
            AD = self.get_AD() or getattr(self, "_zte_auth_AD", None)
            self._zte_auth_AD = AD
            header = {"Referer": self.referer}
            # Encode phone number and message
            phoneNumberEncoded = urllib.parse.quote(phone_number, safe="")
            messageEncoded = encodeMessage(message)
            logger.debug(f"Encoded SMS (GSM 7-bit): {messageEncoded}")
            payload = {
                'isTest': 'false',
                'goformId': 'SEND_SMS',
                'notCallback': 'true',
                'Number': phoneNumberEncoded,
                'sms_time': get_sms_time(),
                'MessageBody': messageEncoded,
                'ID': '-1',
                'encode_type': 'GSM7_default',
                'AD': AD
            }
            encoded_payload = urllib.parse.urlencode(payload)
            body = encoded_payload.encode('utf-8')
            r = self.request_with_session('POST', self.referer + "goform/goform_set_cmd_process", headers=header, body=body)
            logger.info(f"SMS sent with status code: {r.status}")
            response_text = r.data.decode(errors='replace')
            logger.debug(f"Router response: {response_text}")

            # Newer MC888 firmwares may require RED-encrypted SMS payloads.
            router_result = None
            try:
                parsed = json.loads(response_text)
                router_result = str(parsed.get("result", "")).lower()
            except Exception:
                # Do not short-circuit here; still try RED fallback on non-explicit success.
                logger.debug("Plain SMS response JSON parse failed; trying RED fallback path")

            if router_result == "success":
                return r.status

            red_ready = self._setup_red_crypto()
            if not red_ready:
                # Some firmwares expose RED SMS crypto only after SMS endpoints are touched.
                try:
                    self.ztesmsinfo()
                except Exception:
                    pass
                red_ready = self._setup_red_crypto()

            if red_ready:
                logger.info("Retrying SMS send with RED encryption payload")
                AD = self.get_AD() or getattr(self, "_zte_auth_AD", None)
                self._zte_auth_AD = AD
                red_payload = {
                    'isTest': 'false',
                    'goformId': 'SEND_SMS',
                    'notCallback': 'true',
                    'Number': self._red_encrypt_value(phone_number),
                    'sms_time': get_sms_time(),
                    'MessageBody': self._red_encrypt_value(encodeMessage(message)),
                    'ID': '-1',
                    'encode_type': 'GSM7_default',
                    'AD': AD
                }
                red_body = urllib.parse.urlencode(red_payload).encode('utf-8')
                rr = self.request_with_session(
                    'POST',
                    self.referer + "goform/goform_set_cmd_process",
                    headers=header,
                    body=red_body,
                )
                logger.info(f"RED SMS send status code: {rr.status}")
                red_response_text = rr.data.decode(errors='replace')
                logger.debug(f"RED Router response: {red_response_text}")
                try:
                    red_parsed = json.loads(red_response_text)
                    if red_parsed.get("result") == "success":
                        return rr.status
                except Exception:
                    pass
            else:
                logger.info("RED SMS fallback unavailable in this session")

            return r.status
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            logger.debug(traceback.format_exc())
            return None



    def zteinfo(self):
        logger.debug("Fetching ZTE info")
        try:
            header = {
                "Host": self.ip,
                "Referer": f"{self.referer}index.html",
            }
            cmd_url = f"{self.protocol}://{self.ip}/goform/goform_get_cmd_process?isTest=false&cmd=wa_inner_version%2Ccr_version%2Cnetwork_type%2Crssi%2Crscp%2Crmcc%2Crmnc%2Cenodeb_id%2C5g_rx0_rsrp%2C5g_rx1_rsrp%2Clte_rsrq%2Clte_rsrp%2CZ5g_snr%2CZ5g_rsrp%2CZCELLINFO_band%2CZ5g_dlEarfcn%2Clte_ca_pcell_arfcn%2Clte_ca_pcell_band%2Clte_ca_scell_band%2Clte_ca_pcell_bandwidth%2Clte_ca_scell_info%2Clte_ca_scell_bandwidth%2Cwan_lte_ca%2Clte_pci%2CZ5g_CELL_ID%2CZ5g_SINR%2Ccell_id%2Cwan_lte_ca%2Clte_ca_pcell_band%2Clte_ca_pcell_bandwidth%2Clte_ca_scell_band%2Clte_ca_scell_bandwidth%2Clte_ca_pcell_arfcn%2Clte_ca_scell_arfcn%2Clte_multi_ca_scell_info%2Cwan_active_band%2Cnr5g_pci%2Cnr5g_action_band%2Cnr5g_cell_id%2Clte_snr%2Cecio%2Cwan_active_channel%2Cnr5g_action_channel%2Cngbr_cell_info%2Cmonthly_tx_bytes%2Cmonthly_rx_bytes%2Clte_pci%2Clte_pci_lock%2Clte_earfcn_lock%2Cwan_ipaddr%2Cwan_apn%2Cpm_sensor_mdm%2Cpm_modem_5g%2Cnr5g_pci%2Cnr5g_action_channel%2Cnr5g_action_band%2CZ5g_SINR%2CZ5g_rsrp%2Cwan_active_band%2Cwan_active_channel%2Cwan_lte_ca%2Clte_multi_ca_scell_info%2Ccell_id%2Cdns_mode%2Cprefer_dns_manual%2Cstandby_dns_manual%2Cnetwork_type%2Crmcc%2Crmnc%2Clte_rsrq%2Clte_rssi%2Clte_rsrp%2Clte_snr%2Cwan_lte_ca%2Clte_ca_pcell_band%2Clte_ca_pcell_bandwidth%2Clte_ca_scell_band%2Clte_ca_scell_bandwidth%2Clte_ca_pcell_arfcn%2Clte_ca_scell_arfcn%2Cwan_ipaddr%2Cstatic_wan_ipaddr%2Copms_wan_mode%2Copms_wan_auto_mode%2Cppp_status%2Cloginfo%2Crealtime_time%2Csignalbar&multi_data=1"
            response = self.request_with_session('GET', cmd_url, headers=header)
            data = response.data.decode('utf-8')
            logger.info("Fetched ZTE info successfully")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch ZTE info: {e}")
            return ""

    # ... (Previous methods in the class)

    def zteinfo2(self):
        logger.debug("Fetching ZTE info 2")
        try:
            header = {
                "Host": self.ip,
                "Referer": f"{self.referer}index.html",
            }
            cmd_url = f"{self.protocol}://{self.ip}/goform/goform_get_cmd_process?multi_data=1&isTest=false&sms_received_flag_flag=0&sts_received_flag_flag=0&cmd=network_type%2Crssi%2Clte_rssi%2Crscp%2Clte_rsrp%2CZ5g_snr%2CZ5g_rsrp%2CZCELLINFO_band%2CZ5g_dlEarfcn%2Clte_ca_pcell_arfcn%2Clte_ca_pcell_band%2Clte_ca_scell_band%2Clte_ca_pcell_bandwidth%2Clte_ca_scell_info%2Clte_ca_scell_bandwidth%2Cwan_lte_ca%2Clte_pci%2CZ5g_CELL_ID%2CZ5g_SINR%2Ccell_id%2Cwan_lte_ca%2Clte_ca_pcell_band%2Clte_ca_pcell_bandwidth%2Clte_ca_scell_band%2Clte_ca_scell_bandwidth%2Clte_ca_pcell_arfcn%2Clte_ca_scell_arfcn%2Clte_multi_ca_scell_info%2Cwan_active_band%2Cnr5g_pci%2Cnr5g_action_band%2Cnr5g_cell_id%2Clte_snr%2Cecio%2Cwan_active_channel%2Cnr5g_action_channel%2Cmodem_main_state%2Cpin_status%2Copms_wan_mode%2Copms_wan_auto_mode%2Cloginfo%2Cnew_version_state%2Ccurrent_upgrade_state%2Cis_mandatory%2Cwifi_dfs_status%2Cbattery_value%2Cppp_dial_conn_fail_counter%2Cwifi_chip1_ssid1_auth_mode%2Cwifi_chip2_ssid1_auth_mode%2Csignalbar%2Cnetwork_type%2Cnetwork_provider%2Cppp_status%2Csimcard_roam%2Cspn_name_data%2Cspn_b1_flag%2Cspn_b2_flag%2Cwifi_onoff_state%2Cwifi_chip1_ssid1_ssid%2Cwifi_chip2_ssid1_ssid%2Cwan_lte_ca%2Cmonthly_tx_bytes%2Cmonthly_rx_bytes%2Cpppoe_status%2Cdhcp_wan_status%2Cstatic_wan_status%2Crmcc%2Crmnc%2Cmdm_mcc%2Cmdm_mnc%2CEX_SSID1%2Csta_ip_status%2CEX_wifi_profile%2Cm_ssid_enable%2CRadioOff%2Cwifi_chip1_ssid1_access_sta_num%2Cwifi_chip2_ssid1_access_sta_num%2Clan_ipaddr%2Cstation_mac%2Cwifi_access_sta_num%2Cbattery_charging%2Cbattery_vol_percent%2Cbattery_pers%2Crealtime_tx_bytes%2Crealtime_rx_bytes%2Crealtime_time%2Crealtime_tx_thrpt%2Crealtime_rx_thrpt%2Cmonthly_time%2Cdate_month%2Cdata_volume_limit_switch%2Cdata_volume_limit_size%2Cdata_volume_alert_percent%2Cdata_volume_limit_unit%2Croam_setting_option%2Cupg_roam_switch%2Cssid%2Cwifi_enable%2Cwifi_5g_enable%2Ccheck_web_conflict%2Cdial_mode%2Cprivacy_read_flag%2Cis_night_mode%2Cvpn_conn_status%2Cwan_connect_status%2Csms_received_flag%2Csts_received_flag%2Csms_unread_num%2Cwifi_chip1_ssid2_access_sta_num%2Cwifi_chip2_ssid2_access_sta_num&multi_data=1"
            response = self.request_with_session('GET', cmd_url, headers=header)
            data = response.data.decode('utf-8')
            logger.info("Fetched ZTE info 2 successfully")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch ZTE info 2: {e}")
            return ""

    def zteinfo3(self):
        logger.debug("Fetching comprehensive ZTE info (zteinfo3) with hybrid splitting and fault tolerance")
        try:
            # Use authentication/session from instance
            header = {
                "Host": self.ip,
                "Referer": f"{self.referer}index.html",
            }

            # Step 3: Parameter groups to fetch
            param_groups = {
                "system_info": (
                    "wa_inner_version,cr_version,loginfo,new_version_state,current_upgrade_state,"
                    "is_mandatory,modem_main_state,pin_status,signalbar,imei,"
                    "imsi,iccid,hardware_version,wa_version,sim_imsi,mac_address,web_version,LocalDomain"
                ),
                "radio_network": (
                    "network_type,network_provider,network_provider_fullname,rmcc,rmnc,mdm_mcc,mdm_mnc,"
                    "rssi,ecio,ecio_1,ecio_2,ecio_3,ecio_4,rscp,rscp_1,rscp_2,rscp_3,rscp_4,lte_rsrp,"
                    "lte_rsrp_1,lte_rsrp_2,lte_rsrp_3,lte_rsrp_4,lte_rsrq,lte_snr,lte_snr_1,lte_snr_2,lte_snr_3,lte_snr_4,"
                    "lte_rssi,Z5g_rsrp,Z5g_rsrq,Z5g_snr,Z5g_SINR,Z5g_dlEarfcn,Z5g_CELL_ID,ZCELLINFO_band,"
                    "enodeb_id,lte_pci,lte_pci_lock,lte_band,lte_ca_pcell_band,lte_ca_scell_band,lte_ca_scell_info,"
                    "lte_multi_ca_scell_info,lte_multi_ca_scell_sig_info,lte_ca_scell_arfcn,lte_ca_scell_bandwidth,"
                    "lte_ca_pcell_bandwidth,lte_ca_pcell_arfcn,lte_ca_pcell_freq,lte_earfcn_lock,nr5g_action_band,"
                    "nr5g_action_channel,nr5g_action_nsa_band,nr5g_pci,nr5g_cell_id,nr_ca_pcell_band,nr_ca_pcell_freq,"
                    "nr5g_nsa_band_lock,nr5g_sa_band_lock,nr_multi_ca_scell_info,wan_active_band,wan_active_channel,"
                    "cell_id,tx_power,ngbr_cell_info,5g_rx0_rsrp,5g_rx1_rsrp"
                ),
                "connectivity": (
                    "wan_ipaddr,wan_apn,wan_connect_status,wan_lte_ca,opms_wan_mode,opms_wan_auto_mode,"
                    "ppp_status,pppoe_status,dial_mode,dhcp_wan_status,static_wan_status,static_wan_ipaddr,"
                    "ip_passthrough_enabled,vpn_conn_status,ppp_dial_conn_fail_counter"
                ),
                "ipv6_config": (
                    "ipv6_wan_ipaddr,pdp_type,ipv6_pdp_type,pdp_type_ui,ipv6_pdp_type_ui"
                ),
                "wifi": (
                    "wifi_enable,wifi_onoff_state,wifi_5g_enable,wifi_chip_temp,wifi_dfs_status,ssid,EX_SSID1,EX_wifi_profile,"
                    "m_ssid_enable,m_SSID2,wifi_chip1_ssid1_ssid,wifi_chip2_ssid1_ssid,wifi_chip1_ssid1_auth_mode,"
                    "wifi_chip2_ssid1_auth_mode,wifi_chip1_ssid2_access_sta_num,wifi_chip2_ssid2_access_sta_num,"
                    "wifi_chip1_ssid1_access_sta_num,wifi_chip2_ssid1_access_sta_num,wifi_chip1_ssid2_max_access_num,"
                    "wifi_chip2_ssid2_max_access_num,wifi_chip1_ssid1_wifi_coverage,wifi_access_sta_num,sta_ip_status,"
                    "guest_switch"
                ),
                "wifi_advanced": (
                    "wifi_chip1_ssid1_password_encode,wifi_chip2_ssid1_password_encode,wifi_chip1_ssid1_switch_onoff,"
                    "wifi_chip2_ssid1_switch_onoff,wifi_chip1_ssid2_switch_onoff,wifi_chip2_ssid2_switch_onoff,"
                    "wifi_chip1_ssid1_max_access_num,wifi_chip2_ssid1_max_access_num,wifi_chip2_ssid2_max_access_num,"
                    "wifi_chip2_ssid2_ssid,wifi_chip1_ssid2_ssid,wifi_lbd_enable,m_HideSSID,station_ip_addr"
                ),
                "power_sensors": (
                    "battery_value,battery_pers,battery_charging,battery_vol_percent,pm_modem_5g,pm_sensor_5g,"
                    "pm_sensor_mdm,pm_sensor_ambient,pm_sensor_pa1"
                ),
                "misc": (
                    "monthly_rx_bytes,monthly_tx_bytes,monthly_time,realtime_rx_bytes,realtime_tx_bytes,"
                    "realtime_rx_thrpt,realtime_tx_thrpt,realtime_time,date_month,data_volume_limit_switch,"
                    "data_volume_limit_size,data_volume_alert_percent,data_volume_limit_unit,roam_setting_option,"
                    "upg_roam_switch,privacy_read_flag,is_night_mode,check_web_conflict,station_mac,lan_ipaddr,"
                    "sms_received_flag,sms_unread_num,sts_received_flag,spn_name_data,spn_b1_flag,spn_b2_flag,"
                    "simcard_roam,"
                    "flux_realtime_tx_bytes,flux_realtime_rx_bytes,flux_realtime_time,"
                    "flux_realtime_tx_thrpt,flux_realtime_rx_thrpt,"
                    "flux_monthly_rx_bytes,flux_monthly_tx_bytes,flux_monthly_time,"
                    "flux_data_volume_limit_size,flux_data_volume_alert_percent,flux_data_volume_limit_unit"
                ),
                "dns_config": (
                    "dns_mode,prefer_dns_manual,standby_dns_manual"
                ),
                "unclassified": (
                    "RadioOff,apn_interface_version,bandwidth,"
                    "network_information,Lte_ca_status"
                )
            }

            # Step 4: Prepare for chunked requests
            combined_data = {}
            failed_groups = {}
            partial = False
            url_base = f"{self.protocol}://{self.ip}/goform/goform_get_cmd_process?isTest=false&multi_data=1&cmd="

            for group_name, param_str in param_groups.items():
                param_list = param_str.split(",")
                chunks = [param_list[i:i + 60] for i in range(0, len(param_list), 60)]

                for idx, chunk in enumerate(chunks):
                    cmd_encoded = quote(",".join(chunk))
                    url = url_base + cmd_encoded
                    success = False

                    for attempt in range(3):  # max 3 retries
                        try:
                            response = self.request_with_session('GET', url, headers=header)
                            raw_data = response.data.decode('utf-8')
                            parsed = json.loads(raw_data)
                            combined_data.update(parsed)
                            empty_params = sum(1 for val in parsed.values() if val == "")
                            logger.debug(f"✅ {group_name} (chunk {idx+1}) fetched with {len(parsed)} keys ({empty_params} empty)")
                            success = True
                            break
                        except Exception as ex:
                            logger.warning(f"⚠️ {group_name} (chunk {idx+1}) failed on attempt {attempt+1}: {ex}")
                            time.sleep(1.5 * (attempt + 1))

                    if not success:
                        failed_groups[f"{group_name}_chunk_{idx+1}"] = f"Failed after 3 attempts"
                        partial = True

                    # No cookie update logic needed

            # Step 5: Partial detection
            if partial:
                logger.warning(f"⚠️ zteinfo3: Partial data returned; failed chunks: {list(failed_groups.keys())}")
                combined_data["__partial"] = True
                combined_data["__errors__"] = failed_groups

            # Convert all values to strings to ensure Home Assistant compatibility
            for key, value in combined_data.items():
                if not isinstance(value, str):
                    try:
                        combined_data[key] = str(value)
                    except Exception:
                        combined_data[key] = "N/A"

            logger.info("✅ Fetched ZTE info using hybrid strategy")
            return json.dumps(combined_data)

        except Exception as e:
            logger.error(f"❌ Critical failure in zteinfo3: {e}")
            return ""

    def zteinfo4(self):
        """
        Fetch ZTE modem info for both 'station_list' (WiFi) and 'lan_station_list' (LAN),
        tag each with type, and return a merged list under 'all_devices'.
        """
        logger.debug("Fetching ZTE info: station_list and lan_station_list (tagged & merged)")
        try:
            header = {
                "Host": self.ip,
                "Referer": f"{self.referer}index.html",
            }

            combined_data = {}

            def normalize_client_list(raw_value):
                """Normalize firmware-specific list payloads to list[dict]."""
                if isinstance(raw_value, list):
                    return [item for item in raw_value if isinstance(item, dict)]

                if isinstance(raw_value, str):
                    text = raw_value.strip()
                    if not text or text.lower() in ("null", "none", "[]"):
                        return []
                    try:
                        decoded = json.loads(text)
                        if isinstance(decoded, list):
                            return [item for item in decoded if isinstance(item, dict)]
                        if isinstance(decoded, dict):
                            for nested_key in ("list", "items", "devices", "clients"):
                                nested = decoded.get(nested_key)
                                if isinstance(nested, list):
                                    return [item for item in nested if isinstance(item, dict)]
                    except Exception:
                        return []

                if isinstance(raw_value, dict):
                    for nested_key in ("list", "items", "devices", "clients"):
                        nested = raw_value.get(nested_key)
                        if isinstance(nested, list):
                            return [item for item in nested if isinstance(item, dict)]

                return []

            for param in ["station_list", "lan_station_list"]:
                cmd_str = quote(param)
                url = f"{self.protocol}://{self.ip}/goform/goform_get_cmd_process?isTest=false&cmd={cmd_str}"
                response = self.request_with_session('GET', url, headers=header)
                raw_data = response.data.decode('utf-8')

                # No cookie update logic needed

                try:
                    parsed = json.loads(raw_data)

                    raw_clients = parsed.get(param, [])
                    clients = normalize_client_list(raw_clients)

                    # Firmware fallback keys
                    if not clients:
                        alt_candidates = [
                            "wireless_access_list_info" if param == "station_list" else "lan_access_list_info",
                            "clients",
                            "devices",
                            "list",
                            "items",
                        ]
                        for alt_key in alt_candidates:
                            clients = normalize_client_list(parsed.get(alt_key, []))
                            if clients:
                                break

                    # Tag each device with type: WiFi or LAN
                    for item in clients:
                        item["type"] = "WiFi" if param == "station_list" else "LAN"

                    combined_data[param] = clients
                    logger.debug(f"Fetched {param} with {len(clients)} entries")
                except Exception as ex:
                    logger.warning(f"Failed to parse {param}: {ex}")
                    combined_data[param] = []

            # ✅ Merge all into one list
            combined_data["all_devices"] = combined_data["station_list"] + combined_data["lan_station_list"]
            logger.info(f"Fetched and merged {len(combined_data['all_devices'])} total devices")

            return json.dumps(combined_data)

        except Exception as e:
            logger.error(f"Failed to fetch ZTE info: {e}")
            return ""


    def ztesmsinfo(self):
        logger.debug("Fetching ZTE SMS info")
        try:
            header = {
                "Host": self.ip,
                "Referer": f"{self.referer}index.html",
            }
            cmd_url = f"{self.protocol}://{self.ip}/goform/goform_get_cmd_process?isTest=false&cmd=sms_capacity_info"
            response = self.request_with_session('GET', cmd_url, headers=header)
            data = response.data.decode('utf-8')

            # Parse the response JSON
            data_json = json.loads(data)
            logger.info("Fetched ZTE SMS info successfully")

            # Calculate sms_capacity_left
            sms_nv_total = int(data_json.get("sms_nv_total", 0))
            sms_nv_rev_total = int(data_json.get("sms_nv_rev_total", 0))
            sms_nv_send_total = int(data_json.get("sms_nv_send_total", 0))
            sms_capacity_left = sms_nv_total - sms_nv_rev_total - sms_nv_send_total

            # Add the new key-value pair
            data_json["sms_capacity_left"] = str(sms_capacity_left)
            return json.dumps(data_json)
        except Exception as e:
            logger.error(f"Failed to fetch SMS info: {e}")
            return ""

    def ztereboot(self):
        logger.debug("Rebooting ZTE router")
        try:
            AD = getattr(self, "_zte_auth_AD", None)
            header = {"Referer": self.referer}
            payload = {
                'isTest': 'false',
                'goformId': 'REBOOT_DEVICE',
                'AD': AD
            }
            encoded_payload = urllib.parse.urlencode(payload)
            body = encoded_payload.encode('utf-8')
            r = self.request_with_session('POST', self.referer + "goform/goform_set_cmd_process", headers=header, body=body)
            logger.info(f"Router rebooted with status code: {r.status}")
            return r.status
        except Exception as e:
            logger.error(f"Failed to reboot router: {e}")
            return None

    def deletesms(self, msg_id):
        logger.debug(f"Deleting SMS with ID: {msg_id}")
        try:
            AD = getattr(self, "_zte_auth_AD", None)
            header = {"Referer": self.referer}
            payload = {
                'isTest': 'false',
                'goformId': 'DELETE_SMS',
                'msg_id': msg_id,
                'AD': AD
            }
            encoded_payload = urllib.parse.urlencode(payload)
            body = encoded_payload.encode('utf-8')
            r = self.request_with_session('POST', self.referer + "goform/goform_set_cmd_process", headers=header, body=body)
            logger.info(f"SMS deleted with status code: {r.status}")
            return r.status
        except Exception as e:
            logger.error(f"Failed to delete SMS: {e}")
            return None

    def parsesms(self):
        logger.debug("Starting SMS parsing process")
        try:
            # RED-encrypted firmware requires key negotiation before fetching SMS payload.
            red_ready = self._setup_red_crypto()

            header = {"Referer": self.referer}
            payload = {
                'cmd': 'sms_data_total',
                'page': '0',
                'data_per_page': '5000',
                'mem_store': '1',
                'tags': '10',
                'order_by': 'order by id desc'
            }
            encoded_payload = urllib.parse.urlencode(payload)
            url = self.referer + "goform/goform_get_cmd_process?" + encoded_payload
            r = self.request_with_session('GET', url, headers=header)
            response_text = r.data.decode('utf-8', errors='replace')
            logger.debug(f"Raw SMS response: {repr(response_text[:300])}...")  # Preview first 300 chars
            # Clean invalid characters
            sanitized_text = clean_control_chars(response_text)
            sanitized_text = sanitized_text.replace('HR�Telekom', 'HR Telekom')  # Specific fix
            try:
                response_json = json.loads(sanitized_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decoding failed: {e}")
                return ""
            # Ensure 'messages' exists and is a list
            if 'messages' not in response_json or not isinstance(response_json['messages'], list):
                logger.warning("'messages' key is missing or invalid in SMS response; defaulting to empty list.")
                response_json['messages'] = []
            messages = response_json['messages']
            logger.info(f"Fetched {len(messages)} SMS messages")
            decode_errors = 0
            decrypted_any = False

            def _decode_messages(items):
                nonlocal decode_errors, decrypted_any
                for item in items:
                    try:
                        original_content = item.get('content', '') or ''
                        original_number = item.get('number', '') or ''

                        # Legacy mode: UCS2 hex directly from router.
                        if self._looks_like_hex_ucs2(original_content):
                            item['content'] = hex2utf(original_content)
                            decrypted_any = True
                            continue

                        # Newer firmware mode: RED-encrypted base64 payload.
                        if red_ready:
                            decrypted_content = self._red_decrypt_value(original_content)
                            if decrypted_content and self._looks_like_hex_ucs2(decrypted_content):
                                item['content'] = hex2utf(decrypted_content)
                                decrypted_any = True
                            elif decrypted_content:
                                item['content'] = decrypted_content
                                decrypted_any = True

                            decrypted_number = self._red_decrypt_value(original_number)
                            if decrypted_number:
                                item['number'] = decrypted_number
                                decrypted_any = True
                    except Exception as e:
                        logger.warning(f"Failed to decode SMS content: {e}")
                        decode_errors += 1

            _decode_messages(messages)

            # Some RED firmwares require one payload fetch after key setup in same session.
            if red_ready and messages and not decrypted_any:
                logger.debug("SMS decrypt yielded no plaintext; refreshing RED session and refetching once")
                self._red_key_bytes = None
                red_ready = self._setup_red_crypto()
                if red_ready:
                    r = self.request_with_session('GET', url, headers=header)
                    response_text = r.data.decode('utf-8', errors='replace')
                    sanitized_text = clean_control_chars(response_text).replace('HR�Telekom', 'HR Telekom')
                    try:
                        retry_json = json.loads(sanitized_text)
                        retry_messages = retry_json.get('messages', [])
                        if isinstance(retry_messages, list):
                            messages = retry_messages
                            response_json['messages'] = messages
                            _decode_messages(messages)
                    except Exception as retry_err:
                        logger.debug(f"SMS retry parse failed: {retry_err}")

            if decode_errors:
                logger.warning(f"{decode_errors} messages failed to decode cleanly.")
            # Return dummy message if no SMS exists
            if not messages:
                dummy_message = {
                    'id': '999',
                    'number': 'DUMMY',
                    'content': 'NO SMS IN MEMORY',
                    'tag': '1',
                    'date': datetime.now().strftime('%y,%m,%d,%H,%M,%S,+2'),
                    'draft_group_id': '',
                    'received_all_concat_sms': '1',
                    'concat_sms_total': '0',
                    'concat_sms_received': '0',
                    'sms_class': '4'
                }
                response_json['messages'].append(dummy_message)
            logger.info("Parsed all SMS messages successfully")
            return json.dumps(response_json, indent=2)
        except Exception as e:
            logger.error(f"Failed to parse SMS: {e}")
            return ""

    def _looks_like_hex_ucs2(self, value):
        if not value or len(value) % 4 != 0:
            return False
        return re.fullmatch(r"[0-9A-Fa-f]+", value) is not None

    def _setup_red_crypto(self):
        if getattr(self, "_red_key_bytes", None):
            return True
        try:
            def _normalize_pem(pem_text):
                if not pem_text:
                    return ""
                pem_text = pem_text.strip()
                begin = "-----BEGIN PUBLIC KEY-----"
                end = "-----END PUBLIC KEY-----"
                if begin in pem_text and end in pem_text and "\n" not in pem_text:
                    core = pem_text.replace(begin, "").replace(end, "").strip()
                    chunks = [core[i:i + 64] for i in range(0, len(core), 64)]
                    return begin + "\n" + "\n".join(chunks) + "\n" + end + "\n"
                return pem_text

            AD = getattr(self, "_zte_auth_AD", None)
            base_urls = [self.referer, f"http://{self.ip}/", f"https://{self.ip}/"]
            seen = set()

            for base_url in base_urls:
                if base_url in seen:
                    continue
                seen.add(base_url)

                header = {"Referer": base_url}
                url = base_url + "goform/goform_get_cmd_process?isTest=false&cmd=web_crt_get"
                r = self.request_with_session('GET', url, headers=header)
                raw_cert_reply = r.data.decode('utf-8', errors='replace')
                payload = json.loads(raw_cert_reply)
                pem = _normalize_pem(payload.get("result", ""))
                if not pem or "BEGIN PUBLIC KEY" not in pem:
                    logger.debug(f"RED crypto unavailable on {base_url}: web_crt_get reply={raw_cert_reply}")
                    continue

                os_hex = secrets.token_hex(32)
                pubkey = serialization.load_pem_public_key(pem.encode('utf-8'))
                encrypted = pubkey.encrypt(os_hex.encode('ascii'), asym_padding.PKCS1v15())
                web_enstr = base64.b64encode(encrypted).decode('ascii')

                payload_variants = [
                    {
                        'isTest': 'false',
                        'goformId': 'web_http_enstr_set',
                        'web_enstr': web_enstr,
                        'AD': self.get_AD() or AD
                    },
                    {
                        'isTest': 'false',
                        'goformId': 'web_http_enstr_set',
                        'web_enstr': web_enstr,
                    },
                ]
                for idx, payload_set in enumerate(payload_variants, start=1):
                    body = urllib.parse.urlencode(payload_set).encode('utf-8')
                    rr = self.request_with_session(
                        'POST',
                        base_url + "goform/goform_set_cmd_process",
                        headers=header,
                        body=body,
                    )
                    reply = rr.data.decode('utf-8', errors='replace')
                    data = json.loads(reply)
                    if data.get("result") == "success":
                        self._red_key_bytes = bytes.fromhex(os_hex)
                        logger.debug(f"RED crypto session established (base={base_url}, variant={idx})")
                        return True
                    logger.debug(f"RED crypto set failed (base={base_url}, variant={idx}): {reply}")
            return False
        except Exception as e:
            logger.debug(f"RED crypto setup failed: {e}")
            return False

    def _red_encrypt_value(self, plain_text):
        if not getattr(self, "_red_key_bytes", None):
            return plain_text
        if plain_text is None:
            plain_text = ""
        iv = secrets.token_bytes(12)
        encrypted = AESGCM(self._red_key_bytes).encrypt(iv, plain_text.encode('utf-8'), None)
        cipher = encrypted[:-16]
        tag = encrypted[-16:]
        return base64.b64encode(iv + tag + cipher).decode('ascii')

    def _red_decrypt_value(self, encoded_text):
        if not getattr(self, "_red_key_bytes", None):
            return None
        if not encoded_text:
            return None
        try:
            raw = base64.b64decode(encoded_text)
            if len(raw) < 28:
                return None
            iv = raw[:12]
            # Main observed format: iv(12) + tag(16) + cipher
            tag = raw[12:28]
            cipher = raw[28:]
            plain = AESGCM(self._red_key_bytes).decrypt(iv, cipher + tag, None)
            return plain.decode('utf-8', errors='replace')
        except Exception:
            try:
                # Compatibility fallback: iv(12) + cipher + tag(16)
                raw = base64.b64decode(encoded_text)
                if len(raw) < 28:
                    return None
                iv = raw[:12]
                cipher = raw[12:-16]
                tag = raw[-16:]
                plain = AESGCM(self._red_key_bytes).decrypt(iv, cipher + tag, None)
                return plain.decode('utf-8', errors='replace')
            except Exception:
                return None

    def connect_data(self):
        logger.debug("Connecting to data network")
        try:
            AD = getattr(self, "_zte_auth_AD", None)
            header = {"Referer": self.referer}
            payload = {
                'isTest': 'false',
                'goformId': 'CONNECT_NETWORK',
                'AD': AD
            }
            encoded_payload = urllib.parse.urlencode(payload)
            body = encoded_payload.encode('utf-8')
            r = self.request_with_session('POST', self.referer + "goform/goform_set_cmd_process", headers=header, body=body)
            logger.info(f"Connected to data network with status code: {r.status}")
            return r.status
        except Exception as e:
            logger.error(f"Failed to connect to data network: {e}")
            return None

    def disconnect_data(self):
        logger.debug("Disconnecting from data network")
        try:
            AD = getattr(self, "_zte_auth_AD", None)
            header = {"Referer": self.referer}
            payload = {
                'isTest': 'false',
                'goformId': 'DISCONNECT_NETWORK',
                'AD': AD
            }
            encoded_payload = urllib.parse.urlencode(payload)
            body = encoded_payload.encode('utf-8')
            r = self.request_with_session('POST', self.referer + "goform/goform_set_cmd_process", headers=header, body=body)
            logger.info(f"Disconnected from data network with status code: {r.status}")
            return r.status
        except Exception as e:
            logger.error(f"Failed to disconnect from data network: {e}")
            return None

    def setdata_mode(self, BearerPreference):
        logger.debug(f"Setting data mode with BearerPreference: {BearerPreference}")
        try:
            AD = getattr(self, "_zte_auth_AD", None)
            header = {"Referer": self.referer}
            payload = {
                'isTest': 'false',
                'goformId': 'SET_BEARER_PREFERENCE',
                'BearerPreference': BearerPreference,
                'AD': AD
            }
            encoded_payload = urllib.parse.urlencode(payload)
            body = encoded_payload.encode('utf-8')
            r = self.request_with_session('POST', self.referer + "goform/goform_set_cmd_process", headers=header, body=body)
            logger.info(f"Set data mode '{BearerPreference}' with status code: {r.status}")
            return r.status
        except Exception as e:
            logger.error(f"Failed to set data mode '{BearerPreference}': {e}")
            return None



# Global variables for SMS sending
getsmstime = get_sms_time()
getsmstimeEncoded = urllib.parse.quote(getsmstime, safe="")
#phoneNumber = '13909'  # enter phone number here
#phoneNumberEncoded = urllib.parse.quote(phoneNumber, safe="")
#message = 'BRZINA'  # enter your message here
#messageEncoded = gsm_encode(message)
#outputmessage = messageEncoded.decode()

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: script.py ip password command1[,command2,...] [username]")
        sys.exit(1)

    ip = sys.argv[1]
    password = sys.argv[2]
    commands = sys.argv[3].split(',')
    print(f"Commands received: {commands}")
    username = sys.argv[4] if len(sys.argv) > 4 else None
    phone_number = sys.argv[5] if len(sys.argv) > 5 else None
    message = sys.argv[6] if len(sys.argv) > 6 else None

    zte = zteRouter(ip, username, password)

    # Single authentication before executing the commands
    zte.authenticate()

    results = {}

    for command in commands:
        try:
            cmd_id = int(command)
        except Exception:
            results[command] = f"Invalid command: {command}"
            continue
        try:
            if cmd_id == 1:
                results[cmd_id] = json.loads(zte.zteinfo())
            elif cmd_id == 2:
                results[cmd_id] = json.loads(zte.zteinfo2())
            elif cmd_id == 3:
                results[cmd_id] = json.loads(zte.ztesmsinfo())
            elif cmd_id == 4:
                results[cmd_id] = zte.ztereboot()
            elif cmd_id == 5:
                result = zte.parsesms()
                if result:
                    data = json.loads(result)
                    ids = [msg['id'] for msg in data.get('messages', [])]
                    if ids:
                        formatted_ids = ";".join(ids)
                        logger.info(f"Deleting SMS messages with IDs: {formatted_ids}")
                        result = zte.deletesms(formatted_ids)
                        results[cmd_id] = {"deleted_ids": ids, "status": result}
                    else:
                        logger.info("No SMS in memory to delete")
                        results[cmd_id] = {"deleted_ids": [], "status": "No SMS"}
                else:
                    logger.warning("Failed to parse SMS for deletion")
                    results[cmd_id] = {"error": "parsesms() returned empty or invalid data"}
            elif cmd_id == 6:
                result = zte.parsesms()
                if result:
                    data = json.loads(result)
                    messages = data.get("messages", [])
                    if messages:
                        first_message = messages[0]
                        results[cmd_id] = first_message
                    else:
                        dummy_message = {
                            'id': '999',
                            'number': 'DUMMY',
                            'content': 'NO SMS IN MEMORY',
                            'tag': '1',
                            'date': '24,07,18,09,39,05,+8',
                            'draft_group_id': '',
                            'received_all_concat_sms': '1',
                            'concat_sms_total': '0',
                            'concat_sms_received': '0',
                            'sms_class': '4'
                        }
                        results[cmd_id] = dummy_message
                else:
                    logger.warning("Failed to parse SMS data for reading")
                    results[cmd_id] = {"error": "parsesms() returned empty or invalid data"}
            elif cmd_id == 7:
                results[cmd_id] = json.loads(zte.zteinfo3())
            elif cmd_id == 8:
                if len(commands) > 1:
                    results[cmd_id] = "SMS sending not supported in multi-command mode."
                else:
                    if phone_number and message:
                        logger.info(f"Sending SMS to {phone_number} with message: {message}")
                        result = zte.sendsms(phone_number, message)
                        results[cmd_id] = result
                    else:
                        logger.error(f"Phone number or message not provided. Phone: {phone_number}, Message: {message}")
                        results[cmd_id] = "Phone number or message not provided for sending SMS"
            elif cmd_id == 9:
                results[cmd_id] = zte.connect_data()
            elif cmd_id == 10:
                results[cmd_id] = zte.disconnect_data()
            elif cmd_id == 11:
                results[cmd_id] = zte.setdata_mode("Only_LTE")
            elif cmd_id == 12:
                results[cmd_id] = zte.setdata_mode("4G_AND_5G")
            elif cmd_id == 13:
                results[cmd_id] = zte.setdata_mode("LTE_AND_5G")
            elif cmd_id == 14:
                results[cmd_id] = zte.setdata_mode("Only_5G")
            elif cmd_id == 15:
                results[cmd_id] = zte.setdata_mode("WL_AND_5G")
            elif cmd_id == 16:
                results[cmd_id] = json.loads(zte.zteinfo4())
            else:
                results[cmd_id] = f"Invalid command: {cmd_id}"
        except Exception as e:
            results[cmd_id] = f"Error: {e}"

    print(json.dumps(results, indent=2))
