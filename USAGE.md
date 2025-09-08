# Python Updater - Quick Start Guide

## Installation

```bash
pip install requests cryptography netifaces
```

## Basic Usage

### 1. Use the Baseplate Template

Start with `baseplate_app.py` as your template:

```python
# Copy baseplate_app.py to your project
cp baseplate_app.py my_app.py

# Edit and set your product ID
# Replace YOUR_PRODUCT_ID with your actual identifier
```

### 2. Minimal Example

```python
import asyncio
from lib.updater_client import UpdaterClient

async def main():
    # Create updater
    updater = UpdaterClient({
        'product_identifier': 'your-product-id-here'
    })
    
    # Check for updates (automatically handles everything)
    result = await updater.check_for_updates()
    
    print(f"Status: {result['status']}")
    print(f"Version: {result['version']}")

asyncio.run(main())
```

### 3. Integration with Existing App

Add these lines to your existing application:

```python
# In your initialization
from lib.updater_client import UpdaterClient

self.updater = UpdaterClient({
    'product_identifier': 'your-product-id'
})

# In your main loop or periodic check
result = await self.updater.check_for_updates()

if result['status'] == 'update_available':
    # Restart your application
    pass
```

## What It Does Automatically

When you call `check_for_updates()`, the updater:

1. **Connects** to the update server securely
2. **Downloads** any available updates
3. **Verifies** package integrity
4. **Installs** the update (replaces files)
5. **Executes** any server directives
6. **Reports** results back to server

## Configuration

The updater uses `config.json` in your app directory:

```json
{
  "version": "1.0",
  "productId": "your-product-id"
}
```

This file is created and updated automatically.

## Key Points

- **Product ID**: Get this from your update dashboard
- **Version Management**: Handled automatically via config.json
- **Directives**: Execute automatically when received
- **Security**: All communication is encrypted and signed

## Testing

Run the baseplate app with a test product ID:

```bash
# Edit baseplate_app.py and set a test product ID
python baseplate_app.py
```

## Directory Structure

```
your-app/
├── lib/                  # Updater module files
│   ├── updater_client.py
│   ├── encryption.py
│   ├── network.py
│   └── utils.py
├── baseplate_app.py      # Template application
├── config.json           # Auto-managed version file
└── your_app.py          # Your actual application
```

## Troubleshooting

1. **Import Error**: Ensure the lib/ directory is in your Python path
2. **Connection Failed**: Check internet connection and firewall
3. **No Updates**: Verify product ID matches dashboard configuration
4. **Directive Failed**: Check Python version (3.7+ required)