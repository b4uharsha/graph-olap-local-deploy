"""E2E tests that execute Jupyter notebooks.

Auto-discovers notebooks from notebooks.yaml. Adding a test = adding a YAML entry.

Test Coverage:
- SDK notebook execution in actual Jupyter kernel
- All SDK features work end-to-end through notebook interface
- Validates user workflow as documented

Parallel Execution:
Tests are organized into xdist groups defined in notebooks.yaml.
Run modes:
  Sequential:  pytest tests/test_notebook_execution.py
  Parallel:    pytest tests/test_notebook_execution.py -n auto --dist=loadgroup

Cleanup Strategy (Google Best Practice):
- The test runner (not notebooks) guarantees cleanup via try/finally blocks
- Cleanup happens even if notebooks fail mid-execution
- Each test cleans up its own resources immediately after execution
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Generator
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from conftest import get_control_plane_url

if TYPE_CHECKING:
    pass


# =============================================================================
# Configuration Loading
# =============================================================================


def _load_notebook_config() -> dict[str, Any]:
    """Load notebook configuration from YAML."""
    config_path = Path(__file__).parent.parent / "notebooks.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def _get_notebook_path(name: str) -> Path:
    """Get path to a notebook file."""
    tests_dir = Path(__file__).parent
    notebooks_dir = tests_dir.parent / "notebooks"

    # Support both with and without .ipynb extension
    notebook_name = name if name.endswith(".ipynb") else f"{name}.ipynb"

    # E2E test notebooks are in platform-tests/
    platform_tests_path = notebooks_dir / "platform-tests" / notebook_name
    if platform_tests_path.exists():
        return platform_tests_path

    # Legacy: check root notebooks dir (for backwards compatibility)
    notebook_path = notebooks_dir / notebook_name
    if notebook_path.exists():
        return notebook_path

    # Container fallback (also updated for new structure)
    for container_dir in [
        Path("/app/notebooks/platform-tests"),
        Path("/app/notebooks"),
    ]:
        container_path = container_dir / notebook_name
        if container_path.exists():
            return container_path

    raise FileNotFoundError(f"Notebook not found: {notebook_name}")


# =============================================================================
# Resource Cleanup
# =============================================================================


def _cleanup_test_resources(
    test_prefix: str | None,
    max_age_minutes: int = 30,
    control_plane_url: str | None = None,
) -> None:
    """Clean up test resources created by a notebook.

    This function is called after notebook execution (success or failure) to ensure
    all resources are cleaned up. Uses the existing cleanup framework for robust,
    dependency-aware cleanup.

    Args:
        test_prefix: Test prefix to filter resources (e.g., "CrudTest")
        max_age_minutes: Only clean up resources created within this time window
        control_plane_url: Control plane URL (uses env var if not provided)
    """
    from datetime import datetime, timedelta

    if not test_prefix:
        return

    try:
        from graph_olap import GraphOLAPClient
        from graph_olap.exceptions import NotFoundError

        if not control_plane_url:
            control_plane_url = get_control_plane_url()

        admin_api_key = os.environ.get("GRAPH_OLAP_API_KEY_ADMIN_CAROL")
        if not admin_api_key:
            print("Warning: GRAPH_OLAP_API_KEY_ADMIN_CAROL not set - cleanup may fail")
            return

        client = GraphOLAPClient(api_url=control_plane_url, api_key=admin_api_key)

        try:
            cutoff = datetime.now(UTC) - timedelta(minutes=max_age_minutes)
            cleaned = {"instances": 0, "snapshots": 0, "mappings": 0}

            print(f"\nCleaning up {test_prefix} resources (created within {max_age_minutes} min)...")

            # 1. Delete instances (reverse dependency order)
            instances = client.instances.list()
            for instance in instances:
                if test_prefix in instance.name and instance.created_at >= cutoff:
                    try:
                        client.instances.terminate(instance.id)
                        cleaned["instances"] += 1
                        print(f"  Terminated instance {instance.id} ({instance.name})")
                    except NotFoundError:
                        pass
                    except Exception as e:
                        print(f"  Warning: Failed to terminate instance {instance.id}: {e}")

            # 2. Delete snapshots
            snapshots = client.snapshots.list()
            for snapshot in snapshots:
                if test_prefix in snapshot.name and snapshot.created_at >= cutoff:
                    try:
                        client.snapshots.delete(snapshot.id)
                        cleaned["snapshots"] += 1
                        print(f"  Deleted snapshot {snapshot.id} ({snapshot.name})")
                    except NotFoundError:
                        pass
                    except Exception as e:
                        print(f"  Warning: Failed to delete snapshot {snapshot.id}: {e}")

            # 3. Delete mappings
            mappings = client.mappings.list()
            for mapping in mappings:
                if test_prefix in mapping.name and mapping.created_at >= cutoff:
                    try:
                        client.mappings.delete(mapping.id)
                        cleaned["mappings"] += 1
                        print(f"  Deleted mapping {mapping.id} ({mapping.name})")
                    except NotFoundError:
                        pass
                    except Exception as e:
                        print(f"  Warning: Failed to delete mapping {mapping.id}: {e}")

            total = sum(cleaned.values())
            if total > 0:
                print(f"Cleanup complete: {cleaned['instances']} instances, "
                      f"{cleaned['snapshots']} snapshots, {cleaned['mappings']} mappings")
            else:
                print("No resources to clean up")

        finally:
            client.close()

    except Exception as e:
        print(f"Warning: Test resource cleanup failed: {e}")
        print("(Orphaned resources will be cleaned up by lifecycle job)")


# =============================================================================
# Notebook Execution
# =============================================================================


def _execute_notebook(
    notebook_name: str,
    output_dir: Path,
    parameters: dict[str, Any],
    test_name: str,
    test_prefix: str | None = None,
    execution_timeout: int = 180,
) -> None:
    """Execute a notebook with papermill and FAIL HARD on any error.

    Google TAP Best Practice: Tests must fail fast and loud.
    - Any cell exception = test failure
    - Any unexpected error = test failure
    - No silent failures or ignored errors

    Args:
        notebook_name: Name of the notebook file
        output_dir: Directory for output notebooks
        parameters: Parameters to inject into notebook
        test_name: Human-readable test name for logging
        test_prefix: Resource prefix for cleanup (e.g., "CrudTest")
        execution_timeout: Timeout per cell in seconds (default 180)

    Raises:
        pytest.fail: On ANY error - notebook cell failure, kernel error, timeout, etc.
    """
    import papermill as pm

    notebook_path = _get_notebook_path(notebook_name)
    output_path = output_dir / notebook_name.replace(".ipynb", "_output.ipynb")

    print(f"\nExecuting {test_name}: {notebook_path} (timeout={execution_timeout}s/cell)")

    api_url = parameters.get("GRAPH_OLAP_API_URL")
    test_failed = False
    failure_message = ""

    try:
        pm.execute_notebook(
            str(notebook_path),
            str(output_path),
            parameters=parameters,
            kernel_name="python3",
            progress_bar=False,
            execution_timeout=execution_timeout,
        )
        print(f"\n{test_name} passed!")

    except pm.PapermillExecutionError as e:
        test_failed = True
        print(f"\n{'='*60}")
        print(f"{test_name.upper()} FAILED - CELL EXECUTION ERROR")
        print(f"{'='*60}")
        print(f"Cell index: {e.cell_index}")
        print(f"Cell source:\n{e.source}")
        print(f"\nError:\n{e.ename}: {e.evalue}")
        if e.traceback:
            print(f"\nTraceback:\n{''.join(e.traceback)}")
        print(f"\nOutput notebook saved to: {output_path}")
        failure_message = f"{test_name} failed at cell {e.cell_index}: {e.ename}: {e.evalue}"

    except Exception as e:
        test_failed = True
        print(f"\n{'='*60}")
        print(f"{test_name.upper()} FAILED - UNEXPECTED ERROR")
        print(f"{'='*60}")
        print(f"Exception type: {type(e).__name__}")
        print(f"Exception message: {e}")
        import traceback
        print(f"\nFull traceback:\n{traceback.format_exc()}")
        if output_path.exists():
            print(f"\nPartial output notebook saved to: {output_path}")
        failure_message = f"{test_name} failed with unexpected error: {type(e).__name__}: {e}"

    finally:
        # CRITICAL: Cleanup runs even if notebook failed
        _cleanup_test_resources(
            test_prefix=test_prefix,
            max_age_minutes=30,
            control_plane_url=api_url,
        )

        if test_failed:
            pytest.fail(failure_message)


# =============================================================================
# Parameter Resolution
# =============================================================================


def _resolve_parameters(
    params: dict[str, Any],
    fixtures: dict[str, Any],
) -> dict[str, Any]:
    """Resolve {{fixture.field}} placeholders in parameters.

    Supports:
    - {{fixture_name}} - direct fixture value
    - {{fixture_name.field}} - nested field access
    """
    resolved = {}
    for key, value in params.items():
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            ref = value[2:-2]  # Remove {{ and }}
            if "." in ref:
                fixture_name, field = ref.split(".", 1)
                fixture_value = fixtures.get(fixture_name)
                if isinstance(fixture_value, dict):
                    resolved[key] = fixture_value.get(field)
                else:
                    resolved[key] = None
            else:
                resolved[key] = fixtures.get(ref)
        else:
            resolved[key] = value
    return resolved


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def papermill_available() -> bool:
    """Check if papermill is available."""
    try:
        import papermill  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.fixture(scope="module")
def notebook_output_dir() -> Generator[Path, None, None]:
    """Create temporary directory for notebook outputs."""
    output_dir = Path(tempfile.mkdtemp(prefix="notebook_test_"))
    yield output_dir
    shutil.rmtree(output_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def control_plane_url() -> str:
    """Get Control Plane URL for notebook tests."""
    return get_control_plane_url()


# seeded_ids fixture is defined in conftest.py - uses shared_snapshot and
# shared_readonly_instance to provide REAL IDs instead of hardcoded placeholders.


# =============================================================================
# Test Generation
# =============================================================================


def pytest_generate_tests(metafunc):
    """Dynamically generate test cases from notebooks.yaml."""
    if "notebook_config" not in metafunc.fixturenames:
        return

    config = _load_notebook_config()
    defaults = config.get("defaults", {})
    notebooks = config.get("notebooks", {})

    test_cases = []
    ids = []

    for name, nb_config in notebooks.items():
        nb_config = nb_config or {}

        # Merge default parameters with notebook-specific parameters
        default_params = defaults.get("parameters", {}).copy()
        nb_params = nb_config.get("parameters", {})
        merged_params = {**default_params, **nb_params}

        test_cases.append({
            "name": name,
            "xdist_group": nb_config.get("xdist_group", defaults.get("xdist_group", "default")),
            "timeout": nb_config.get("timeout", defaults.get("timeout", 300)),
            "prefix": nb_config.get("prefix"),
            "fixtures": nb_config.get("fixtures", []),
            "parameters": merged_params,
            "skip_if_missing": nb_config.get("skip_if_missing"),
        })
        ids.append(f"test_{name}")

    metafunc.parametrize("notebook_config", test_cases, ids=ids)


# =============================================================================
# Single Parametrized Test
# =============================================================================


@pytest.mark.e2e
def test_notebook(
    notebook_config: dict,
    papermill_available: bool,
    notebook_output_dir: Path,
    control_plane_url: str,
    request: pytest.FixtureRequest,
) -> None:
    """Execute a notebook test.

    This single function replaces all hardcoded test functions.
    Configuration comes from notebooks.yaml.
    """
    if not papermill_available:
        pytest.skip("papermill not installed")

    # Check skip condition
    skip_env = notebook_config.get("skip_if_missing")
    if skip_env and not os.environ.get(skip_env):
        pytest.skip(f"{skip_env} not set")

    # Dynamically request fixtures based on notebook config
    required_fixtures = notebook_config.get("fixtures", [])
    fixture_values = {}
    for fixture_name in required_fixtures:
        try:
            fixture_values[fixture_name] = request.getfixturevalue(fixture_name)
        except pytest.FixtureLookupError:
            pytest.fail(f"Unknown fixture: {fixture_name}")

    # Build fixture dict for parameter resolution
    fixtures = {
        "control_plane_url": control_plane_url,
        "seeded_ids": fixture_values.get("seeded_ids", {}),
        "shared_snapshot_id": fixture_values.get("shared_snapshot_id"),
        "shared_readonly_instance": fixture_values.get("shared_readonly_instance"),
        "instance_pool": fixture_values.get("instance_pool", {}),
    }

    # Resolve parameters
    parameters = _resolve_parameters(notebook_config["parameters"], fixtures)

    # Calculate per-cell timeout (half of total timeout, minimum 60s)
    total_timeout = notebook_config.get("timeout", 300)
    cell_timeout = max(60, total_timeout // 2)

    # Execute
    _execute_notebook(
        f"{notebook_config['name']}.ipynb",
        notebook_output_dir,
        parameters=parameters,
        test_name=notebook_config["name"],
        test_prefix=notebook_config.get("prefix"),
        execution_timeout=cell_timeout,
    )
