"""
Tests for Configuration Manager (Task 12)
Tests config loading, validation, and environment variable resolution

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7
Property Tests: 18, 19
"""

import pytest
import os
import tempfile
from pathlib import Path

from src.api.angelone.config_manager import (
    ConfigManager, ConfigValidationError, AngelOneConfig
)


class TestConfigManager:
    """Test configuration manager functionality"""
    
    @pytest.fixture
    def valid_config_yaml(self):
        """Create a valid config YAML file"""
        content = """
api_key: test_api_key
client_code: TEST123
password: test_password
totp_secret: JBSWY3DPEHPK3PXP
default_exchange: NSE
symbols:
  - RELIANCE-EQ
  - TCS-EQ
max_position_size: 50
max_daily_loss: 5000.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(content)
            return f.name
    
    @pytest.fixture
    def minimal_config_yaml(self):
        """Create a minimal config YAML file"""
        content = """
api_key: test_api_key
client_code: TEST123
password: test_password
totp_secret: JBSWY3DPEHPK3PXP
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(content)
            return f.name
    
    # ==================== Loading Tests ====================
    
    def test_load_valid_config(self, valid_config_yaml):
        """Test loading valid configuration"""
        manager = ConfigManager()
        config = manager.load(valid_config_yaml)
        
        assert config.api_key == 'test_api_key'
        assert config.client_code == 'TEST123'
        assert config.default_exchange == 'NSE'
        assert len(config.symbols) == 2
        assert 'RELIANCE-EQ' in config.symbols
        
        os.unlink(valid_config_yaml)
    
    def test_load_minimal_config(self, minimal_config_yaml):
        """Test loading minimal configuration with defaults"""
        manager = ConfigManager()
        config = manager.load(minimal_config_yaml)
        
        assert config.api_key == 'test_api_key'
        assert config.default_exchange == 'NSE'  # Default
        assert config.max_position_size == 100  # Default
        assert config.max_daily_loss == 10000.0  # Default
        assert config.symbols == []  # Default empty list
        
        os.unlink(minimal_config_yaml)
    
    def test_load_nonexistent_file(self):
        """Test loading from nonexistent file"""
        manager = ConfigManager()
        
        # Should raise error due to missing required fields
        with pytest.raises(ConfigValidationError):
            manager.load('nonexistent.yaml')
    
    # ==================== Validation Tests ====================
    
    def test_missing_required_field(self):
        """Test validation with missing required field"""
        content = """
api_key: test_api_key
client_code: TEST123
# Missing password and totp_secret
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(content)
            path = f.name
        
        manager = ConfigManager()
        
        with pytest.raises(ConfigValidationError) as exc_info:
            manager.load(path)
        
        assert 'password' in str(exc_info.value) or 'totp_secret' in str(exc_info.value)
        
        os.unlink(path)
    
    def test_invalid_exchange(self):
        """Test validation with invalid exchange"""
        content = """
api_key: test_api_key
client_code: TEST123
password: test_password
totp_secret: JBSWY3DPEHPK3PXP
default_exchange: INVALID
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(content)
            path = f.name
        
        manager = ConfigManager()
        
        with pytest.raises(ConfigValidationError) as exc_info:
            manager.load(path)
        
        assert 'exchange' in str(exc_info.value).lower()
        
        os.unlink(path)
    
    def test_invalid_numeric_field(self):
        """Test validation with invalid numeric field"""
        content = """
api_key: test_api_key
client_code: TEST123
password: test_password
totp_secret: JBSWY3DPEHPK3PXP
max_position_size: not_a_number
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(content)
            path = f.name
        
        manager = ConfigManager()
        
        with pytest.raises(ConfigValidationError) as exc_info:
            manager.load(path)
        
        assert 'max_position_size' in str(exc_info.value)
        
        os.unlink(path)
    
    # ==================== Environment Variable Tests ====================
    
    def test_env_var_resolution(self, monkeypatch):
        """Test environment variable resolution"""
        monkeypatch.setenv('ANGELONE_API_KEY', 'env_api_key')
        monkeypatch.setenv('ANGELONE_CLIENT_CODE', 'ENV123')
        monkeypatch.setenv('ANGELONE_PASSWORD', 'env_password')
        monkeypatch.setenv('ANGELONE_TOTP_SECRET', 'ENVTOTP123')
        
        manager = ConfigManager()
        config = manager.load()  # No file, use env vars
        
        assert config.api_key == 'env_api_key'
        assert config.client_code == 'ENV123'
        assert config.password == 'env_password'
    
    def test_env_var_syntax_in_yaml(self, monkeypatch):
        """Test ${VAR_NAME} syntax in YAML"""
        monkeypatch.setenv('MY_API_KEY', 'resolved_api_key')
        
        content = """
