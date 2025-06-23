"""
Trinetri CLI - Command Line Interface for Multi-Agent LLM Observability.

Provides health checking, dynamic instrumentation, and diagnostic tools.
"""

# Copyright 2024 Trinetri
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
import time
import importlib
import urllib.request
import urllib.error
from typing import Optional, Tuple, Any

import click

from .agent import instrument_agent
from ._instrument import get_patch_status


# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_status(message: str, status: str, details: str = "") -> None:
    """Print a formatted status message with color coding."""
    if status == "OK":
        status_color = Colors.GREEN
        status_symbol = "✅"
    elif status == "WARN":
        status_color = Colors.YELLOW
        status_symbol = "⚠️ "
    elif status == "FAIL":
        status_color = Colors.RED
        status_symbol = "❌"
    else:
        status_color = Colors.BLUE
        status_symbol = "ℹ️ "
    
    click.echo(f"{status_symbol} {Colors.BOLD}{message}{Colors.END}: "
               f"{status_color}{status}{Colors.END}")
    if details:
        click.echo(f"   {Colors.CYAN}{details}{Colors.END}")


def check_environment_variables() -> bool:
    """Check for required and recommended environment variables."""
    print_status("Environment Variables", "INFO", "Checking OTLP configuration...")
    
    required_vars = {
        "OTEL_EXPORTER_OTLP_ENDPOINT": "OpenTelemetry endpoint",
        "OTEL_SERVICE_NAME": "Service identification"
    }
    
    optional_vars = {
        "OTEL_EXPORTER_OTLP_HEADERS": "Authentication headers",
        "OTEL_RESOURCE_ATTRIBUTES": "Resource metadata",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "Protocol specification",
        "TRINETRI_CORRELATION_PREFIX": "Custom correlation ID prefix"
    }
    
    all_good = True
    
    # Check required variables
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            print_status(f"  {var}", "OK", f"{description}: {value}")
        else:
            print_status(f"  {var}", "FAIL", f"Missing {description}")
            all_good = False
    
    # Check optional variables
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value:
            print_status(f"  {var}", "OK", f"{description}: {value}")
        else:
            print_status(f"  {var}", "WARN", f"Optional {description} not set")
    
    return all_good


