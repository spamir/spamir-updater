#!/usr/bin/env python3
"""
Minimal Baseplate Application with Auto-Update Support
========================================================

This is a minimal template for applications using the Python updater module.
Simply replace YOUR_PRODUCT_ID with your actual product identifier and
add your application code where indicated.
"""

import asyncio
import signal
import sys
import os
from pathlib import Path

# Add the updater module to path (adjust if needed)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the updater client
from lib.updater_client import UpdaterClient


class Application:
    """Minimal application with auto-update support"""
    
    def __init__(self, product_id):
        self.product_id = product_id
        self.running = False
        self.updater = None
        
        # =====================================================
        # YOUR INITIALIZATION CODE HERE
        # =====================================================
        # Example:
        # self.config = self.load_config()
        # self.database = self.connect_db()
        
    async def check_for_updates(self):
        """Check for updates and execute directives"""
        try:
            # Create updater instance
            self.updater = UpdaterClient({
                'product_identifier': self.product_id,
                # Version will be loaded from config.json or default to 1.0
            })
            
            print(f"Checking for updates... (v{self.updater.current_version})")
            
            # Check for updates - this automatically:
            # 1. Downloads and installs updates
            # 2. Executes any directives from server
            # 3. Reports results back
            result = await self.updater.check_for_updates()
            
            if result['status'] == 'update_available':
                print(f"✅ Updated to version {result.get('new_version', 'unknown')}")
                print("Please restart the application.")
                return True  # Signal restart needed
            elif result['status'] == 'no_update':
                print(f"Application is up to date (v{result['version']})")
                
                # Log any directives that were processed
                if 'directiveResults' in result:
                    print(f"Processed {len(result['directiveResults'])} directive(s)")
            else:
                print(f"Update check status: {result['status']}")
                
        except Exception as e:
            print(f"Update check failed: {e}")
            
        return False
    
    async def main_loop(self):
        """Main application loop"""
        self.running = True
        
        # Initial update check
        needs_restart = await self.check_for_updates()
        if needs_restart:
            self.running = False
            return
        
        # Check for updates every hour
        update_interval = 3600  # seconds
        last_update_check = 0
        
        while self.running:
            # =====================================================
            # YOUR APPLICATION CODE HERE
            # =====================================================
            # This is where your main application logic goes.
            # Example:
            #
            # await self.process_data()
            # await self.handle_requests()
            # await self.update_ui()
            #
            # For this template, we'll just sleep:
            await asyncio.sleep(1)
            
            # Periodic update check
            last_update_check += 1
            if last_update_check >= update_interval:
                needs_restart = await self.check_for_updates()
                if needs_restart:
                    self.running = False
                    break
                last_update_check = 0
    
    def shutdown(self):
        """Clean shutdown"""
        print("\nShutting down...")
        self.running = False
        
        # =====================================================
        # YOUR CLEANUP CODE HERE
        # =====================================================
        # Example:
        # self.save_state()
        # self.close_connections()
    
    async def run(self):
        """Run the application"""
        print("=" * 60)
        print("Application Starting")
        print(f"Product ID: {self.product_id}")
        print("=" * 60)
        
        try:
            await self.main_loop()
        finally:
            self.shutdown()


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\nReceived signal {signum}")
    sys.exit(0)


async def main():
    """Main entry point"""
    # =========================================================
    # CONFIGURATION - CHANGE THIS
    # =========================================================
    PRODUCT_ID = "YOUR_PRODUCT_ID"  # Replace with your actual product ID
    
    if PRODUCT_ID == "YOUR_PRODUCT_ID":
        print("ERROR: Please set your product ID in the code!")
        print("Edit this file and replace YOUR_PRODUCT_ID with your actual product identifier.")
        sys.exit(1)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run application
    app = Application(PRODUCT_ID)
    await app.run()


if __name__ == "__main__":
    # Run the application
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)