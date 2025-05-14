"""
Simple HTTP server to keep the service alive
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import threading
import logging
import socket

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("server")

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
            logger.info("Health check request received")
        else:
            self.send_response(404)
            self.end_headers()
            logger.info(f"Invalid path requested: {self.path}")

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def run_server():
    # Get port from environment variable, default to 10000 if not set
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Attempting to start server on port {port}")
    
    # Check if port is already in use
    if is_port_in_use(port):
        logger.error(f"Port {port} is already in use!")
        raise RuntimeError(f"Port {port} is already in use")
    
    try:
        # Create server with explicit host and port
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        logger.info(f"Server created successfully, binding to 0.0.0.0:{port}")
        
        # Start the server
        logger.info("Starting server...")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise

if __name__ == "__main__":
    logger.info("Starting application...")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Environment variables: PORT={os.environ.get('PORT', 'not set')}")
    
    # Start the HTTP server in a separate thread
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True  # This ensures the thread will exit when the main program exits
    server_thread.start()
    logger.info("HTTP server thread started")
    
    # Import and run the bot
    try:
        import bot
        import asyncio
        logger.info("Starting Discord bot...")
        asyncio.run(bot.main())
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise
