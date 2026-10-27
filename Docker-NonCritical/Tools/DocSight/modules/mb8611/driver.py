"""Motorola MB8611 driver for DOCSight."""

import hashlib
import hmac
import logging
import re
import time
from urllib.parse import urlparse

import urllib3
import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from app.drivers.base import ModemDriver

log = logging.getLogger("docsis.driver.mb8611")


class MB8611Driver(ModemDriver):

    DRIVER_KEY = "mb8611"

    def __init__(self, url: str, user: str, password: str):
        super().__init__(url, user, password)
        self._session = requests.Session()
        self._session.verify = False  # MB8611 uses a self-signed certificate
        self._session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"})
        self._real_base = url.rstrip("/")
        self._private_key: str = ""  # set after successful HNAP login

    # HNAP1 — MB8611 firmware uses JSON-HNAP (not SOAP XML)
    _HNAP_URL = "/HNAP1/"
    _HNAP_BASE = "http://purenetworks.com/HNAP1/"

    def _hnap_request(self, action: str, payload: dict, cookie: str = "") -> dict:
        """POST a JSON HNAP1 request and return the parsed response dict."""
        url = f"{self._real_base}{self._HNAP_URL}"
        soap_action = f'"{self._HNAP_BASE}{action}"'
        headers = {
            "Content-Type": "application/json",
            "SOAPAction": soap_action,
        }
        if cookie:
            # During login challenge/response only
            headers["Cookie"] = f"uid={cookie}"
        elif self._private_key:
            # Authenticated requests require HNAP_AUTH: HMAC-MD5(PrivateKey, ts+SOAPAction) ts
            ts = str(int(time.time() * 1000) % 2_000_000_000)
            auth_hash = self._hmac_md5(self._private_key, ts + soap_action)
            headers["HNAP_AUTH"] = f"{auth_hash} {ts}"
        r = self._session.post(url, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _hmac_md5(key: str, msg: str) -> str:
        return hmac.new(key.encode(), msg.encode(), hashlib.md5).hexdigest().upper()

    def login(self) -> None:
        """Authenticate via HNAP1 challenge-response (used by all MB8611 firmware)."""
        if not self._user and not self._password:
            return
        try:
            # Resolve http→https redirect to get the real base URL
            r0 = self._session.get(f"{self._url}/", timeout=15, allow_redirects=True)
            r0.raise_for_status()
            parsed = urlparse(r0.url)
            self._real_base = f"{parsed.scheme}://{parsed.netloc}"

            if "logout" in r0.text.lower() and "login" not in r0.url.lower():
                return  # already authenticated

            # Step 1 — request challenge
            resp1 = self._hnap_request("Login", {"Login": {
                "Action": "request",
                "Username": self._user,
                "LoginPassword": "",
                "Captcha": "",
                "PrivateLogin": "LoginPassword",
            }})
            login_resp = resp1.get("LoginResponse", resp1)
            log.debug("MB8611: HNAP challenge response: %s", login_resp)

            challenge = login_resp.get("Challenge", "")
            public_key = login_resp.get("PublicKey", "")
            cookie_val = login_resp.get("Cookie", "")
            result1 = login_resp.get("LoginResult", "")

            log.debug("MB8611: HNAP challenge -> result=%r challenge_len=%d pubkey_len=%d cookie_len=%d",
                      result1, len(challenge), len(public_key), len(cookie_val))

            if not challenge or not public_key or not cookie_val:
                raise RuntimeError(
                    f"MB8611: HNAP challenge missing fields "
                    f"(challenge={bool(challenge)} pubkey={bool(public_key)} cookie={bool(cookie_val)}); "
                    f"response: {login_resp}"
                )

            # Step 2 — compute HMAC-MD5 keys and login
            private_key = self._hmac_md5(public_key + self._password, challenge)
            login_password = self._hmac_md5(private_key, challenge)

            resp2 = self._hnap_request("Login", {"Login": {
                "Action": "login",
                "Username": self._user,
                "LoginPassword": login_password,
                "Captcha": "",
                "PrivateLogin": "LoginPassword",
            }}, cookie=cookie_val)
            result2 = resp2.get("LoginResponse", resp2).get("LoginResult", "")
            log.debug("MB8611: HNAP login result: %r", result2)

            if result2.upper() != "OK":
                raise RuntimeError(f"MB8611: HNAP login failed — LoginResult={result2!r}")

            # Persist the session cookie and private key for subsequent authenticated requests
            self._session.cookies.set("uid", cookie_val, domain=parsed.netloc)
            self._private_key = private_key
            log.info("MB8611: HNAP login succeeded")

        except requests.RequestException as e:
            raise RuntimeError(f"MB8611: login failed: {e}")

    # Known status page paths across MB8611 firmware versions
    _STATUS_PATHS = [
        # MB8611-specific paths (most likely first)
        "/MotoConnectionStatus.html",
        "/MotoStatusConnection.html",
        "/cmconnectionstatus.html",
        "/DocsisStatus.htm",
        "/RgConnect.asp",
        "/motoconnectionstatus.html",
        "/connection_status.html",
        "/status_docsis.asp",
        "/MotoConnection.html",
        "/MotoStatus.html",
        "/channel_status.html",
        "/docsis_status.html",
    ]

    def _find_status_url(self) -> str | None:
        """Try known paths, then scrape root page links as fallback."""
        found_paths = []
        for path in self._STATUS_PATHS:
            try:
                resp = self._session.get(f"{self._real_base}{path}", timeout=10)
                table_count = resp.text.lower().count("<table")
                found_paths.append(f"{path}={resp.status_code}(t={table_count})")
                if resp.status_code == 200 and table_count >= 3:
                    log.debug("MB8611: status page found at %s (tables=%d)", path, table_count)
                    return f"{self._real_base}{path}"
            except requests.RequestException as e:
                found_paths.append(f"{path}=ERR({e})")
                continue

        # scrape MotoHome.html (authenticated home) for status page links
        try:
            root = self._session.get(f"{self._real_base}/MotoHome.html", timeout=10)
            # extract all href attrs and any quoted .html/.htm/.asp strings from JS
            all_refs = re.findall(r'["\']([^"\']*\.(?:html?|asp))["\']', root.text, re.IGNORECASE)
            log.debug("MB8611: all page refs found on MotoHome: %s", sorted(set(all_refs)))
            keywords = ("status", "docsis", "connection", "connect", "channel")
            for ref in all_refs:
                if any(kw in ref.lower() for kw in keywords):
                    url = ref if ref.startswith("http") else f"{self._real_base}/{ref.lstrip('/')}"
                    log.info("MB8611: trying discovered ref: %s", url)
                    resp = self._session.get(url, timeout=10)
                    # Require ≥3 tables — the DOCSIS page has DS table + US table + others;
                    # software/firmware pages may have tables but not enough for channel data
                    table_count = resp.text.lower().count("<table")
                    log.info("MB8611: %s -> status=%d tables=%d", url, resp.status_code, table_count)
                    if resp.status_code == 200 and table_count >= 3:
                        return url
        except requests.RequestException:
            pass

        log.error("MB8611: path probe results: %s", found_paths)
        return None

    def get_docsis_data(self) -> dict:
        # MB8611 loads channel data via HNAP JSON calls from JavaScript — the HTML
        # tables are empty placeholders.  Fetch directly using the same HNAP session.
        resp_ds = self._hnap_request(
            "GetMotoStatusDownstreamChannelInfo",
            {"GetMotoStatusDownstreamChannelInfo": ""},
        )
        resp_us = self._hnap_request(
            "GetMotoStatusUpstreamChannelInfo",
            {"GetMotoStatusUpstreamChannelInfo": ""},
        )
        log.debug("MB8611: HNAP DS raw: %r", str(resp_ds)[:600])
        log.debug("MB8611: HNAP US raw: %r", str(resp_us)[:600])

        ds_body = resp_ds.get("GetMotoStatusDownstreamChannelInfoResponse", resp_ds)
        us_body = resp_us.get("GetMotoStatusUpstreamChannelInfoResponse", resp_us)

        downstream = self._parse_hnap_downstream(
            ds_body.get("MotoConnDownstreamChannel", ""),
            ds_body.get("MotoConnOfdmChannel", ""),
        )
        upstream = self._parse_hnap_upstream(
            us_body.get("MotoConnUpstreamChannel", ""),
            us_body.get("MotoConnOfdmaChannel", ""),
        )
        log.info("MB8611: parsed DS=%d US=%d", len(downstream), len(upstream))

        return {
            "docsis": "3.1",
            "downstream": downstream,
            "upstream": upstream,
        }

    def _parse_hnap_downstream(self, sc_qam_raw: str, ofdm_raw: str = "") -> list:
        """Parse caret-delimited SC-QAM and OFDM downstream channel strings.

        SC-QAM field order: index^lockStatus^modulation^channelId^freqHz^powerDbmv^snrDb^corrected^uncorrected^
        OFDM field order:   index^lockStatus^modulation^channelId^freqHz^powerDbmv^snrDb^corrected^uncorrected^...
        Channels are pipe-separated.
        """
        result = []
        for raw, ch_kind in ((sc_qam_raw, "qam"), (ofdm_raw, "ofdm")):
            if not raw:
                continue
            for entry in raw.strip("|").split("|"):
                parts = [p.strip() for p in entry.split("^")]
                if len(parts) < 9:
                    continue
                if parts[1].lower() != "locked":
                    continue
                try:
                    mod = parts[2].upper()
                    is_ofdm = ch_kind == "ofdm" or "OFDM" in mod
                    freq_hz = float(parts[4]) if parts[4] else 0.0
                    freq_mhz = freq_hz / 1_000_000 if freq_hz > 1_000 else freq_hz
                    power = float(parts[5]) if parts[5] else None
                    snr = float(parts[6]) if parts[6] else None
                    corr = int(float(parts[7])) if parts[7] else 0
                    uncorr = int(float(parts[8])) if parts[8] else 0
                    result.append({
                        "channelID": parts[3],
                        "type": "ofdm" if is_ofdm else _normalize_modulation(parts[2]) or "qam",
                        "frequency": f"{freq_mhz:.1f} MHz" if freq_mhz else "",
                        "powerLevel": power,
                        "mse": None if is_ofdm else (-snr if snr is not None else None),
                        "mer": snr,
                        "latency": 0,
                        "corrError": corr,
                        "nonCorrError": uncorr,
                    })
                except (ValueError, TypeError, IndexError) as e:
                    log.warning("MB8611: DS parse error %s for parts=%s", e, parts)
        return result

    def _parse_hnap_upstream(self, sc_qam_raw: str, ofdma_raw: str = "") -> list:
        """Parse caret-delimited SC-QAM and OFDMA upstream channel strings.

        SC-QAM field order: index^lockStatus^channelType^channelId^symbolRate^freqHz^powerDbmv^
        OFDMA field order may vary; treat similarly.
        Channels are pipe-separated.
        """
        result = []
        for raw, ch_kind in ((sc_qam_raw, "sc-qam"), (ofdma_raw, "ofdma")):
            if not raw:
                continue
            for entry in raw.strip("|").split("|"):
                parts = [p.strip() for p in entry.split("^")]
                if len(parts) < 7:
                    continue
                if parts[1].lower() != "locked":
                    continue
                try:
                    freq_hz = float(parts[5]) if parts[5] else 0.0
                    freq_mhz = freq_hz / 1_000_000 if freq_hz > 1_000 else freq_hz
                    power = float(parts[6]) if parts[6] else None
                    ch_type = parts[2].upper()
                    result.append({
                        "channelID": parts[3],
                        "type": "ofdma" if ("OFDM" in ch_type or ch_kind == "ofdma") else "sc-qam",
                        "frequency": f"{freq_mhz:.1f} MHz" if freq_mhz else "",
                        "powerLevel": power,
                        "multiplex": "",
                    })
                except (ValueError, TypeError, IndexError) as e:
                    log.warning("MB8611: US parse error %s for parts=%s", e, parts)
        return result

    def get_device_info(self) -> dict:
        return {
            "manufacturer": "Motorola",
            "model": "MB8611",
            "sw_version": "",
        }

    def get_connection_info(self) -> dict:
        return {}

    def _parse_downstream(self, table) -> list:
        rows = table.find_all("tr")
        header_row = _find_header_row(rows)
        if header_row is None:
            return []

        headers = [c.get_text(strip=True).lower() for c in header_row.find_all(["th", "td"])]
        col = _map_ds_columns(headers)
        result = []

        for row in rows:
            if row is header_row:
                continue
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 4:
                continue
            if _cell(cells, col["lock_status"]).lower() != "locked":
                continue
            try:
                ch_type = _cell(cells, col["channel_type"]).upper()
                modulation = _normalize_modulation(_cell(cells, col["modulation"]))
                if ch_type == "OFDM":
                    final_type = "ofdm"
                elif modulation:
                    final_type = modulation
                else:
                    final_type = "qam"

                freq = _parse_frequency(_cell(cells, col["frequency"]))
                power = _parse_number(_cell(cells, col["power"]))
                snr = _parse_number(_cell(cells, col["snr"]))
                corr = int(_parse_number(_cell(cells, col["corrected"])))
                uncorr = int(_parse_number(_cell(cells, col["uncorrected"])))
                is_ofdm = final_type == "ofdm"

                result.append({
                    "channelID": _cell(cells, col["channel_id"], "0"),
                    "type": final_type,
                    "frequency": f"{int(freq)} MHz" if freq else "",
                    "powerLevel": power,
                    "mse": None if is_ofdm else (-snr if snr else None),
                    "mer": snr if snr else None,
                    "latency": 0,
                    "corrError": corr,
                    "nonCorrError": uncorr,
                })
            except (ValueError, TypeError, IndexError) as e:
                log.warning("MB8611: failed to parse DS row: %s", e)

        return result

    def _parse_upstream(self, table) -> list:
        rows = table.find_all("tr")
        header_row = _find_header_row(rows)
        if header_row is None:
            return []

        headers = [c.get_text(strip=True).lower() for c in header_row.find_all(["th", "td"])]
        col = _map_us_columns(headers)
        result = []

        for row in rows:
            if row is header_row:
                continue
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 4:
                continue
            if _cell(cells, col["lock_status"]).lower() != "locked":
                continue
            try:
                modulation = _normalize_modulation(_cell(cells, col["modulation"]))
                freq = _parse_frequency(_cell(cells, col["frequency"]))
                power = _parse_number(_cell(cells, col["power"]))

                result.append({
                    "channelID": _cell(cells, col["channel_id"], "0"),
                    "type": modulation or "qam",
                    "frequency": f"{int(freq)} MHz" if freq else "",
                    "powerLevel": power,
                    "multiplex": "",
                })
            except (ValueError, TypeError, IndexError) as e:
                log.warning("MB8611: failed to parse US row: %s", e)

        return result


def _find_header_row(rows):
    for row in rows:
        cells = row.find_all(["th", "td"])
        if cells and not any(c.get("colspan") for c in cells) and len(cells) > 3:
            return row
    return None


def _cell(cells, index, default=""):
    if index is None or index >= len(cells):
        return default
    return cells[index]


def _map_ds_columns(headers):
    col = {k: None for k in ("channel_id", "lock_status", "channel_type", "modulation",
                              "frequency", "power", "snr", "corrected", "uncorrected")}
    for i, h in enumerate(headers):
        if "channel" in h and ("id" in h or "index" in h):
            col["channel_id"] = i
        elif "lock" in h:
            col["lock_status"] = i
        elif "channel" in h and "type" in h:
            col["channel_type"] = i
        elif "modulation" in h or "profile" in h:
            col["modulation"] = i
        elif "freq" in h:
            col["frequency"] = i
        elif any(kw in h for kw in ("power", "receive", "level")):
            col["power"] = i
        elif "snr" in h or "mer" in h:
            col["snr"] = i
        elif "corrected" in h and "un" not in h:
            col["corrected"] = i
        elif "uncorrect" in h:
            col["uncorrected"] = i
    # positional fallbacks
    if col["channel_id"] is None:
        col["channel_id"] = 0
    if col["lock_status"] is None:
        col["lock_status"] = 1
    if col["frequency"] is None:
        col["frequency"] = 3
    if col["corrected"] is None:
        col["corrected"] = 6
    if col["uncorrected"] is None:
        col["uncorrected"] = 7
    return col


def _map_us_columns(headers):
    col = {k: None for k in ("channel_id", "lock_status", "modulation", "frequency", "power")}
    for i, h in enumerate(headers):
        if "channel" in h and ("id" in h or "index" in h):
            col["channel_id"] = i
        elif "lock" in h:
            col["lock_status"] = i
        elif "modulation" in h:
            col["modulation"] = i
        elif "freq" in h:
            col["frequency"] = i
        elif any(kw in h for kw in ("power", "transmit", "level")):
            col["power"] = i
    if col["lock_status"] is None:
        col["lock_status"] = 1
    if col["frequency"] is None:
        col["frequency"] = 3
    return col


def _parse_frequency(s):
    if not s:
        return 0.0
    parts = s.strip().split()
    try:
        v = float(parts[0])
    except (IndexError, ValueError):
        return 0.0
    unit = parts[1].lower() if len(parts) > 1 else ""
    if unit == "hz":
        return v / 1_000_000
    if unit == "khz":
        return v / 1_000
    if unit == "mhz":
        return v
    if v > 1_000_000:
        return v / 1_000_000
    if v > 1_000:
        return v / 1_000
    return v


def _parse_number(s):
    if not s:
        return 0.0
    try:
        return float(s.strip().split()[0])
    except (IndexError, ValueError):
        return 0.0


def _normalize_modulation(mod):
    if not mod:
        return ""
    m = mod.upper().replace("-", "")
    if "OFDMA" in m:
        return "ofdma"
    if "OFDM" in m:
        return "ofdm"
    if "ATDMA" in m:
        return "atdma"
    if "QAM" in m:
        num = m.replace("QAM", "").strip()
        return f"qam_{num}" if num else "qam"
    return mod.lower()
