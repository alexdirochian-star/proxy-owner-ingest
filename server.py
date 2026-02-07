from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length'))
        body = self.rfile.read(length)
        print("RECEIVED POST:")
        print(body.decode())

        self.send_response(200)
        self.send_header("Content-type", "text/xml")
        self.end_headers()
        self.wfile.write(b"<Response></Response>")

server = HTTPServer(("0.0.0.0", 10000), Handler)
print("Server running...")
server.serve_forever()
+
