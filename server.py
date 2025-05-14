"""
Simple HTTP server to keep the service alive
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import threading

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Starting HTTP server on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    # Start the HTTP server in a separate thread
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True  # This ensures the thread will exit when the main program exits
    server_thread.start()
    
    # Import and run the bot
    import bot
    import asyncio
    asyncio.run(bot.main()) 