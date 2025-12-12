import json
import os
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner
from src.cli import cli

runner = CliRunner()

def test_config_persistence(tmp_path):
    # Mock CONFIG_FILE_PATH to point to tmp_path/config.json
    # We need to patch it where it is imported/used.
    # It's used in src.utils.config.load_config and save_config.
    
    config_path = tmp_path / "config.json"
    
    with patch("src.utils.config.CONFIG_FILE_PATH", config_path):
        # 1. Set a value
        result = runner.invoke(cli, ["config", "set", "simple_mode", "true"])
        assert result.exit_code == 0
        assert "simple_mode = True" in result.output
        
        # 2. Verify file content
        assert config_path.exists()
        with open(config_path) as f:
            data = json.load(f)
            assert data["simple_mode"] is True
            
        # 3. Get value
        result = runner.invoke(cli, ["config", "get", "simple_mode"])
        assert result.exit_code == 0
        assert "simple_mode" in result.output
        assert "True" in result.output
        
        # 4. List values
        result = runner.invoke(cli, ["config", "list"])
        assert result.exit_code == 0
        assert "simple_mode" in result.output
        assert "True" in result.output

def test_config_defaults(tmp_path):
    config_path = tmp_path / "config.json"
    # Ensure no file exists
    if config_path.exists():
        config_path.unlink()
        
    with patch("src.utils.config.CONFIG_FILE_PATH", config_path):
        # List should show defaults
        result = runner.invoke(cli, ["config", "list"])
        assert result.exit_code == 0
        assert "simple_mode" in result.output
        assert "False" in result.output # Default
