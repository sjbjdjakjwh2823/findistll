"""
Simple HTTP proxy to forward port 80 to 8004 for preciso-data.com
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

TARGET_HOST = "localhost"
TARGET_PORT = 8004

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.proxy_request()
    
    def do_POST(self):
        self.proxy_request()
    
    def proxy_request(self):
        try:
            # Build target URL
            target_url = f"http://{TARGET_HOST}:{TARGET_PORT}{self.path}"
            
            # Forward request
            headers = {}
            for header, value in self.headers.items():
                if header.lower() not in ['host', 'connection']:
                    headers[header] = value
            
            # Get request body for POST
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None
            
            # Create request
            req = urllib.request.Request(
                target_url,
                data=body,
                headers=headers,
                method=self.command
            )
            
            # Send request and get response
            with urllib.request.urlopen(req) as response:
                # Send response status
                self.send_response(response.status)
                
                # Send response headers
                for header, value in response.headers.items():
                    if header.lower() not in ['connection', 'transfer-encoding']:
                        self.send_header(header, value)
                self.end_headers()
                
                # Send response body
                self.wfile.write(response.read())
                
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head><title>Proxy Error</title></head>
            <body>
                <h1>Proxy Error</h1>
                <p>Failed to connect to backend server: {str(e)}</p>
                <p>Target: {TARGET_HOST}:{TARGET_PORT}</p>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())
    
    def log_message(self, format, *args):
        print(f"[Proxy] {self.address_string()} - {format % args}")

if __name__ == "__main__":
    PORT = 80
    print(f"Starting proxy server on port {PORT}")
    print(f"Forwarding to {TARGET_HOST}:{TARGET_PORT}")
    print(f"Access via: http://preciso-data.com/")
    print("Press Ctrl+C to stop")
    
    try:
        server = HTTPServer(('0.0.0.0', PORT), ProxyHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down proxy server...")
        server.shutdown()
    except PermissionError:
        print(f"\nERROR: Permission denied to bind to port {PORT}")
        print("You need administrator privileges to use port 80")
        print("\nAlternative: Use http://preciso-data.com:8004/ instead")
