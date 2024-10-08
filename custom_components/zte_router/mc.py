import hashlib
from datetime import datetime
import binascii
import json
import sys
import time
import urllib3
import urllib
import logging
from http.cookies import SimpleCookie
import ssl
import socket
from cryptography import x509
from cryptography.hazmat.backends import default_backend

# Disable warnings for insecure connections
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure the logger
logger = logging.getLogger('homeassistant.components.zte_router')

if __name__ == "__main__":
    # Configure logging when run directly
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()  # Defaults to stderr
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
else:
    # Suppress logging when imported
    logger.setLevel(logging.WARNING)

gsm = ("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
       "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ`¿abcdefghijklmnopqrstuvwxyzäöñüà")
ext = ("``````````````````^```````````````````{}`````\\````````````[~]`"
       "|````````````````````````````````````€``````````````````````````")

# Create a PoolManager instance to handle HTTP requests
s = urllib3.PoolManager(cert_reqs='CERT_NONE')

def get_sms_time():
    logger.debug("Generating SMS time")
    return datetime.now().strftime("%y;%m;%d;%H;%M;%S;+2")

def gsm_encode(plaintext):
    logger.debug(f"Encoding GSM message: {plaintext}")
    res = bytearray()
    for c in plaintext:
        res.append(0)
        idx = gsm.find(c)
        if idx != -1:
            res.append(idx)
            continue
        idx = ext.find(c)
        if idx != -1:
            res.append(27)
            res.append(idx)
    return binascii.hexlify(res)

