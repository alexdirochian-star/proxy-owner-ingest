from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        self.rfile.read(length)

        self.send_response(200)
        self.send_header("Content-Type", "text/xml")
        self.end_headers()
        self.wfile.write(b"""
<Response>
  <Say>Please hold</Say>
</Response>
""")

server = HTTPServer(("0.0.0.0", 10000), Handler)
print("Server running...")
server.serve_forever()

