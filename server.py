"""
Simple HTTP server to keep the service alive and handle health checks
"""

import os
import logging
import threading
import socket
from flask import Flask, jsonify

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("server")

# Create Flask app
app = Flask(__name__)

# Health check endpoint
@app.route('/health')
def health_check():
    logger.info("Health check request received")
    return 'OK'

# Root endpoint (similar to the Express example)
@app.route('/')
def hello_world():
    return 'Discord Loan Bot is running!'

# Test endpoint for UnbelievaBoat API
@app.route('/api-status')
def api_status():
    return jsonify({
        "status": "online",
        "message": "API endpoint available"
    })

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
        # Start Flask app on the specified port and bind to all interfaces
        logger.info(f"Starting Flask server on port {port}...")
        app.run(host='0.0.0.0', port=port)
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