class zteRouter:
    def __init__(self, ip, username, password):
        self.ip = ip
        self.protocol = "http"  # default to http
        self.username = username
        self.password = password
        self.cookies = {}  # Initialize cookies dictionary
        logger.info(f"Initializing ZTE Router with IP {ip}, Username: {username}, Password: {password}")
        self.try_set_protocol()
        self.referer = f"{self.protocol}://{self.ip}/"
        self.js = """/*\n * A JavaScript implementation of the RSA Data Security, Inc. MD5 Message\n * Digest Algorithm, as defined in RFC 1321.\n * Version 2.1 Copyright (C) Paul Johnston 1999 - 2002.\n * Other contributors: Greg Holt, Andrew Kepert, Ydnar, Lostinet\n * Distributed under the BSD License\n * See http://pajhome.org.uk/crypt/md5 for more info.\n */\n\n/*\n * Configurable variables. You may need to tweak these to be compatible with\n * the server-side, but the defaults work in most cases.\n */\nvar hexcase = 0;  /* hex output format. 0 - lowercase; 1 - uppercase        */\nvar b64pad  = ""; /* base-64 pad character. "=" for strict RFC compliance   */\nvar chrsz   = 8;  /* bits per input character. 8 - ASCII; 16 - Unicode      */\n\n/*\n * These are the functions you\'ll usually want to call\n * They take string arguments and return either hex or base-64 encoded strings\n */\nfunction hex_md5(s){ return binl2hex(core_md5(str2binl(s), s.length * chrsz));}\nfunction b64_md5(s){ return binl2b64(core_md5(str2binl(s), s.length * chrsz));}\nfunction str_md5(s){ return binl2str(core_md5(str2binl(s), s.length * chrsz));}\nfunction hex_hmac_md5(key, data) { return binl2hex(core_hmac_md5(key, data)); }\nfunction b64_hmac_md5(key, data) { return binl2b64(core_hmac_md5(key, data)); }\nfunction str_hmac_md5(key, data) { return binl2str(core_hmac_md5(key, data)); }\n\n/*\n * Perform a simple self-test to see if the VM is working\n */\nfunction md5_vm_test()\n{\n  return hex_md5("abc") == "900150983cd24fb0d6963f7d28e17f72";\n}\n\n/*\n * Calculate the MD5 of an array of little-endian words, and a bit length\n */\nfunction core_md5(x, len)\n{\n  /* append padding */\n  x[len >> 5] |= 0x80 << ((len) % 32);\n  x[(((len + 64) >>> 9) << 4) + 14] = len;\n\n  var a =  1732584193;\n  var b = -271733879;\n  var c = -1732584194;\n  var d =  271733878;\n\n  for(var i = 0; i < x.length; i += 16)\n  {\n    var olda = a;\n    var oldb = b;\n    var oldc = c;\n    var oldd = d;\n\n    a = md5_ff(a, b, c, d, x[i+ 0], 7 , -680876936);\n    d = md5_ff(d, a, b, c, x[i+ 1], 12, -389564586);\n    c = md5_ff(c, d, a, b, x[i+ 2], 17,  606105819);\n    b = md5_ff(b, c, d, a, x[i+ 3], 22, -1044525330);\n    a = md5_ff(a, b, c, d, x[i+ 4], 7 , -176418897);\n    d = md5_ff(d, a, b, c, x[i+ 5], 12,  1200080426);\n    c = md5_ff(c, d, a, b, x[i+ 6], 17, -1473231341);\n    b = md5_ff(b, c, d, a, x[i+ 7], 22, -45705983);\n    a = md5_ff(a, b, c, d, x[i+ 8], 7 ,  1770035416);\n    d = md5_ff(d, a, b, c, x[i+ 9], 12, -1958414417);\n    c = md5_ff(c, d, a, b, x[i+10], 17, -42063);\n    b = md5_ff(b, c, d, a, x[i+11], 22, -1990404162);\n    a = md5_ff(a, b, c, d, x[i+12], 7 ,  1804603682);\n    d = md5_ff(d, a, b, c, x[i+13], 12, -40341101);\n    c = md5_ff(c, d, a, b, x[i+14], 17, -1502002290);\n    b = md5_ff(b, c, d, a, x[i+15], 22,  1236535329);\n\n    a = md5_gg(a, b, c, d, x[i+ 1], 5 , -165796510);\n    d = md5_gg(d, a, b, c, x[i+ 6], 9 , -1069501632);\n    c = md5_gg(c, d, a, b, x[i+11], 14,  643717713);\n    b = md5_gg(b, c, d, a, x[i+ 0], 20, -373897302);\n    a = md5_gg(a, b, c, d, x[i+ 5], 5 , -701558691);\n    d = md5_gg(d, a, b, c, x[i+10], 9 ,  38016083);\n    c = md5_gg(c, d, a, b, x[i+15], 14, -660478335);\n    b = md5_gg(b, c, d, a, x[i+ 4], 20, -405537848);\n    a = md5_gg(a, b, c, d, x[i+ 9], 5 ,  568446438);\n    d = md5_gg(d, a, b, c, x[i+14], 9 , -1019803690);\n    c = md5_gg(c, d, a, b, x[i+ 3], 14, -187363961);\n    b = md5_gg(b, c, d, a, x[i+ 8], 20,  1163531501);\n    a = md5_gg(a, b, c, d, x[i+13], 5 , -1444681467);\n    d = md5_gg(d, a, b, c, x[i+ 2], 9 , -51403784);\n    c = md5_gg(c, d, a, b, x[i+ 7], 14,  1735328473);\n    b = md5_gg(b, c, d, a, x[i+12], 20, -1926607734);\n\n    a = md5_hh(a, b, c, d, x[i+ 5], 4 , -378558);\n    d = md5_hh(d, a, b, c, x[i+ 8], 11, -2022574463);\n    c = md5_hh(c, d, a, b, x[i+11], 16,  1839030562);\n    b = md5_hh(b, c, d, a, x[i+14], 23, -35309556);\n    a = md5_hh(a, b, c, d, x[i+ 1], 4 , -1530992060);\n    d = md5_hh(d, a, b, c, x[i+ 4], 11,  1272893353);\n    c = md5_hh(c, d, a, b, x[i+ 7], 16, -155497632);\n    b = md5_hh(b, c, d, a, x[i+10], 23, -1094730640);\n    a = md5_hh(a, b, c, d, x[i+13], 4 ,  681279174);\n    d = md5_hh(d, a, b, c, x[i+ 0], 11, -358537222);\n    c = md5_hh(c, d, a, b, x[i+ 3], 16, -722521979);\n    b = md5_hh(b, c, d, a, x[i+ 6], 23,  76029189);\n    a = md5_hh(a, b, c, d, x[i+ 9], 4 , -640364487);\n    d = md5_hh(d, a, b, c, x[i+12], 11, -421815835);\n    c = md5_hh(c, d, a, b, x[i+15], 16,  530742520);\n    b = md5_hh(b, c, d, a, x[i+ 2], 23, -995338651);\n\n    a = md5_ii(a, b, c, d, x[i+ 0], 6 , -198630844);\n    d = md5_ii(d, a, b, c, x[i+ 7], 10,  1126891415);\n    c = md5_ii(c, d, a, b, x[i+14], 15, -1416354905);\n    b = md5_ii(b, c, d, a, x[i+ 5], 21, -57434055);\n    a = md5_ii(a, b, c, d, x[i+12], 6 ,  1700485571);\n    d = md5_ii(d, a, b, c, x[i+ 3], 10, -1894986606);\n    c = md5_ii(c, d, a, b, x[i+10], 15, -1051523);\n    b = md5_ii(b, c, d, a, x[i+ 1], 21, -2054922799);\n    a = md5_ii(a, b, c, d, x[i+ 8], 6 ,  1873313359);\n    d = md5_ii(d, a, b, c, x[i+15], 10, -30611744);\n    c = md5_ii(c, d, a, b, x[i+ 6], 15, -1560198380);\n    b = md5_ii(b, c, d, a, x[i+13], 21,  1309151649);\n    a = md5_ii(a, b, c, d, x[i+ 4], 6 , -145523070);\n    d = md5_ii(d, a, b, c, x[i+11], 10, -1120210379);\n    c = md5_ii(c, d, a, b, x[i+ 2], 15,  718787259);\n    b = md5_ii(b, c, d, a, x[i+ 9], 21, -343485551);\n\n    a = safe_add(a, olda);\n    b = safe_add(b, oldb);\n    c = safe_add(c, oldc);\n    d = safe_add(d, oldd);\n  }\n  return Array(a, b, c, d);\n\n}\n\n/*\n * These functions implement the four basic operations the algorithm uses.\n */\nfunction md5_cmn(q, a, b, x, s, t)\n{\n  return safe_add(bit_rol(safe_add(safe_add(a, q), safe_add(x, t)), s),b);\n}\nfunction md5_ff(a, b, c, d, x, s, t)\n{\n  return md5_cmn((b & c) | ((~b) & d), a, b, x, s, t);\n}\nfunction md5_gg(a, b, c, d, x, s, t)\n{\n  return md5_cmn((b & d) | (c & (~d)), a, b, x, s, t);\n}\nfunction md5_hh(a, b, c, d, x, s, t)\n{\n  return md5_cmn(b ^ c ^ d, a, b, x, s, t);\n}\nfunction md5_ii(a, b, c, d, x, s, t)\n{\n  return md5_cmn(c ^ (b | (~d)), a, b, x, s, t);\n}\n\n/*\n * Calculate the HMAC-MD5, of a key and some data\n */\nfunction core_hmac_md5(key, data)\n{\n  var bkey = str2binl(key);\n  if(bkey.length > 16) bkey = core_md5(bkey, key.length * chrsz);\n\n  var ipad = Array(16), opad = Array(16);\n  for(var i = 0; i < 16; i++)\n  {\n    ipad[i] = bkey[i] ^ 0x36363636;\n    opad[i] = bkey[i] ^ 0x5C5C5C5C;\n  }\n\n  var hash = core_md5(ipad.concat(str2binl(data)), 512 + data.length * chrsz);\n  return core_md5(opad.concat(hash), 512 + 128);\n}\n\n/*\n * Add integers, wrapping at 2^32. This uses 16-bit operations internally\n * to work around bugs in some JS interpreters.\n */\nfunction safe_add(x, y)\n{\n  var lsw = (x & 0xFFFF) + (y & 0xFFFF);\n  var msw = (x >> 16) + (y >> 16) + (lsw >> 16);\n  return (msw << 16) | (lsw & 0xFFFF);\n}\n\n/*\n * Bitwise rotate a 32-bit number to the left.\n */\nfunction bit_rol(num, cnt)\n{\n  return (num << cnt) | (num >>> (32 - cnt));\n}\n\n/*\n * Convert a string to an array of little-endian words\n * If chrsz is ASCII, characters >255 have their hi-byte silently ignored.\n */\nfunction str2binl(str)\n{\n  var bin = Array();\n  var mask = (1 << chrsz) - 1;\n  for(var i = 0; i < str.length * chrsz; i += chrsz)\n    bin[i>>5] |= (str.charCodeAt(i / chrsz) & mask) << (i%32);\n  return bin;\n}\n\n/*\n * Convert an array of little-endian words to a string\n */\nfunction binl2str(bin)\n{\n  var str = "";\n  var mask = (1 << chrsz) - 1;\n  for(var i = 0; i < bin.length * 32; i += chrsz)\n    str += String.fromCharCode((bin[i>>5] >>> (i % 32)) & mask);\n  return str;\n}\n\n/*\n * Convert an array of little-endian words to a hex string.\n */\nfunction binl2hex(binarray)\n{\n  var hex_tab = hexcase ? "0123456789ABCDEF" : "0123456789abcdef";\n  var str = "";\n  for(var i = 0; i < binarray.length * 4; i++)\n  {\n    str += hex_tab.charAt((binarray[i>>2] >> ((i%4)*8+4)) & 0xF) +\n           hex_tab.charAt((binarray[i>>2] >> ((i%4)*8  )) & 0xF);\n  }\n  return str;\n}\n\n/*\n * Convert an array of little-endian words to a base-64 string\n */\nfunction binl2b64(binarray)\n{\n  var tab = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";\n  var str = "";\n  for(var i = 0; i < binarray.length * 4; i += 3)\n  {\n    var triplet = (((binarray[i   >> 2] >> 8 * ( i   %4)) & 0xFF) << 16)\n                | (((binarray[i+1 >> 2] >> 8 * ((i+1)%4)) & 0xFF) << 8 )\n                |  ((binarray[i+2 >> 2] >> 8 * ((i+2)%4)) & 0xFF);\n    for(var j = 0; j < 4; j++)\n    {\n      if(i * 8 + j * 6 > binarray.length * 32) str += b64pad;\n      else str += tab.charAt((triplet >> 6*(3-j)) & 0x3F);\n    }\n  }\n  return str;\n}\nhex_md5(evalString)\n"""

    
    def get_certificate_info(self, hostname, port=443):
        logger.debug(f"Retrieving SSL certificate for {hostname}:{port}")
        context = ssl._create_unverified_context()
        context.check_hostname = False  # Ensure hostname checking is disabled
        try:
            with socket.create_connection((hostname, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    # Retrieve the certificate in binary form (DER)
                    der_cert = ssock.getpeercert(binary_form=True)
                    if der_cert is None:
                        logger.error("No certificate received")
                        return None
                    # Convert DER to PEM format
                    pem_cert = ssl.DER_cert_to_PEM_cert(der_cert)
                    logger.info(f"SSL certificate for {hostname}:{port} retrieved successfully")
                    logger.info(f"Certificate in PEM format:\n{pem_cert}")
                    # Optionally, parse the PEM certificate
                    self.parse_certificate(pem_cert)
                    return pem_cert
        except Exception as e:
            logger.error(f"Failed to retrieve SSL certificate for {hostname}:{port}: {e}")
            return None
        
    def parse_certificate(self, pem_cert):
        logger.debug("Parsing PEM certificate")
        try:
            cert = x509.load_pem_x509_certificate(pem_cert.encode('utf-8'), default_backend())
            # Extract subject and issuer attributes safely
            def get_attribute(name, oid):
                try:
                    return name.get_attributes_for_oid(oid)[0].value
                except IndexError:
                    return "N/A"

            # Subject attributes
            subject = cert.subject
            subject_common_name = get_attribute(subject, x509.NameOID.COMMON_NAME)
            subject_organization = get_attribute(subject, x509.NameOID.ORGANIZATION_NAME)
            subject_organizational_unit = get_attribute(subject, x509.NameOID.ORGANIZATIONAL_UNIT_NAME)
            subject_country = get_attribute(subject, x509.NameOID.COUNTRY_NAME)
            subject_state = get_attribute(subject, x509.NameOID.STATE_OR_PROVINCE_NAME)
            subject_email = get_attribute(subject, x509.NameOID.EMAIL_ADDRESS)

            # Issuer attributes
            issuer = cert.issuer
            issuer_common_name = get_attribute(issuer, x509.NameOID.COMMON_NAME)
            issuer_organization = get_attribute(issuer, x509.NameOID.ORGANIZATION_NAME)
            issuer_organizational_unit = get_attribute(issuer, x509.NameOID.ORGANIZATIONAL_UNIT_NAME)
            issuer_country = get_attribute(issuer, x509.NameOID.COUNTRY_NAME)
            issuer_state = get_attribute(issuer, x509.NameOID.STATE_OR_PROVINCE_NAME)
            issuer_email = get_attribute(issuer, x509.NameOID.EMAIL_ADDRESS)

            # Validity dates
            not_before = cert.not_valid_before_utc
            not_after = cert.not_valid_after_utc

            # Serial number
            serial_number = cert.serial_number

            # Build the certificate info string
            cert_info = f"""
    Certificate Information:
    ========================
    Subject:
        Common Name:          {subject_common_name}
        Organization:         {subject_organization}
        Organizational Unit:  {subject_organizational_unit}
        Country:              {subject_country}
        State/Province:       {subject_state}
        Email Address:        {subject_email}

    Issuer:
        Common Name:          {issuer_common_name}
        Organization:         {issuer_organization}
        Organizational Unit:  {issuer_organizational_unit}
        Country:              {issuer_country}
        State/Province:       {issuer_state}
        Email Address:        {issuer_email}

    Validity:
        Not Before:           {not_before}
        Not After:            {not_after}

    Serial Number:            {serial_number}
    """
            logger.info(cert_info)
        except Exception as e:
            logger.error(f"Failed to parse certificate: {e}")


    
    def update_cookies(self, set_cookie_header):
        if set_cookie_header:
            cookie = SimpleCookie()
            cookie.load(set_cookie_header)
            for key, morsel in cookie.items():
                self.cookies[key] = morsel.value

    def build_cookie_header(self):
        cookie_header = '; '.join(f'{key}={value}' for key, value in self.cookies.items())
        return cookie_header

    def try_set_protocol(self):
        protocols = ["http", "https"]
        for protocol in protocols:
            url = f"{protocol}://{self.ip}"
            try:
                response = s.request('GET', url, timeout=5)
                if response.status == 200:
                    self.protocol = protocol
                    logger.info(f"Protocol set to {protocol}")
                    # If HTTPS, get certificate info
                    if protocol == "https":
                        self.get_certificate_info(self.ip)
                    return
            except Exception as e:
                logger.info(f"Failed to connect using {protocol}: {e} will try to switch to another protocol")
                # If HTTPS, attempt to get certificate info even if connection fails
                if protocol == "https":
                    self.get_certificate_info(self.ip)


    def hash(self, str):
        hashed = hashlib.sha256(str.encode()).hexdigest()
        logger.debug(f"Hashed string: {hashed}")
        return hashed

    def getVersion(self):
        logger.debug("Fetching router version")
        header = {"Referer": self.referer}
        # Include cookies if any
        cookie_header = self.build_cookie_header()
        if cookie_header:
            header['Cookie'] = cookie_header
        payload = "isTest=false&cmd=wa_inner_version"
        url = self.referer + f"goform/goform_get_cmd_process?{payload}"
        try:
            r = s.request('GET', url, headers=header)
            data = r.data.decode('utf-8')
            # Update cookies
            set_cookie_header = r.headers.get('Set-Cookie', '')
            self.update_cookies(set_cookie_header)
            version = json.loads(data)["wa_inner_version"]
            logger.info(f"Router version: {version}")
            return version
        except Exception as e:
            logger.error(f"Failed to fetch version: {e}")
            return ""

    def get_LD(self):
        logger.debug("Fetching LD value")
        header = {"Referer": self.referer}
        # Include cookies if any
        cookie_header = self.build_cookie_header()
        if cookie_header:
            header['Cookie'] = cookie_header
        payload = "isTest=false&cmd=LD"
        url = self.referer + f"goform/goform_get_cmd_process?{payload}"
        try:
            r = s.request('GET', url, headers=header)
            data = r.data.decode('utf-8')
            # Update cookies
            set_cookie_header = r.headers.get('Set-Cookie', '')
            self.update_cookies(set_cookie_header)
            ld = json.loads(data)["LD"].upper()
            logger.info(f"LD: {ld}")
            return ld
        except Exception as e:
            logger.error(f"Failed to fetch LD: {e}")
            return ""

    def getCookie(self, username, password, LD):
        logger.debug(f"Getting cookie for username: {username}, password: {password}, LD: {LD}")
        header = {"Referer": self.referer}
        # Build Cookie header
        cookie_header = self.build_cookie_header()
        if cookie_header:
            header['Cookie'] = cookie_header
        hashPassword = self.hash(password).upper()
        logger.debug(f"Hashed password: {hashPassword}")
        ztePass = self.hash(hashPassword + LD).upper()
        logger.debug(f"Hashed password+LD: {ztePass}")
        old_login = self.getVersion()

        if username is not None and username != "":
            goform_id = 'LOGIN_MULTI_USER'
            logger.debug(f"Username is not none selecting LOGIN_MULTI_USER")
        else:
            goform_id = 'LOGIN'
            logger.debug(f"Username is none selecting LOGIN")

        payload = {
            'isTest': 'false',
            'goformId': goform_id,
            'password': ztePass
        }

        if username is not None and username != "":
            payload['username'] = username

        url = self.referer + "goform/goform_set_cmd_process"
        # Prepare the encoded form data
        encoded_payload = urllib.parse.urlencode(payload)
        body = encoded_payload.encode('utf-8')

        try:
            r = s.request('POST', url, headers=header, body=body)
            data = r.data.decode('utf-8')
            # Parse Set-Cookie header
            set_cookie_header = r.headers.get('Set-Cookie', '')
            self.update_cookies(set_cookie_header)
            # Check if 'stok' is in cookies
            stok = self.cookies.get('stok')
            if not stok:
                logger.error("Failed to obtain a valid cookie from the router")
                raise ValueError("Failed to obtain a valid cookie from the router")
            logger.info(f"Obtained cookie: stok={stok}")
            return stok
        except Exception as e:
            logger.error(f"Failed to obtain cookie: {e}")
            raise

    def get_RD(self):
        logger.debug("Fetching RD value")
        header = {"Referer": self.referer}
        # Include cookies if any
        cookie_header = self.build_cookie_header()
        if cookie_header:
            header['Cookie'] = cookie_header
        payload = "isTest=false&cmd=RD"
        url = self.referer + f"goform/goform_get_cmd_process?{payload}"
        try:
            r = s.request('POST', url, headers=header)
            data = r.data.decode('utf-8')
            # Update cookies
            set_cookie_header = r.headers.get('Set-Cookie', '')
            self.update_cookies(set_cookie_header)
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
        cookie_header = self.build_cookie_header()
        if cookie_header:
            header['Cookie'] = cookie_header
        try:
            rd_url = self.referer + "goform/goform_get_cmd_process?isTest=false&cmd=RD"
            rd_response = s.request('GET', rd_url, headers=header)
            data = rd_response.data.decode('utf-8')
            # Update cookies
            set_cookie_header = rd_response.headers.get('Set-Cookie', '')
            self.update_cookies(set_cookie_header)
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
            self.getCookie(username=self.username, password=self.password, LD=self.get_LD())
            AD = self.get_AD()
            header = {"Referer": self.referer}
            # Build Cookie header
            cookie_header = self.build_cookie_header()
            if cookie_header:
                header['Cookie'] = cookie_header

            # Encode phone number and message
            phoneNumberEncoded = urllib.parse.quote(phone_number, safe="")
            messageEncoded = gsm_encode(message).decode()

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

            # Prepare the encoded form data
            encoded_payload = urllib.parse.urlencode(payload)
            body = encoded_payload.encode('utf-8')

            r = s.request('POST', self.referer + "goform/goform_set_cmd_process", headers=header, body=body)

            logger.info(f"SMS sent with status code: {r.status}")
            return r.status
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return None


    def zteinfo(self):
        logger.debug("Fetching ZTE info")
        try:
            # Get LD and update cookies
            LD = self.get_LD()
            # getCookie will update self.cookies
            self.getCookie(username=self.username, password=self.password, LD=LD)
            header = {
                "Host": self.ip,
                "Referer": f"{self.referer}index.html",
            }
            cookie_header = self.build_cookie_header()
            if cookie_header:
                header['Cookie'] = cookie_header
            cmd_url = f"{self.protocol}://{self.ip}/goform/goform_get_cmd_process?isTest=false&cmd=wa_inner_version%2Ccr_version%2Cnetwork_type%2Crssi%2Crscp%2Crmcc%2Crmnc%2Cenodeb_id%2Clte_rsrq%2Clte_rsrp%2CZ5g_snr%2CZ5g_rsrp%2CZCELLINFO_band%2CZ5g_dlEarfcn%2Clte_ca_pcell_arfcn%2Clte_ca_pcell_band%2Clte_ca_scell_band%2Clte_ca_pcell_bandwidth%2Clte_ca_scell_info%2Clte_ca_scell_bandwidth%2Cwan_lte_ca%2Clte_pci%2CZ5g_CELL_ID%2CZ5g_SINR%2Ccell_id%2Cwan_lte_ca%2Clte_ca_pcell_band%2Clte_ca_pcell_bandwidth%2Clte_ca_scell_band%2Clte_ca_scell_bandwidth%2Clte_ca_pcell_arfcn%2Clte_ca_scell_arfcn%2Clte_multi_ca_scell_info%2Cwan_active_band%2Cnr5g_pci%2Cnr5g_action_band%2Cnr5g_cell_id%2Clte_snr%2Cecio%2Cwan_active_channel%2Cnr5g_action_channel%2Cngbr_cell_info%2Cmonthly_tx_bytes%2Cmonthly_rx_bytes%2Clte_pci%2Clte_pci_lock%2Clte_earfcn_lock%2Cwan_ipaddr%2Cwan_apn%2Cpm_sensor_mdm%2Cpm_modem_5g%2Cnr5g_pci%2Cnr5g_action_channel%2Cnr5g_action_band%2CZ5g_SINR%2CZ5g_rsrp%2Cwan_active_band%2Cwan_active_channel%2Cwan_lte_ca%2Clte_multi_ca_scell_info%2Ccell_id%2Cdns_mode%2Cprefer_dns_manual%2Cstandby_dns_manual%2Cnetwork_type%2Crmcc%2Crmnc%2Clte_rsrq%2Clte_rssi%2Clte_rsrp%2Clte_snr%2Cwan_lte_ca%2Clte_ca_pcell_band%2Clte_ca_pcell_bandwidth%2Clte_ca_scell_band%2Clte_ca_scell_bandwidth%2Clte_ca_pcell_arfcn%2Clte_ca_scell_arfcn%2Cwan_ipaddr%2Cstatic_wan_ipaddr%2Copms_wan_mode%2Copms_wan_auto_mode%2Cppp_status%2Cloginfo%2Crealtime_time%2Csignalbar&multi_data=1"
            response = s.request('GET', cmd_url, headers=header)
            data = response.data.decode('utf-8')
            # Update cookies
            set_cookie_header = response.headers.get('Set-Cookie', '')
            self.update_cookies(set_cookie_header)
            logger.info("Fetched ZTE info successfully")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch ZTE info: {e}")
            return ""

    # ... (Previous methods in the class)

    def zteinfo2(self):
        logger.debug("Fetching ZTE info 2")
        try:
            # Get LD and update cookies
            LD = self.get_LD()
            # getCookie will update self.cookies
            self.getCookie(username=self.username, password=self.password, LD=LD)
            header = {
                "Host": self.ip,
                "Referer": f"{self.referer}index.html",
            }
            cookie_header = self.build_cookie_header()
            if cookie_header:
                header['Cookie'] = cookie_header
            cmd_url = f"{self.protocol}://{self.ip}/goform/goform_get_cmd_process?multi_data=1&isTest=false&sms_received_flag_flag=0&sts_received_flag_flag=0&cmd=network_type%2Crssi%2Clte_rssi%2Crscp%2Clte_rsrp%2CZ5g_snr%2CZ5g_rsrp%2CZCELLINFO_band%2CZ5g_dlEarfcn%2Clte_ca_pcell_arfcn%2Clte_ca_pcell_band%2Clte_ca_scell_band%2Clte_ca_pcell_bandwidth%2Clte_ca_scell_info%2Clte_ca_scell_bandwidth%2Cwan_lte_ca%2Clte_pci%2CZ5g_CELL_ID%2CZ5g_SINR%2Ccell_id%2Cwan_lte_ca%2Clte_ca_pcell_band%2Clte_ca_pcell_bandwidth%2Clte_ca_scell_band%2Clte_ca_scell_bandwidth%2Clte_ca_pcell_arfcn%2Clte_ca_scell_arfcn%2Clte_multi_ca_scell_info%2Cwan_active_band%2Cnr5g_pci%2Cnr5g_action_band%2Cnr5g_cell_id%2Clte_snr%2Cecio%2Cwan_active_channel%2Cnr5g_action_channel%2Cmodem_main_state%2Cpin_status%2Copms_wan_mode%2Copms_wan_auto_mode%2Cloginfo%2Cnew_version_state%2Ccurrent_upgrade_state%2Cis_mandatory%2Cwifi_dfs_status%2Cbattery_value%2Cppp_dial_conn_fail_counter%2Cwifi_chip1_ssid1_auth_mode%2Cwifi_chip2_ssid1_auth_mode%2Csignalbar%2Cnetwork_type%2Cnetwork_provider%2Cppp_status%2Csimcard_roam%2Cspn_name_data%2Cspn_b1_flag%2Cspn_b2_flag%2Cwifi_onoff_state%2Cwifi_chip1_ssid1_ssid%2Cwifi_chip2_ssid1_ssid%2Cwan_lte_ca%2Cmonthly_tx_bytes%2Cmonthly_rx_bytes%2Cpppoe_status%2Cdhcp_wan_status%2Cstatic_wan_status%2Crmcc%2Crmnc%2Cmdm_mcc%2Cmdm_mnc%2CEX_SSID1%2Csta_ip_status%2CEX_wifi_profile%2Cm_ssid_enable%2CRadioOff%2Cwifi_chip1_ssid1_access_sta_num%2Cwifi_chip2_ssid1_access_sta_num%2Clan_ipaddr%2Cstation_mac%2Cwifi_access_sta_num%2Cbattery_charging%2Cbattery_vol_percent%2Cbattery_pers%2Crealtime_tx_bytes%2Crealtime_rx_bytes%2Crealtime_time%2Crealtime_tx_thrpt%2Crealtime_rx_thrpt%2Cmonthly_time%2Cdate_month%2Cdata_volume_limit_switch%2Cdata_volume_limit_size%2Cdata_volume_alert_percent%2Cdata_volume_limit_unit%2Croam_setting_option%2Cupg_roam_switch%2Cssid%2Cwifi_enable%2Cwifi_5g_enable%2Ccheck_web_conflict%2Cdial_mode%2Cprivacy_read_flag%2Cis_night_mode%2Cvpn_conn_status%2Cwan_connect_status%2Csms_received_flag%2Csts_received_flag%2Csms_unread_num%2Cwifi_chip1_ssid2_access_sta_num%2Cwifi_chip2_ssid2_access_sta_num&multi_data=1"
            response = s.request('GET', cmd_url, headers=header)
            data = response.data.decode('utf-8')
            # Update cookies
            set_cookie_header = response.headers.get('Set-Cookie', '')
            self.update_cookies(set_cookie_header)
            logger.info("Fetched ZTE info 2 successfully")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch ZTE info 2: {e}")
            return ""

    def zteinfo3(self):
        logger.debug("Fetching ZTE info 3")
        try:
            # Get LD and update cookies
            LD = self.get_LD()
            # getCookie will update self.cookies
            self.getCookie(username=self.username, password=self.password, LD=LD)
            header = {
                "Host": self.ip,
                "Referer": f"{self.referer}index.html",
            }
            cookie_header = self.build_cookie_header()
            if cookie_header:
                header['Cookie'] = cookie_header
            cmd_url = f"{self.protocol}://{self.ip}/goform/goform_get_cmd_process?isTest=false&multi_data=1&sms_received_flag_flag=0&sts_received_flag_flag=0&cmd=wa_inner_version%2Ccr_version%2Cnetwork_type%2Crssi%2Crscp%2Crmcc%2Crmnc%2Cenodeb_id%2Clte_rsrq%2Clte_rsrp%2CZ5g_snr%2CZ5g_rsrp%2CZCELLINFO_band%2CZ5g_dlEarfcn%2Clte_ca_pcell_arfcn%2Clte_ca_pcell_band%2Clte_ca_scell_band%2Clte_ca_pcell_bandwidth%2Clte_ca_scell_info%2Clte_ca_scell_bandwidth%2Cwan_lte_ca%2Clte_pci%2CZ5g_CELL_ID%2CZ5g_SINR%2Ccell_id%2Clte_ca_scell_arfcn%2Clte_multi_ca_scell_info%2Cwan_active_band%2Cnr5g_pci%2Cnr5g_action_band%2Cnr5g_cell_id%2Clte_snr%2Cecio%2Cwan_active_channel%2Cnr5g_action_channel%2Cngbr_cell_info%2Cmonthly_tx_bytes%2Cmonthly_rx_bytes%2Clte_pci_lock%2Clte_earfcn_lock%2Cwan_ipaddr%2Cwan_apn%2Cpm_sensor_mdm%2Cpm_modem_5g%2Cmodem_main_state%2Cpin_status%2Copms_wan_mode%2Copms_wan_auto_mode%2Cloginfo%2Cnew_version_state%2Ccurrent_upgrade_state%2Cis_mandatory%2Cwifi_dfs_status%2Cbattery_value%2Cppp_dial_conn_fail_counter%2Cwifi_chip1_ssid1_auth_mode%2Cwifi_chip2_ssid1_auth_mode%2Cnetwork_provider%2Csimcard_roam%2Cspn_name_data%2Cspn_b1_flag%2Cspn_b2_flag%2Cwifi_onoff_state%2Cwifi_chip1_ssid1_ssid%2Cwifi_chip2_ssid1_ssid%2Cpppoe_status%2Cdhcp_wan_status%2Cstatic_wan_status%2Cmdm_mcc%2Cmdm_mnc%2CEX_SSID1%2Csta_ip_status%2CEX_wifi_profile%2Cm_ssid_enable%2CRadioOff%2Cwifi_chip1_ssid1_access_sta_num%2Cwifi_chip2_ssid1_access_sta_num%2Clan_ipaddr%2Cstation_mac%2Cwifi_access_sta_num%2Cbattery_charging%2Cbattery_vol_percent%2Cbattery_pers%2Crealtime_tx_bytes%2Crealtime_rx_bytes%2Crealtime_time%2Crealtime_tx_thrpt%2Crealtime_rx_thrpt%2Cmonthly_time%2Cdate_month%2Cdata_volume_limit_switch%2Cdata_volume_limit_size%2Cdata_volume_alert_percent%2Cdata_volume_limit_unit%2Croam_setting_option%2Cupg_roam_switch%2Cssid%2Cwifi_enable%2Cwifi_5g_enable%2Ccheck_web_conflict%2Cdial_mode%2Cprivacy_read_flag%2Cis_night_mode%2Cvpn_conn_status%2Cwan_connect_status%2Csms_received_flag%2Csts_received_flag%2Csms_unread_num%2Cwifi_chip1_ssid2_access_sta_num%2Cwifi_chip2_ssid2_access_sta_num%2Cstatic_wan_ipaddr%2Cdns_mode%2Cprefer_dns_manual%2Cstandby_dns_manual%2Csignalbar%2Cppp_status"
            response = s.request('GET', cmd_url, headers=header)
            data = response.data.decode('utf-8')
            # Update cookies
            set_cookie_header = response.headers.get('Set-Cookie', '')
            self.update_cookies(set_cookie_header)
            logger.info("Fetched ZTE info 3 successfully")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch ZTE info 3: {e}")
            return ""

    def ztesmsinfo(self):
        logger.debug("Fetching ZTE SMS info")
        try:
            # Get LD and update cookies
            LD = self.get_LD()
            # getCookie will update self.cookies
            self.getCookie(username=self.username, password=self.password, LD=LD)
            header = {
                "Host": self.ip,
                "Referer": f"{self.referer}index.html",
            }
            cookie_header = self.build_cookie_header()
            if cookie_header:
                header['Cookie'] = cookie_header
            cmd_url = f"{self.protocol}://{self.ip}/goform/goform_get_cmd_process?isTest=false&cmd=sms_capacity_info"
            response = s.request('GET', cmd_url, headers=header)
            data = response.data.decode('utf-8')
            # Update cookies
            set_cookie_header = response.headers.get('Set-Cookie', '')
            self.update_cookies(set_cookie_header)

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
            # Get LD and update cookies
            LD = self.get_LD()
            # getCookie will update self.cookies
            self.getCookie(username=self.username, password=self.password, LD=LD)
            # AD value
            AD = self.get_AD()
            header = {"Referer": self.referer}
            cookie_header = self.build_cookie_header()
            if cookie_header:
                header['Cookie'] = cookie_header
            payload = {
                'isTest': 'false',
                'goformId': 'REBOOT_DEVICE',
                'AD': AD
            }
            encoded_payload = urllib.parse.urlencode(payload)
            body = encoded_payload.encode('utf-8')
            r = s.request('POST', self.referer + "goform/goform_set_cmd_process", headers=header, body=body)
            logger.info(f"Router rebooted with status code: {r.status}")
            return r.status
        except Exception as e:
            logger.error(f"Failed to reboot router: {e}")
            return None

    def deletesms(self, msg_id):
        logger.debug(f"Deleting SMS with ID: {msg_id}")
        try:
            # Get LD and update cookies
            LD = self.get_LD()
            # getCookie will update self.cookies
            self.getCookie(username=self.username, password=self.password, LD=LD)
            # AD value
            AD = self.get_AD()
            header = {"Referer": self.referer}
            cookie_header = self.build_cookie_header()
            if cookie_header:
                header['Cookie'] = cookie_header
            payload = {
                'isTest': 'false',
                'goformId': 'DELETE_SMS',
                'msg_id': msg_id,
                'AD': AD
            }
            encoded_payload = urllib.parse.urlencode(payload)
            body = encoded_payload.encode('utf-8')
            r = s.request('POST', self.referer + "goform/goform_set_cmd_process", headers=header, body=body)
            logger.info(f"SMS deleted with status code: {r.status}")
            return r.status
        except Exception as e:
            logger.error(f"Failed to delete SMS: {e}")
            return None

    def parsesms(self):
        logger.debug("Parsing SMS")
        try:
            # Get LD and update cookies
            LD = self.get_LD()
            # getCookie will update self.cookies
            self.getCookie(username=self.username, password=self.password, LD=LD)
            header = {"Referer": self.referer}
            cookie_header = self.build_cookie_header()
            if cookie_header:
                header['Cookie'] = cookie_header
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
            r = s.request('GET', url, headers=header)
            response_text = r.data.decode('utf-8')

            modified_response_text = response_text.replace('HRTelekom', 'HR Telekom')
            response_json = json.loads(modified_response_text)
            value = response_json['messages']

            def hex2utf(string):
                length = len(string) // 4
                result = ''
                for i in range(length):
                    result += chr(int(string[i*4:i*4+4], 16))
                return result

            smslist = response_json

            for item in smslist['messages']:
                item['content'] = hex2utf(item['content'])

            logger.info("Parsed SMS successfully")
            return json.dumps(smslist, indent=2)
        except Exception as e:
            logger.error(f"Failed to parse SMS: {e}")
            return ""

    def connect_data(self):
        logger.debug("Connecting to data network")
        try:
            # Get LD and update cookies
            LD = self.get_LD()
            # getCookie will update self.cookies
            self.getCookie(username=self.username, password=self.password, LD=LD)
            # AD value
            AD = self.get_AD()
            header = {"Referer": self.referer}
            cookie_header = self.build_cookie_header()
            if cookie_header:
                header['Cookie'] = cookie_header
            payload = {
                'isTest': 'false',
                'goformId': 'CONNECT_NETWORK',
                'AD': AD
            }
            encoded_payload = urllib.parse.urlencode(payload)
            body = encoded_payload.encode('utf-8')
            r = s.request('POST', self.referer + "goform/goform_set_cmd_process", headers=header, body=body)
            logger.info(f"Connected to data network with status code: {r.status}")
            return r.status
        except Exception as e:
            logger.error(f"Failed to connect to data network: {e}")
            return None

    def disconnect_data(self):
        logger.debug("Disconnecting from data network")
        try:
            # Get LD and update cookies
            LD = self.get_LD()
            # getCookie will update self.cookies
            self.getCookie(username=self.username, password=self.password, LD=LD)
            # AD value
            AD = self.get_AD()
            header = {"Referer": self.referer}
            cookie_header = self.build_cookie_header()
            if cookie_header:
                header['Cookie'] = cookie_header
            payload = {
                'isTest': 'false',
                'goformId': 'DISCONNECT_NETWORK',
                'AD': AD
            }
            encoded_payload = urllib.parse.urlencode(payload)
            body = encoded_payload.encode('utf-8')
            r = s.request('POST', self.referer + "goform/goform_set_cmd_process", headers=header, body=body)
            logger.info(f"Disconnected from data network with status code: {r.status}")
            return r.status
        except Exception as e:
            logger.error(f"Failed to disconnect from data network: {e}")
            return None

    def setdata_5G_SA(self):
        logger.debug("Setting data to 5G SA mode")
        try:
            # Get LD and update cookies
            LD = self.get_LD()
            # getCookie will update self.cookies
            self.getCookie(username=self.username, password=self.password, LD=LD)
            # AD value
            AD = self.get_AD()
            header = {"Referer": self.referer}
            cookie_header = self.build_cookie_header()
            if cookie_header:
                header['Cookie'] = cookie_header
            payload = {
                'isTest': 'false',
                'goformId': 'SET_BEARER_PREFERENCE',
                'BearerPreference': 'Only_5G',
                'AD': AD
            }
            encoded_payload = urllib.parse.urlencode(payload)
            body = encoded_payload.encode('utf-8')
            r = s.request('POST', self.referer + "goform/goform_set_cmd_process", headers=header, body=body)
            logger.info(f"Set data to 5G SA mode with status code: {r.status}")
            return r.status
        except Exception as e:
            logger.error(f"Failed to set data to 5G SA mode: {e}")
            return None

    def setdata_5G_NSA(self):
        logger.debug("Setting data to 5G NSA mode")
        try:
            # Get LD and update cookies
            LD = self.get_LD()
            # getCookie will update self.cookies
            self.getCookie(username=self.username, password=self.password, LD=LD)
            # AD value
            AD = self.get_AD()
            header = {"Referer": self.referer}
            cookie_header = self.build_cookie_header()
            if cookie_header:
                header['Cookie'] = cookie_header
            payload = {
                'isTest': 'false',
                'goformId': 'SET_BEARER_PREFERENCE',
                'BearerPreference': 'LTE_AND_5G',
                'AD': AD
            }
            encoded_payload = urllib.parse.urlencode(payload)
            body = encoded_payload.encode('utf-8')
            r = s.request('POST', self.referer + "goform/goform_set_cmd_process", headers=header, body=body)
            logger.info(f"Set data to 5G NSA mode with status code: {r.status}")
            return r.status
        except Exception as e:
            logger.error(f"Failed to set data to 5G NSA mode: {e}")
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
        print("Usage: script.py ip password command [username] [phone_number] [message]")
        sys.exit(1)

    ip = sys.argv[1]
    password = sys.argv[2]
    command = int(sys.argv[3])

    # Initialize variables
    username = None
    phone_number = None
    message = None

    # Adjust argument parsing based on the command
    if command == 8:
        # Command to send SMS
        if len(sys.argv) == 6:
            # No username provided
            username = None
            phone_number = sys.argv[4]
            message = sys.argv[5]
        elif len(sys.argv) == 7:
            # Username provided
            username = sys.argv[4] if sys.argv[4] != "" else None
            phone_number = sys.argv[5]
            message = sys.argv[6]
        else:
            print("Invalid number of arguments for sending SMS")
            sys.exit(1)
    else:
        # For other commands
        if len(sys.argv) > 4:
            username = sys.argv[4] if sys.argv[4] != "" else None

    # Create a router instance
    zte = zteRouter(ip, username, password)

    logger.info(f"Command: {command}, Username: {username}, Password: {password}")

    try:
        result = None  # Ensure result is initialized
        if command == 1:
            result = zte.zteinfo()
            print(result)
        elif command == 2:
            result = zte.zteinfo2()
            print(result)
        elif command == 3:
            result = zte.ztesmsinfo()
            print(result)
        elif command == 4:
            result = zte.ztereboot()
            print(result)
        elif command == 5:
            result = zte.parsesms()
            if result:
                data = json.loads(result)
                ids = [msg['id'] for msg in data['messages']]
                if ids:
                    formatted_ids = ";".join(ids)
                    logger.info(f"Deleting SMS messages with IDs: {formatted_ids}")
                    result = zte.deletesms(formatted_ids)
                    print(result)
                else:
                    logger.info("No SMS in memory")
                    sys.exit(0)
        elif command == 6:
            result = zte.parsesms()
            if result:
                test = json.loads(result)
                if test["messages"]:
                    first_message = test["messages"][0]
                    first_message_json = json.dumps(first_message)
                    print(first_message_json)
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
                    print(json.dumps(dummy_message))
                    sys.exit(0)
        elif command == 7:
            result = zte.zteinfo3()
            print(result)
        elif command == 8:
            if phone_number and message:
                logger.info(f"Sending SMS to {phone_number} with message: {message}")
                result = zte.sendsms(phone_number, message)
                print(result)
            else:
                logger.error(f"Phone number or message not provided. Phone number: {phone_number}, Message: {message}")
                print("Phone number or message not provided for sending SMS")
                sys.exit(1)
        elif command == 9:
            result = zte.connect_data()
            print(result)
        elif command == 10:
            result = zte.disconnect_data()
            print(result)
        elif command == 11:
            result = zte.setdata_5G_SA()
            print(result)
        elif command == 12:
            result = zte.setdata_5G_NSA()
            print(result)
        else:
            print(f"Invalid command: {command}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"An error occurred: {e}")