from http.server import BaseHTTPRequestHandler, HTTPServer

TWIML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Pause length="60"/>
</Response>
"""

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        print("RECEIVED POST FROM TWILIO:")
        try:
            print(body.decode())
        except:
            print(body)

        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.end_headers()
        self.wfile.write(TWIML)

server = HTTPServer(("0.0.0.0", 10000), Handler)
print("Server running...")
server.serve_forever()
