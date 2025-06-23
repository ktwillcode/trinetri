"""
Tests for Trinetri CLI functionality.

Tests the doctor health check command and dynamic instrumentation
using subprocess isolation to avoid import side effects.
"""

# Copyright 2025 Trinetri Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import subprocess
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

# Add src to Python path for direct imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trinetri_auto.cli import (
    check_environment_variables,
    check_otlp_endpoint, 
    check_dependencies,
    check_instrumentation_status,
    import_class_from_string,
    Colors
)


class TestEnvironmentChecks:
    """Test environment variable checking functionality."""
    
    def test_check_environment_variables_all_present(self):
        """Test environment check when all variables are present."""
        env_vars = {
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
            "OTEL_SERVICE_NAME": "test-service",
            "OTEL_EXPORTER_OTLP_HEADERS": "api-key=test",
            "OTEL_RESOURCE_ATTRIBUTES": "service.version=1.0.0",
            "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            "TRINETRI_CORRELATION_PREFIX": "test-"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            result = check_environment_variables()
            assert result is True
    
    def test_check_environment_variables_missing_required(self):
        """Test environment check when required variables are missing."""
        env_vars = {
            "OTEL_EXPORTER_OTLP_HEADERS": "api-key=test"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            result = check_environment_variables()
            assert result is False
    
    def test_check_environment_variables_partial_required(self):
        """Test environment check with only some required variables."""
        env_vars = {
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"
            # Missing OTEL_SERVICE_NAME
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            result = check_environment_variables()
            assert result is False


class TestOTLPConnectivity:
    """Test OTLP endpoint connectivity checking."""
    
    def test_check_otlp_endpoint_no_env_var(self):
        """Test OTLP check when no endpoint is configured."""
        with patch.dict(os.environ, {}, clear=True):
            result = check_otlp_endpoint()
            assert result is False
    
    @patch('urllib.request.urlopen')
    def test_check_otlp_endpoint_success(self, mock_urlopen):
        """Test successful OTLP endpoint connectivity."""
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"}, clear=True):
            result = check_otlp_endpoint()
            assert result is True
    
    @patch('urllib.request.urlopen')
    def test_check_otlp_endpoint_404_acceptable(self, mock_urlopen):
        """Test that 404 responses are acceptable for OTLP endpoints."""
        from urllib.error import HTTPError
        
        # Mock 404 response (acceptable for OTLP)
        mock_urlopen.side_effect = HTTPError(
            url="http://localhost:4318/v1/traces",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )
        
        with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"}, clear=True):
            result = check_otlp_endpoint()
            assert result is True
    
    @patch('urllib.request.urlopen')
    def test_check_otlp_endpoint_connection_error(self, mock_urlopen):
        """Test OTLP endpoint connection failure."""
        from urllib.error import URLError
        
        mock_urlopen.side_effect = URLError("Connection refused")
        
        with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"}, clear=True):
            result = check_otlp_endpoint()
            assert result is False


class TestDependencyChecks:
    """Test dependency checking functionality."""
    
    @patch('importlib.import_module')
    def test_check_dependencies_all_available(self, mock_import):
        """Test dependency check when all packages are available."""
        mock_import.return_value = MagicMock()
        
        result = check_dependencies()
        assert result is True
    
    @patch('importlib.import_module')
    def test_check_dependencies_missing_required(self, mock_import):
        """Test dependency check when required packages are missing."""
        def side_effect(package):
            if package in ["opentelemetry_api", "opentelemetry_sdk"]:
                raise ImportError(f"No module named '{package}'")
            return MagicMock()
        
        mock_import.side_effect = side_effect
        
        result = check_dependencies()
        assert result is False


class TestInstrumentationStatus:
    """Test instrumentation status checking."""
    
    @patch('trinetri_auto.cli.get_patch_status')
    def test_check_instrumentation_status_success(self, mock_get_status):
        """Test successful instrumentation status check."""
        mock_get_status.return_value = {
            "openai": True,
            "anthropic": True,
            "httpx": True,
            "langgraph": False,
            "crewai": False
        }
        
        result = check_instrumentation_status()
        assert result is True
    
    @patch('trinetri_auto.cli.get_patch_status')
    def test_check_instrumentation_status_error(self, mock_get_status):
        """Test instrumentation status check with error."""
        mock_get_status.side_effect = Exception("Patch status error")
        
        result = check_instrumentation_status()
        assert result is False


class TestClassImport:
    """Test dynamic class import functionality."""
    
    def test_import_class_from_string_valid(self):
        """Test importing a valid class from string."""
        # Import a built-in class for testing
        class_obj, class_name = import_class_from_string("builtins:dict")
        assert class_obj is dict
        assert class_name == "dict"
    
    def test_import_class_from_string_invalid_format(self):
        """Test error handling for invalid format."""
        with pytest.raises(ValueError, match="Format must be"):
            import_class_from_string("invalid_format")
    
    def test_import_class_from_string_missing_module(self):
        """Test error handling for missing module."""
        with pytest.raises(ImportError, match="Could not import module"):
            import_class_from_string("nonexistent_module:SomeClass")
    
    def test_import_class_from_string_missing_class(self):
        """Test error handling for missing class."""
        with pytest.raises(AttributeError, match="Class .* not found"):
            import_class_from_string("builtins:NonexistentClass")


class TestCLICommands:
    """Test CLI commands using subprocess for isolation."""
    
    def test_cli_doctor_help(self):
        """Test that doctor command help works."""
        result = subprocess.run(
            [sys.executable, "-m", "trinetri_auto.cli", "doctor", "--help"],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent / "src")}
        )
        
        assert result.returncode == 0
        assert "health checks" in result.stdout.lower()
        assert "environment variables" in result.stdout.lower()
    
    def test_cli_instrument_help(self):
        """Test that instrument command help works."""
        result = subprocess.run(
            [sys.executable, "-m", "trinetri_auto.cli", "instrument", "--help"],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent / "src")}
        )
        
        assert result.returncode == 0
        assert "dynamically instrument" in result.stdout.lower()
        assert "module:class" in result.stdout.lower()
    
    def test_cli_doctor_missing_env_vars(self):
        """Test doctor command with missing environment variables."""
        # Create clean environment without OTEL variables
        clean_env = {k: v for k, v in os.environ.items() 
                    if not k.startswith("OTEL_")}
        clean_env["PYTHONPATH"] = str(Path(__file__).parent.parent / "src")
        
        result = subprocess.run(
            [sys.executable, "-m", "trinetri_auto.cli", "doctor"],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            env=clean_env,
            timeout=30
        )
        
        # Should exit with error code due to missing environment variables
        assert result.returncode == 1
        assert "issues found" in result.stdout.lower() or "missing" in result.stdout.lower()
    
    def test_cli_doctor_with_env_vars(self):
        """Test doctor command with proper environment variables."""
        test_env = {
            **os.environ,
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
            "OTEL_SERVICE_NAME": "test-service",
            "PYTHONPATH": str(Path(__file__).parent.parent / "src")
        }
        
        result = subprocess.run(
            [sys.executable, "-m", "trinetri_auto.cli", "doctor", "--verbose"],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            env=test_env,
            timeout=30
        )
        
        # Should show environment variables as OK
        assert "Environment Variables" in result.stdout
        assert "OTEL_EXPORTER_OTLP_ENDPOINT" in result.stdout
        # May still fail on connectivity or dependencies, but env vars should be OK
    
    def test_cli_instrument_invalid_format(self):
        """Test instrument command with invalid format."""
        result = subprocess.run(
            [sys.executable, "-m", "trinetri_auto.cli", "instrument", "invalid_format", "--role", "test"],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent / "src")},
            timeout=30
        )
        
        assert result.returncode == 1
        assert "invalid input format" in result.stdout.lower() or "format must be" in result.stdout.lower()
    
    def test_cli_instrument_dry_run(self):
        """Test instrument command with dry run mode."""
        result = subprocess.run(
            [sys.executable, "-m", "trinetri_auto.cli", "instrument", "builtins:dict", "--role", "test", "--dry-run"],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent / "src")},
            timeout=30
        )
        
        # Should succeed in dry run mode
        assert result.returncode == 0
        assert "dry run" in result.stdout.lower()
        assert "would execute" in result.stdout.lower()
    
    def test_cli_version(self):
        """Test CLI version display."""
        result = subprocess.run(
            [sys.executable, "-m", "trinetri_auto.cli", "--version"],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent / "src")}
        )
        
        assert result.returncode == 0
        assert "0.1.0" in result.stdout