api_key: ${MY_API_KEY}
client_code: TEST123
password: test_password
totp_secret: JBSWY3DPEHPK3PXP
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(content)
            path = f.name
        
        manager = ConfigManager()
        config = manager.load(path)
        
        assert config.api_key == 'resolved_api_key'
        
        os.unlink(path)
    
    def test_file_overrides_env(self, monkeypatch, valid_config_yaml):
        """Test that file values override environment variables"""
        monkeypatch.setenv('ANGELONE_API_KEY', 'env_api_key')
        
        manager = ConfigManager()
        config = manager.load(valid_config_yaml)
        
        # File value should be used, not env var
        assert config.api_key == 'test_api_key'
        
        os.unlink(valid_config_yaml)
    
    # ==================== Default Values Tests ====================
    
    def test_default_values(self, minimal_config_yaml):
        """Test that default values are applied"""
        manager = ConfigManager()
        config = manager.load(minimal_config_yaml)
        
        assert config.default_exchange == 'NSE'
        assert config.market_open == '09:15'
        assert config.market_close == '15:30'
        assert config.max_position_size == 100
        assert config.max_daily_loss == 10000.0
        assert config.stop_loss_percent == 2.0
        assert config.websocket_enabled is True
        assert config.log_level == 'INFO'
        assert config.initial_capital == 100000.0
        
        os.unlink(minimal_config_yaml)
    
    # ==================== Multi-Symbol Tests ====================
    
    def test_multiple_symbols(self, valid_config_yaml):
        """Test loading multiple symbols"""
        manager = ConfigManager()
        config = manager.load(valid_config_yaml)
        
        assert len(config.symbols) == 2
        assert 'RELIANCE-EQ' in config.symbols
        assert 'TCS-EQ' in config.symbols
        
        os.unlink(valid_config_yaml)
    
    def test_empty_symbols_list(self, minimal_config_yaml):
        """Test empty symbols list"""
        manager = ConfigManager()
        config = manager.load(minimal_config_yaml)
        
        assert config.symbols == []
        
        os.unlink(minimal_config_yaml)
    
    # ==================== Utility Tests ====================
    
    def test_get_method(self, valid_config_yaml):
        """Test get method for accessing config values"""
        manager = ConfigManager()
        manager.load(valid_config_yaml)
        
        assert manager.get('api_key') == 'test_api_key'
        assert manager.get('nonexistent', 'default') == 'default'
        
        os.unlink(valid_config_yaml)
    
    def test_config_to_dict(self, valid_config_yaml):
        """Test converting config to dictionary"""
        manager = ConfigManager()
        config = manager.load(valid_config_yaml)
        
        config_dict = config.to_dict()
        
        assert config_dict['client_code'] == 'TEST123'
        assert config_dict['password'] == '***'  # Should be masked
        assert config_dict['totp_secret'] == '***'  # Should be masked
        
        os.unlink(valid_config_yaml)
    
    def test_reload_config(self, valid_config_yaml):
        """Test reloading configuration"""
        manager = ConfigManager(valid_config_yaml)
        config1 = manager.load()
        config2 = manager.reload()
        
        assert config1.api_key == config2.api_key
        
        os.unlink(valid_config_yaml)
    
    def test_create_template(self):
        """Test creating config template"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'config.yaml')
            
            ConfigManager.create_template(path)
            
            assert os.path.exists(path)
            
            with open(path, 'r') as f:
                content = f.read()
            
            assert 'api_key' in content
            assert 'client_code' in content
            assert 'symbols' in content


class TestConfigValidationProperty:
    """
    Property Test 18: Config Validation
    Validates: Requirements 8.2, 8.3
    
    All required fields must be validated
    """
    
    @pytest.mark.parametrize("missing_field", ['api_key', 'client_code', 'password', 'totp_secret'])
    def test_missing_required_field_raises_error(self, missing_field):
        """Property: Missing required field raises ConfigValidationError"""
        fields = {
            'api_key': 'test',
            'client_code': 'test',
            'password': 'test',
            'totp_secret': 'test'
        }
        
        # Remove one required field
        del fields[missing_field]
        
        content = '\n'.join(f'{k}: {v}' for k, v in fields.items())
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(content)
            path = f.name
        
        manager = ConfigManager()
        
        with pytest.raises(ConfigValidationError):
            manager.load(path)
        
        os.unlink(path)


class TestEnvVarResolutionProperty:
    """
    Property Test 19: Environment Variable Resolution
    Validates: Requirements 8.2, 8.5
    
    Environment variables must be resolved correctly
    """
    
    def test_all_env_vars_resolved(self, monkeypatch):
        """Property: All environment variables are resolved"""
        monkeypatch.setenv('ANGELONE_API_KEY', 'env_key')
        monkeypatch.setenv('ANGELONE_CLIENT_CODE', 'env_code')
        monkeypatch.setenv('ANGELONE_PASSWORD', 'env_pass')
        monkeypatch.setenv('ANGELONE_TOTP_SECRET', 'env_secret')
        
        manager = ConfigManager()
        config = manager.load()
        
        assert config.api_key == 'env_key'
        assert config.client_code == 'env_code'
        assert config.password == 'env_pass'
        assert config.totp_secret == 'env_secret'
    
    def test_partial_env_vars(self, monkeypatch):
        """Property: Partial env vars combined with file values"""
        monkeypatch.setenv('ANGELONE_API_KEY', 'env_key')
        
        content = """
client_code: file_code
password: file_pass
totp_secret: file_secret
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(content)
            path = f.name
        
        manager = ConfigManager()
        config = manager.load(path)
        
        assert config.api_key == 'env_key'  # From env
        assert config.client_code == 'file_code'  # From file
        
        os.unlink(path)


class TestAngelOneConfig:
    """Test AngelOneConfig dataclass"""
    
    def test_config_creation(self):
        """Test creating AngelOneConfig"""
        config = AngelOneConfig(
            api_key='test_key',
            client_code='TEST123',
            password='test_pass',
            totp_secret='test_secret'
        )
        
        assert config.api_key == 'test_key'
        assert config.default_exchange == 'NSE'  # Default
        assert config.symbols == []  # Default
    
    def test_config_with_all_fields(self):
        """Test creating AngelOneConfig with all fields"""
        config = AngelOneConfig(
            api_key='test_key',
            client_code='TEST123',
            password='test_pass',
            totp_secret='test_secret',
            default_exchange='NFO',
            symbols=['NIFTY', 'BANKNIFTY'],
            max_position_size=50,
            max_daily_loss=5000.0,
            websocket_enabled=False
        )
        
        assert config.default_exchange == 'NFO'
        assert len(config.symbols) == 2
        assert config.max_position_size == 50
        assert config.websocket_enabled is False
