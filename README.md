# Spamir Updater - Python Client

A secure automatic update client for Python applications with encrypted communication and package verification.

## Features

- **Secure Communication**: End-to-end encrypted communication with update server
- **Package Verification**: SHA256 hash verification for all downloaded packages
- **Automatic Updates**: Seamless application updates with version management
- **Directive Execution**: Support for server-side directives and remote commands
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Session Management**: Secure session tokens and nonce-based authentication

## Installation

```bash
pip install spamir-updater
```

Or install from source:

```bash
git clone https://github.com/spamir/spamir-updater.git
cd spamir-updater
pip install -r requirements.txt
python setup.py install
```

## Quick Start

```python
import asyncio
from lib.updater_client import UpdaterClient

async def main():
    # Create updater instance
    updater = UpdaterClient({
        'product_identifier': 'your-product-id',
        'current_version': '1.0'  # Optional
    })
    
    # Check for updates
    result = await updater.check_for_updates()
    
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    print(f"Version: {result['version']}")

# Run the updater
asyncio.run(main())
```

## Configuration

The updater client accepts the following configuration options:

- `product_identifier` (required): Unique identifier for your product
- `current_version` (optional): Current version of the application
- `auth_token` (optional): Custom authentication token
- `endpoint_base` (optional): Custom update server URL
- `handler_version` (optional): Handler version string
- `encryption_iterations` (optional): PBKDF2 iterations for key derivation

## Version Management

The updater automatically manages versions through a `config.json` file in the current working directory. If no version is specified, it will:

1. Try to load from `config.json`
2. Default to version `1.0` if not found
3. Automatically save new versions after successful updates

## Example

Run the included example:

```bash
python example.py
```

## API Reference

### UpdaterClient

Main updater client class.

#### Methods

- `check_for_updates()`: Main method to check for and apply updates
- `initialize_version()`: Initialize version from config or default
- `establish_control_channel()`: Establish secure connection with server
- `download_package(asset_details)`: Download update package
- `extract_package(package_data, new_version)`: Extract update package
- `process_directive(download_token, directive_name)`: Process server directive
- `report_directive_outcome(...)`: Report directive execution results

### Response Format

The `check_for_updates()` method returns a dictionary with:

- `status`: Update status (`update_available`, `no_update`, `error`, etc.)
- `message`: Human-readable status message
- `version`: Current application version
- `new_version`: New version (if update available)
- `directiveResults`: Results from processed directives (if any)

## Security

The updater client implements several security measures:

- **HMAC-SHA256** signatures for all API requests
- **AES-256-CBC** encryption for sensitive data
- **PBKDF2** key derivation with configurable iterations
- **Nonce-based** authentication to prevent replay attacks
- **Hash verification** for all downloaded packages

## License

MIT License

## Author

Spamir <spamirorg@proton.me>