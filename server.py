"""
Simple HTTP server to keep the service alive and handle health checks
"""

import os
import logging
import threading
import socket
import json
from flask import Flask, jsonify, request
import asyncio

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

# Diagnostic endpoint for UnbelievaBoat API
@app.route('/check-unbelievaboat', methods=['GET'])
def check_unbelievaboat():
    try:
        # Import here to avoid circular imports
        import config
        from unbelievaboat_integration import UnbelievaBoatAPI
        
        # Get guild_id and user_id from query parameters
        guild_id = request.args.get('guild_id')
        user_id = request.args.get('user_id')
        
        if not guild_id or not user_id:
            return jsonify({
                "status": "error",
                "message": "Missing required parameters. Use ?guild_id=XXX&user_id=YYY"
            }), 400
            
        # Create async function for testing
        async def run_test():
            # Create API client
            api = UnbelievaBoatAPI(
                api_key=config.UNBELIEVABOAT["API_KEY"],
                port=None,  # Use default port
                timeout=30
            )
            
            try:
                # Test connection
                balance = await api.get_user_balance(guild_id, user_id)
                
                if balance:
                    return {
                        "status": "success",
                        "message": "API connection successful",
                        "data": {
                            "balance": balance,
                            "api_enabled": config.UNBELIEVABOAT["ENABLED"],
                            "guild_id": guild_id,
                            "user_id": user_id
                        }
                    }
                else:
                    return {
                        "status": "error",
                        "message": "Could not retrieve balance",
                        "data": {
                            "api_enabled": config.UNBELIEVABOAT["ENABLED"],
                            "guild_id": guild_id,
                            "user_id": user_id
                        }
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"API error: {str(e)}",
                    "data": {
                        "api_enabled": config.UNBELIEVABOAT["ENABLED"],
                        "error": str(e)
                    }
                }
            finally:
                await api.close()
                
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_test())
        loop.close()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in check-unbelievaboat endpoint: {e}")
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500

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
