"""
Watchdog script to ensure the bot stays online
This script automatically restarts the bot if it crashes
"""

import subprocess
import time
import sys
import os
import logging
import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("watchdog.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("watchdog")

def run_bot():
    """Run the bot and restart it if it crashes"""
    # Keep track of crash count to avoid restart loops
    crashes = 0
    max_crashes = 10
    crash_timeout = 60  # seconds
    
    # Path to the bot script
    bot_script = "bot.py"
    
    # Python executable
    python_cmd = "py -3.11" if sys.platform == "win32" else "python"
    
    while True:
        start_time = time.time()
        
        # Start time message
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Starting bot at {current_time}")
        
        try:
            # Run the bot
            process = subprocess.Popen(f"{python_cmd} {bot_script}", shell=True)
            process.wait()
            
            # If the process exits with a 0 code, it was a clean shutdown
            if process.returncode == 0:
                logger.info("Bot shut down cleanly. Exiting watchdog.")
                break
            
            # Otherwise it crashed
            logger.error(f"Bot crashed with exit code {process.returncode}")
            
        except Exception as e:
            logger.error(f"Error running bot: {e}")
        
        # Check if it crashed immediately
        run_time = time.time() - start_time
        if run_time < 5:
            # Bot crashed too quickly
            crashes += 1
            logger.warning(f"Bot crashed after only {run_time:.1f} seconds. Crash count: {crashes}/{max_crashes}")
            
            if crashes >= max_crashes:
                logger.critical(f"Bot crashed {max_crashes} times in a row. Waiting {crash_timeout} seconds before trying again.")
                time.sleep(crash_timeout)
                crashes = 0
            else:
                # Short delay before restart
                time.sleep(2)
        else:
            # Bot ran for a while, reset crash counter
            crashes = 0
            logger.info(f"Bot ran for {run_time:.1f} seconds before exiting. Restarting...")
            time.sleep(2)

if __name__ == "__main__":
    logger.info("===== Watchdog starting =====")
    try:
        run_bot()
    except KeyboardInterrupt:
        logger.info("Watchdog stopped by user.")
    except Exception as e:
        logger.critical(f"Watchdog crashed: {e}")
    logger.info("===== Watchdog stopped =====") 