class TestColorOutput:
    """Test color output functionality."""
    
    def test_colors_defined(self):
        """Test that color constants are properly defined."""
        assert hasattr(Colors, 'GREEN')
        assert hasattr(Colors, 'RED')
        assert hasattr(Colors, 'YELLOW')
        assert hasattr(Colors, 'BLUE')
        assert hasattr(Colors, 'END')
        
        # Test that color codes are strings
        assert isinstance(Colors.GREEN, str)
        assert isinstance(Colors.RED, str)
        assert isinstance(Colors.END, str)


class TestCLIIntegration:
    """Integration tests for CLI functionality."""
    
    def test_doctor_with_mock_environment(self):
        """Test doctor command with controlled environment."""
        # Create a temporary script that sets up a controlled environment
        script_content = '''
import os
import sys
sys.path.insert(0, "{}")

# Set up test environment
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
os.environ["OTEL_SERVICE_NAME"] = "test-service"

from trinetri_auto.cli import cli
cli()
'''.format(str(Path(__file__).parent.parent / "src"))
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script_content)
            temp_script = f.name
        
        try:
            result = subprocess.run(
                [sys.executable, temp_script, "doctor"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Check that the command ran and produced expected output
            assert "Environment Variables" in result.stdout
            assert "Dependencies" in result.stdout
            
        finally:
            os.unlink(temp_script)


if __name__ == "__main__":
    pytest.main([__file__]) 