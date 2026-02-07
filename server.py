from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
import os
import base64
import urllib.request
import urllib.parse

# ================== CONFIG ==================
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")      # Twilio number +1...
OWNER_PHONE = os.getenv("OWNER_PHONE", "")             # Owner real phone +1...
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")     # https://proxy-owner-ingest.onrender.com

SMS_TO_CALLER = os.getenv(
    "SMS_TO_CALLER",
    "Sorry we missed your call. A technician will call you back shortly."
)

SMS_TO_OWNER_TEMPLATE = os.getenv(
    "SMS_TO_OWNER_TEMPLATE",
    "Missed call from {caller}. Please call back."
)

# ================== HELPERS ==================
def twiml(xml: str) -> bytes:
    if not xml.strip().startswith("<?xml"):
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml
    return xml.encode("utf-8")

def send_sms(to_number: str, body: str):
    if not (ACCOUNT_SID and AUTH_TOKEN and FROM_NUMBER and to_number):
        print("SMS SKIPPED: missing config")
        return

    url = f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Messages.json"
    data = urllib.parse.urlencode({
        "To": to_number,
        "From": FROM_NUMBER,
        "Body": body,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    auth = base64.b64encode(f"{ACCOUNT_SID}:{AUTH_TOKEN}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print("SMS SENT:", to_number, resp.getcode())
    except Exception as e:
        print("SMS ERROR:", repr(e))

# ================== SERVER ==================
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
        body = self.rfile.read(length).decode("utf-8", errors="ignore")
        params = parse_qs(body)

        caller = params.get("From", [""])[0]
        path = self.path

        # ---------- INCOMING CALL ----------
        if path == "/" or path == "/incoming":
            if not (OWNER_PHONE and PUBLIC_BASE_URL):
                resp = twiml("""
<Response>
  <Say>We are unable to take your call right now.</Say>
  <Hangup/>
</Response>
""")
            else:
                action_url = PUBLIC_BASE_URL.rstrip("/") + "/dial-status"
                resp = twiml(f"""
<Response>
  <Say>Please hold.</Say>
  <Dial timeout="20" action="{action_url}" method="POST">
    <Number>{OWNER_PHONE}</Number>
  </Dial>
</Response>
""")
                print("INCOMING CALL FROM:", caller)

            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(resp)
            return

        # ---------- DIAL RESULT ----------
        if path == "/dial-status":
            dial_status = params.get("DialCallStatus", [""])[0]
            print("DIAL STATUS:", dial_status)

            if dial_status != "completed":
                # Missed call → SMS
                if caller:
                    send_sms(caller, SMS_TO_CALLER)

                if OWNER_PHONE:
                    send_sms(
                        OWNER_PHONE,
                        SMS_TO_OWNER_TEMPLATE.format(caller=caller or "unknown")
                    )

            resp = twiml("""
<Response>
  <Hangup/>
</Response>
""")
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(resp)
            return

        # ---------- FALLBACK ----------
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not found")

# ================== RUN ==================
def main():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print("Server running on port", port)
    server.serve_forever()

if __name__ == "__main__":
    main()
