"""
Python Updater Client Module

Automatic update client for Python applications
Handles secure communication with update server and package management
"""

from .lib.updater_client import UpdaterClient

__version__ = "1.0.0"
__all__ = ["UpdaterClient", "create_updater"]


def create_updater(options):
    """
    Create a new updater instance
    
    Args:
        options (dict): Configuration options
            - product_identifier (str): Unique product identifier (required)
            - current_version (str, optional): Current version (reads from config.json if not provided)
    
    Returns:
        UpdaterClient: Updater client instance
    """
    return UpdaterClient(options)