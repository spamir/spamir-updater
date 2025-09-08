import json
import os
import platform
import sys
import hashlib
import uuid
import socket
import datetime
from pathlib import Path


def load_version_from_config():
    """
    Load version from config.json in the current working directory
    
    Returns:
        str or None: Version string or None if not found
    """
    config_path = Path.cwd() / 'config.json'
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return str(config.get('version')) if config.get('version') else None
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return None


def save_version_to_config(version):
    """
    Save version to config.json in the current working directory
    
    Args:
        version (str): Version to save
    
    Returns:
        bool: Success status
    """
    config_path = Path.cwd() / 'config.json'
    config = {}
    
    try:
        # Try to read existing config
        with open(config_path, 'r') as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Config doesn't exist or is invalid, we'll create a new one
        pass
    
    config['version'] = version
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Failed to save version to config: {e}")
        return False


def get_system_info():
    """
    Get system information
    
    Returns:
        dict: System profile
    """
    profile = {
        'diag_version': '1.2',
        'os_platform': sys.platform,
        'python_version': sys.version,
        'os_architecture': platform.machine(),
        'runtime_ver': f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    }
    
    try:
        profile['os_release'] = platform.release()
    except Exception:
        profile['os_release'] = 'unknown'
    
    return profile


def get_system_component():
    """
    Get network interfaces to generate a unique system identifier
    
    Returns:
        str: MAC address or random hex string
    """
    try:
        import netifaces
        
        interfaces = []
        for interface in netifaces.interfaces():
            try:
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_LINK in addrs:
                    for link in addrs[netifaces.AF_LINK]:
                        mac = link.get('addr', '')
                        if mac and mac != '00:00:00:00:00:00':
                            # Check if it's a low-priority interface
                            is_low_priority = (
                                interface.lower().startswith('lo') or
                                interface.lower().startswith('vmnet') or
                                interface.lower().startswith('docker')
                            )
                            interfaces.append({
                                'name': interface,
                                'mac': mac.replace(':', '').upper(),
                                'priority': 1 if is_low_priority else 0
                            })
            except Exception:
                continue
        
        if not interfaces:
            return os.urandom(16).hex()
        
        # Sort by priority and name
        def sort_key(iface):
            preferred_prefixes = ['eth', 'en', 'wlan']
            name_lower = iface['name'].lower()
            
            for i, prefix in enumerate(preferred_prefixes):
                if name_lower.startswith(prefix):
                    return (iface['priority'], i, iface['name'])
            
            return (iface['priority'], len(preferred_prefixes), iface['name'])
        
        interfaces.sort(key=sort_key)
        return interfaces[0]['mac']
        
    except ImportError:
        # netifaces not available, try alternative method
        try:
            # Try to get MAC address using uuid
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                          for elements in range(0, 8*6, 8)][::-1])
            if mac != '00:00:00:00:00:00':
                return mac.replace(':', '').upper()
        except Exception:
            pass
        
        # Fallback to random
        return os.urandom(16).hex()


def generate_instance_signature(auth_token):
    """
    Generate a unique instance signature
    
    Args:
        auth_token (str): Shared authentication token
    
    Returns:
        str: UUID v5 based on system component and auth token
    """
    system_component = get_system_component()
    id_material = system_component + auth_token
    
    # Using OID namespace for UUID v5
    OID_NAMESPACE = uuid.UUID('6ba7b812-9dad-11d1-80b4-00c04fd430c8')
    return str(uuid.uuid5(OID_NAMESPACE, id_material))


def log_to_file(message, level='INFO'):
    """
    Simple logging function (can be enhanced later)
    
    Args:
        message (str): Message to log
        level (str): Log level (INFO, WARNING, ERROR, etc.)
    """
    timestamp = datetime.datetime.now().isoformat()
    print(f"[{timestamp}] [{level}] {message}")