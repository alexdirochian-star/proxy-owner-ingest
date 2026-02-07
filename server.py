from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
import os
import json
import base64
import urllib.request
import urllib.parse

# ========= CONFIG (Render Environment Variables) =========
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")          # your Twilio number, e.g. +18557033886
OWNER_PHONE = os.getenv("OWNER_PHONE", "")                 # your real phone, e.g. +1XXXXXXXXXX
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")         # e.g. https://proxy-owner-ingest.onrender.com

# Messages (simple MVP text)
SMS_TO_CALLER = os.getenv(
    "SMS_TO_CALLER",
    "Sorry we missed your call. Reply with your name and address and we’ll call you back shortly."
)
SMS_TO_OWNER_TEMPLATE = os.getenv(
    "SMS_TO_OWNER_TEMPLATE",
    "Missed call: {caller}. Please call back."
)

def twilio_sms(to_number: str, body: str) -> tuple[int, str]:
    """
    Sends SMS via Twilio REST API.
    Returns (http_status, response_text).
    """
    if not (ACCOUNT_SID and AUTH_TOKEN and FROM_NUMBER):
        return (0, "Missing TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER")

    url = f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Messages.json"
    data = urllib.parse.urlencode({
        "To": to_number,
        "From": FROM_NUMBER,
        "Body": body,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    auth = base64.b64encode(f"{ACCOUNT_SID}:{AUTH_TOKEN}".encode("utf-8")).decode("utf-8")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return (resp.getcode(), resp.read().decode("utf-8", errors="ignore"))
    except Exception as e:
        return (0, f"SMS send error: {repr(e)}")

def twiml(xml: str) -> bytes:
    if not xml.strip().startswith("<?xml"):
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml
    return xml.encode("utf-8")

class Handler(BaseHTTPRequestHandler):
    # --- healthchecks ---
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    # --- twilio webhooks ---
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(length)
        raw = body_bytes.decode("utf-8", errors="ignore")
        params = parse_qs(raw)

        # Common Twilio params
        caller = params.get("From", [""])[0]
        call_sid = params.get("CallSid", [""])[0]

        # Route by path
        if self.path == "/" or self.path.startswith("/incoming"):
            self.handle_incoming_call(caller=caller, call_sid=call_sid)
            return

        if self.path.startswith("/dial-status"):
            self.handle_dial_status(params=params, caller=caller, call_sid=call_sid)
            return

        # Unknown path
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not found")

    def handle_incoming_call(self, caller: str, call_sid: str):
        # Minimal guardrails
        if not (OWNER_PHONE and PUBLIC_BASE_URL):
            # Tell caller we have a config problem but keep Twilio happy
            resp = twiml("""
<Response>
  <Say>We are unable to take your call right now.</Say>
  <Hangup/>
</Response>
""")
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(resp)
            print("CONFIG ERROR: missing OWNER_PHONE or PUBLIC_BASE_URL")
            return

        # Dial owner; after Dial ends Twilio will POST to /dial-status with DialCallStatus
        action_url = f"{PUBLIC_BASE_URL.rstrip('/')}/dial-status"

        # Keep it very simple: try owner for 20 seconds
        resp = twiml(f"""
<Response>
  <Dial timeout="20" action="{action_url}" method="POST">
    <Number>{OWNER_PHONE}</Number>
  </Dial>
</Response>
""")

        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.end_headers()
        self.wfile.write(resp)

        print("INCOMING:", {"caller": caller, "call_sid": call_sid, "action_url": action_url})

    def handle_dial_status(self, params, caller: str, call_sid: str):
        # Dial result from Twilio
        dial_status = params.get("DialCallStatus", [""])[0]   # completed | no-answer | busy | failed
        dial_call_sid = params.get("DialCallSid", [""])[0]

        print("DIAL RESULT:", {
            "caller": caller,
            "call_sid": call_sid,
            "dial_call_sid": dial_call_sid,
            "dial_status": dial_status
        })

        # If owner DID NOT answer -> "missed call recovery"
        missed = dial_status != "completed"

        if missed:
            # 1) SMS to caller (may fail if toll-free SMS not verified; we still attempt)
            if caller:
                st1, resp1 = twilio_sms(caller, SMS_TO_CALLER)
                print("SMS_TO_CALLER:", {"to": caller, "status": st1, "resp": resp1[:200]})

            # 2) SMS to owner (always useful)
            if OWNER_PHONE:
                msg_owner = SMS_TO_OWNER_TEMPLATE.format(caller=caller or "unknown")
                st2, resp2 = twilio_sms(OWNER_PHONE, msg_owner)
                print("SMS_TO_OWNER:", {"to": OWNER_PHONE, "status": st2, "resp": resp2[:200]})

        # End call politely (caller will be gone anyway if missed, but keep Twilio happy)
        resp = twiml("""
<Response>
  <Say>Thank you. Goodbye.</Say>
  <Hangup/>
</Response>
""")
        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.end_headers()
        self.wfile.write(resp)

def main():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print("Server running on port", port)
    server.serve_forever()

if __name__ == "__main__":
    main()
