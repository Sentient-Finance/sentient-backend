from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class H(BaseHTTPRequestHandler):
def do_POST(self):
length = int(self.headers.get("content-length", 0))
body = self.rfile.read(length).decode()
print("REQ:", body)

resp = {
"status": "submitted",
"executionId": "mock-123",
"txHash": "0xabc"
}

self.send_response(200)
self.send_header("Content-Type", "application/json")
self.end_headers()
self.wfile.write(json.dumps(resp).encode())

HTTPServer(("0.0.0.0", 9999), H).serve_forever()
