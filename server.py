from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
import os
import base64
import urllib.request
import urllib.parse

# ================= CONFIG =================
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")     # +18557033886
OWNER_PHONE = os.getenv("OWNER_PHONE", "")            # +1XXXXXXXXXX
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")    # https://proxy-owner-ingest.onrender.com

SMS_TO_CALLER = os.getenv(
    "SMS_TO_CALLER",
    "Sorry we missed your call. A technician will call you back shortly."
)

SMS_TO_OWNER = os.getenv(
    "SMS_TO_OWNER",
    "Missed call from {caller}. Please call back."
)

# ================= HELPERS =================
def twiml(xml: str) -> bytes:
    if not xml.strip().startswith("<?xml"):
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml
    return xml.encode("utf-8")

def send_sms(to_number: str, body: str):
    if not (ACCOUNT_SID and AUTH_TOKEN and FROM_NUMBER and to_number):
        print("SMS SKIPPED (missing config)")
        return

    url = f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Messages.json"
    data = urllib.parse.urlencode({
        "To": to_number,
        "From": FROM_NUMBER,
        "Body": body,
    }).encode()

    req = urllib.request.Request(url, data=data, method="POST")
    auth = base64.b64encode(f"{ACCOUNT_SID}:{AUTH_TOKEN}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print("SMS SENT:", to_number, r.getcode())
    except Exception as e:
        print("SMS ERROR:", repr(e))

# ================= SERVER =================
class Handler(BaseHTTPRequestHandler):

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode(errors="ignore")
        params = parse_qs(raw)

        caller = params.get("From", [""])[0]
        path = self.path

        print("POST PATH:", path)
        print("FROM:", caller)
        print("RAW:", raw)

        # -------- INCOMING CALL --------
        if path == "/" or path == "/incoming":
            action_url = ""
            can_dial = bool(OWNER_PHONE and PUBLIC_BASE_URL)

            if can_dial:
                action_url = PUBLIC_BASE_URL.rstrip("/") + "/dial-status"

            # ВСЕГДА говорим Please hold
            resp = """
<Response>
  <Say>Please hold.</Say>
"""

            # Dial ТОЛЬКО если есть куда и кому
            if can_dial:
                resp += f"""
  <Dial timeout="20" action="{action_url}" method="POST">
    <Number>{OWNER_PHONE}</Number>
  </Dial>
"""
            else:
                print("DIAL SKIPPED: missing OWNER_PHONE or PUBLIC_BASE_URL")

            resp += """
</Response>
"""
            self._reply_xml(resp)
            return

        # -------- DIAL CALLBACK --------
        if path == "/dial-status":
            dial_status = params.get("DialCallStatus", [""])[0]
            print("DIAL STATUS:", dial_status)

            if dial_status != "completed":
                if caller:
                    send_sms(caller, SMS_TO_CALLER)
                if OWNER_PHONE:
                    send_sms(
                        OWNER_PHONE,
                        SMS_TO_OWNER.format(caller=caller or "unknown")
                    )

            self._reply_xml("<Response><Hangup/></Response>")
            return

        # -------- UNKNOWN --------
        self.send_response(404)
        self.end_headers()

    def _reply_xml(self, xml_body: str):
        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.end_headers()
        self.wfile.write(twiml(xml_body))

# ================= RUN =================
def main():
    port = int(os.getenv("PORT", "10000"))

    # 🔴 КРИТИЧЕСКИЙ ЛОГ — ДОЛЖЕН БЫТЬ ВСЕГДА
    print("BOOT CONFIG:", {
        "ACCOUNT_SID": bool(ACCOUNT_SID),
        "AUTH_TOKEN": bool(AUTH_TOKEN),
        "FROM_NUMBER": FROM_NUMBER,
        "OWNER_PHONE": OWNER_PHONE,
        "PUBLIC_BASE_URL": PUBLIC_BASE_URL,
    })

    server = HTTPServer(("0.0.0.0", port), Handler)
    print("Server running on port", port)
    server.serve_forever()

if __name__ == "__main__":
    main()