def check_otlp_endpoint() -> bool:
    """Check if OTLP endpoint is reachable."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        print_status("OTLP Endpoint Connectivity", "FAIL", 
                    "No OTEL_EXPORTER_OTLP_ENDPOINT configured")
        return False
    
    # Parse endpoint and construct health check URL
    try:
        if endpoint.endswith("/v1/traces"):
            health_url = endpoint.replace("/v1/traces", "/health")
        elif endpoint.endswith("/"):
            health_url = f"{endpoint}v1/traces"
        else:
            health_url = f"{endpoint}/v1/traces"
        
        print_status("OTLP Endpoint Connectivity", "INFO", 
                    f"Testing connection to {endpoint}...")
        
        # Attempt connection with timeout
        req = urllib.request.Request(health_url, method="HEAD")
        req.add_header("User-Agent", "Trinetri-HealthCheck/0.1")
        
        start_time = time.time()
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                response_time = int((time.time() - start_time) * 1000)
                status_code = response.getcode()
                
                if 200 <= status_code < 300:
                    print_status("OTLP Endpoint Connectivity", "OK", 
                                f"HTTP {status_code} in {response_time}ms")
                    return True
                else:
                    print_status("OTLP Endpoint Connectivity", "WARN", 
                                f"HTTP {status_code} in {response_time}ms")
                    return False
                    
        except urllib.error.HTTPError as e:
            response_time = int((time.time() - start_time) * 1000)
            if e.code == 404:
                print_status("OTLP Endpoint Connectivity", "WARN", 
                            f"Endpoint exists but no health check (HTTP 404) in {response_time}ms")
                return True  # 404 is acceptable for OTLP endpoints
            else:
                print_status("OTLP Endpoint Connectivity", "FAIL", 
                            f"HTTP {e.code}: {e.reason} in {response_time}ms")
                return False
                
        except urllib.error.URLError as e:
            print_status("OTLP Endpoint Connectivity", "FAIL", 
                        f"Connection failed: {e.reason}")
            return False
            
        except Exception as e:
            print_status("OTLP Endpoint Connectivity", "FAIL", 
                        f"Unexpected error: {str(e)}")
            return False
            
    except Exception as e:
        print_status("OTLP Endpoint Connectivity", "FAIL", 
                    f"Invalid endpoint format: {str(e)}")
        return False


def check_dependencies() -> bool:
    """Check if required dependencies are available."""
    print_status("Dependencies", "INFO", "Checking Python packages...")
    
    required_deps = [
        ("opentelemetry-api", "OpenTelemetry API"),
        ("opentelemetry-sdk", "OpenTelemetry SDK"),
        ("opentelemetry-exporter-otlp", "OTLP Exporter")
    ]
    
    optional_deps = [
        ("deepeval", "DeepEval evaluation framework"),
        ("langgraph", "LangGraph framework"),
        ("crewai", "CrewAI framework"),
        ("openai", "OpenAI client"),
        ("anthropic", "Anthropic client"),
        ("httpx", "HTTP client")
    ]
    
    all_good = True
    
    # Check required dependencies
    for package, description in required_deps:
        try:
            importlib.import_module(package.replace("-", "_"))
            print_status(f"  {package}", "OK", description)
        except ImportError:
            print_status(f"  {package}", "FAIL", f"Missing {description}")
            all_good = False
    
    # Check optional dependencies
    for package, description in optional_deps:
        try:
            importlib.import_module(package)
            print_status(f"  {package}", "OK", description)
        except ImportError:
            print_status(f"  {package}", "WARN", f"Optional {description} not available")
    
    return all_good


def check_instrumentation_status() -> bool:
    """Check current instrumentation patch status."""
    print_status("Instrumentation Status", "INFO", "Checking patch applications...")
    
    try:
        status = get_patch_status()
        all_patches_ok = True
        
        for component, is_patched in status.items():
            if is_patched:
                print_status(f"  {component}", "OK", "Patched and active")
            else:
                print_status(f"  {component}", "WARN", "Not patched or failed to patch")
                # Don't mark as failure since some patches are optional
        
        return all_patches_ok
        
    except Exception as e:
        print_status("Instrumentation Status", "FAIL", f"Error checking patches: {str(e)}")
        return False


def import_class_from_string(module_class_path: str) -> Tuple[Any, str]:
    """
    Import a class from a module:Class string.
    
    Args:
        module_class_path: String in format "module.path:ClassName"
        
    Returns:
        Tuple of (class_object, class_name)
    """
    if ":" not in module_class_path:
        raise ValueError("Format must be 'module.path:ClassName'")
    
    module_path, class_name = module_class_path.split(":", 1)
    
    try:
        module = importlib.import_module(module_path)
        class_obj = getattr(module, class_name)
        return class_obj, class_name
    except ImportError as e:
        raise ImportError(f"Could not import module '{module_path}': {e}")
    except AttributeError as e:
        raise AttributeError(f"Class '{class_name}' not found in module '{module_path}': {e}")


@click.group()
@click.version_option(version="0.1.0", prog_name="trinetri")
def cli():
    """Trinetri - Auto-instrumentation for Multi-Agent LLM Systems."""
    pass


@cli.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed diagnostic information")
def doctor(verbose: bool):
    """
    Run comprehensive health checks for Trinetri configuration.
    
    Checks environment variables, OTLP endpoint reachability,
    dependencies, and instrumentation status.
    """
    click.echo(f"\n{Colors.BOLD}{Colors.BLUE}🔍 Trinetri Doctor - Health Check{Colors.END}\n")
    
    checks = [
        ("Environment Variables", check_environment_variables),
        ("Dependencies", check_dependencies),
        ("OTLP Connectivity", check_otlp_endpoint),
        ("Instrumentation Status", check_instrumentation_status)
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print_status(check_name, "FAIL", f"Unexpected error: {str(e)}")
            results.append((check_name, False))
    
    # Summary
    click.echo(f"\n{Colors.BOLD}📋 Health Check Summary{Colors.END}")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    if passed == total:
        click.echo(f"{Colors.GREEN}✅ All checks passed ({passed}/{total}){Colors.END}")
        click.echo(f"{Colors.GREEN}🚀 Trinetri is ready for use!{Colors.END}")
        sys.exit(0)
    else:
        failed = total - passed
        click.echo(f"{Colors.YELLOW}⚠️  {passed}/{total} checks passed, {failed} issues found{Colors.END}")
        click.echo(f"{Colors.YELLOW}🔧 Please address the issues above before using Trinetri{Colors.END}")
        
        if verbose:
            click.echo(f"\n{Colors.BOLD}🛠️  Troubleshooting Tips{Colors.END}")
            click.echo("• Set OTEL_EXPORTER_OTLP_ENDPOINT to your collector URL")
            click.echo("• Set OTEL_SERVICE_NAME to identify your application")
            click.echo("• Install missing dependencies: pip install opentelemetry-api opentelemetry-sdk")
            click.echo("• Verify your OTLP collector is running and accessible")
        
        sys.exit(1)


@cli.command()
@click.argument("module_class", metavar="MODULE:CLASS")
@click.option("--role", "-r", required=True, help="Agent role name for identification")
@click.option("--dry-run", is_flag=True, help="Show what would be instrumented without applying")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed instrumentation information")
def instrument(module_class: str, role: str, dry_run: bool, verbose: bool):
    """
    Dynamically instrument a custom agent class.
    
    MODULE:CLASS should be in the format 'module.path:ClassName'
    
    Examples:
      trinetri instrument myapp.agents:CustomAgent --role researcher
      trinetri instrument langchain.agents:Agent --role planner --dry-run
    """
    click.echo(f"\n{Colors.BOLD}{Colors.BLUE}🔧 Trinetri Dynamic Instrumentation{Colors.END}\n")
    
    try:
        # Import the target class
        print_status("Class Import", "INFO", f"Loading {module_class}...")
        agent_class, class_name = import_class_from_string(module_class)
        print_status("Class Import", "OK", f"Successfully loaded {class_name}")
        
        if verbose:
            click.echo(f"   {Colors.CYAN}Class: {agent_class}{Colors.END}")
            click.echo(f"   {Colors.CYAN}Module: {agent_class.__module__}{Colors.END}")
            click.echo(f"   {Colors.CYAN}File: {getattr(agent_class, '__file__', 'Unknown')}{Colors.END}")
        
        # Validate the class
        if not hasattr(agent_class, '__init__'):
            raise ValueError(f"Class {class_name} does not have an __init__ method")
        
        print_status("Class Validation", "OK", f"{class_name} is instrumentable")
        
        # Show what will be instrumented
        print_status("Instrumentation Plan", "INFO", f"Will instrument {class_name} with role '{role}'")
        
        if dry_run:
            click.echo(f"\n{Colors.YELLOW}🏃 Dry run mode - no actual instrumentation applied{Colors.END}")
            click.echo(f"Would execute: instrument_agent({class_name}, role='{role}')")
            return
        
        # Apply instrumentation
        print_status("Instrumentation", "INFO", "Applying agent instrumentation...")
        start_time = time.time()
        
        instrument_agent(agent_class, role=role)
        
        duration = int((time.time() - start_time) * 1000)
        print_status("Instrumentation", "OK", f"Applied in {duration}ms")
        
        # Verify instrumentation
        if hasattr(agent_class, '_trinetri_instrumented'):
            print_status("Verification", "OK", "Instrumentation markers found")
        else:
            print_status("Verification", "WARN", "No instrumentation markers detected")
        
        click.echo(f"\n{Colors.GREEN}✅ Successfully instrumented {class_name} with role '{role}'{Colors.END}")
        click.echo(f"{Colors.GREEN}🎯 Agent instances will now be automatically traced{Colors.END}")
        
        if verbose:
            click.echo(f"\n{Colors.BOLD}📊 Next Steps{Colors.END}")
            click.echo("• Create instances of your agent class")
            click.echo("• Execute agent methods/workflows")
            click.echo("• View traces in your observability platform")
            click.echo("• Run 'trinetri doctor' to verify trace collection")
        
    except ValueError as e:
        print_status("Input Validation", "FAIL", str(e))
        click.echo(f"\n{Colors.RED}❌ Invalid input format{Colors.END}")
        click.echo(f"{Colors.YELLOW}💡 Use format: module.path:ClassName{Colors.END}")
        sys.exit(1)
        
    except (ImportError, AttributeError) as e:
        print_status("Class Import", "FAIL", str(e))
        click.echo(f"\n{Colors.RED}❌ Could not import target class{Colors.END}")
        click.echo(f"{Colors.YELLOW}💡 Verify the module path and class name are correct{Colors.END}")
        sys.exit(1)
        
    except Exception as e:
        print_status("Instrumentation", "FAIL", f"Unexpected error: {str(e)}")
        click.echo(f"\n{Colors.RED}❌ Instrumentation failed{Colors.END}")
        if verbose:
            import traceback
            click.echo(f"{Colors.RED}{traceback.format_exc()}{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    cli() 