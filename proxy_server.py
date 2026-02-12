import http.server
import socketserver
import urllib.request
import urllib.error

PORT = 8004
NEXT_JS_URL = "http://localhost:3000"
FASTAPI_URL = "http://localhost:8000"

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.proxy_request()

    def do_POST(self):
        self.proxy_request()

    def proxy_request(self):
        if self.path.startswith("/api") or self.path.startswith("/cases") or self.path.startswith("/zkp") or self.path.startswith("/graph"):
            target_url = f"{FASTAPI_URL}{self.path}"
        else:
            target_url = f"{NEXT_JS_URL}{self.path}"

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else None

        req = urllib.request.Request(target_url, data=post_data, method=self.command)
        for header, value in self.headers.items():
            if header.lower() not in ['host', 'content-length']:
                req.add_header(header, value)

        try:
            with urllib.request.urlopen(req) as response:
                self.send_response(response.status)
                for header, value in response.getheaders():
                    self.send_header(header, value)
                self.end_headers()
                self.wfile.write(response.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

with socketserver.TCPServer(("", PORT), ProxyHandler) as httpd:
    print(f"Proxy serving at port {PORT}")
    httpd.serve_forever()
