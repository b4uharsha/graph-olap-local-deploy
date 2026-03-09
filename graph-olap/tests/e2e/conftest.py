"""E2E test configuration and fixtures.

This is the SINGLE conftest.py for all E2E tests. Infrastructure management
is handled by the local-dev/ module.

FAIL-FAST BEHAVIOR:
- By default, tests halt on first failure (--exitfirst / -x)
- This ensures failures are noticed immediately, not buried in output
- To run all tests despite failures: PYTEST_ARGS="--no-exitfirst" make test

Prerequisites:
    Infrastructure must be running before tests:
        cd ../local-dev && make up

Usage:
    pytest tests/ -v              # Run all tests
    pytest tests/ -v -k "smoke"   # Run smoke tests only

Authentication:
    Tests use API key authentication via TestPersona environment variables:
    - GRAPH_OLAP_API_KEY_ANALYST_ALICE: Default test user (analyst)
    - GRAPH_OLAP_API_KEY_ANALYST_BOB: Second analyst for multi-user tests
    - GRAPH_OLAP_API_KEY_ADMIN_CAROL: Admin user
    - GRAPH_OLAP_API_KEY_OPS_DAVE: Ops user

For notebooks, use notebook.test() with TestPersona enum instead of these fixtures.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest

from utils.cleanup import ResourceTracker

if TYPE_CHECKING:
    from graph_olap import GraphOLAPClient

from graph_olap.testing import TestPersona
from graph_olap_schemas import WrapperType

logger = logging.getLogger(__name__)


# =============================================================================
# Mode Detection
# =============================================================================

IN_CLUSTER = os.environ.get("IN_CLUSTER", "").lower() in ("true", "1", "yes")


# =============================================================================
# pytest Configuration
# =============================================================================

def pytest_addoption(parser: pytest.Parser) -> None:
    """Add command-line options for E2E tests."""
    parser.addoption(
        "--no-exitfirst",
        action="store_true",
        default=False,
        help="Continue running tests after first failure (overrides default fail-fast)",
    )
    parser.addoption(
        "--keep-cluster",
        action="store_true",
        default=True,
        help="Deprecated: cluster is always kept (managed by local-dev)",
    )
    parser.addoption(
        "--reuse-cluster",
        action="store_true",
        default=True,
        help="Deprecated: cluster is always reused (managed by local-dev)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest for E2E tests.

    Google TAP Best Practice: Fail fast, fail loud.
    - Default behavior: Stop on first failure (--exitfirst)
    - Override with: --no-exitfirst or -p no:exitfirst
    """
    # Only enable exitfirst if not explicitly disabled
    if not config.getoption("--no-exitfirst", default=False):
        # Set exitfirst unless already set via command line
        if not config.getoption("exitfirst", default=False):
            config.option.exitfirst = True

    # Print configuration at test start
    url = os.environ.get("GRAPH_OLAP_API_URL", "NOT SET")
    api_key_set = bool(os.environ.get("GRAPH_OLAP_API_KEY_ANALYST_ALICE"))
    print(f"\n{'='*60}")
    print("E2E Test Configuration")
    print(f"{'='*60}")
    print(f"Mode: {'IN-CLUSTER' if IN_CLUSTER else 'LOCAL'}")
    print(f"Control Plane: {url}")
    print(f"Auth: API Key ({'set' if api_key_set else 'NOT SET'})")
    print(f"{'='*60}\n")


def pytest_collection_modifyitems(session, config, items):
    """Dynamically apply xdist_group and timeout markers from notebooks.yaml.

    This allows notebooks.yaml to be the single source of truth for test configuration.
    Markers are applied at collection time, so pytest-xdist respects them.
    """
    from pathlib import Path

    import yaml

    # Load notebook config
    config_path = Path(__file__).parent / "notebooks.yaml"
    if not config_path.exists():
        return

    with open(config_path) as f:
        nb_config = yaml.safe_load(f)

    defaults = nb_config.get("defaults", {})
    notebooks = nb_config.get("notebooks", {})

    for item in items:
        # Only process notebook tests
        if "test_notebook" not in item.name:
            continue

        # Extract notebook name from parametrized test ID
        # e.g., "test_notebook[test_04_cypher_basics]" -> "04_cypher_basics"
        if "[" not in item.name:
            continue

        param_id = item.name.split("[")[1].rstrip("]")
        if not param_id.startswith("test_"):
            continue

        notebook_name = param_id[5:]  # Remove "test_" prefix

        if notebook_name not in notebooks:
            continue

        cfg = notebooks[notebook_name] or {}

        # Apply xdist_group marker
        xdist_group = cfg.get("xdist_group", defaults.get("xdist_group", "default"))
        item.add_marker(pytest.mark.xdist_group(xdist_group))

        # Apply timeout marker
        timeout = cfg.get("timeout", defaults.get("timeout", 300))
        item.add_marker(pytest.mark.timeout(timeout))

        # Apply e2e marker (for filtering)
        item.add_marker(pytest.mark.e2e)


# =============================================================================
# Helper Functions
# =============================================================================

def get_api_key_for_persona(persona: TestPersona) -> str:
    """Get API key for a specific test persona.

    Args:
        persona: TestPersona enum value

    Returns:
        API key for the persona

    Raises:
        ValueError: If the environment variable is not set
    """
    config = persona.value
    api_key = os.environ.get(config.env_var)
    if not api_key:
        raise ValueError(
            f"Missing API key for persona '{config.name}'. "
            f"Set {config.env_var} environment variable.\n"
            f"Description: {config.description}"
        )
    return api_key


def get_default_api_key() -> str:
    """Get default API key (analyst Alice) for tests.

    Returns:
        API key for analyst Alice

    Raises:
        ValueError: If GRAPH_OLAP_API_KEY_ANALYST_ALICE is not set
    """
    return get_api_key_for_persona(TestPersona.ANALYST_ALICE)


def get_control_plane_url() -> str:
    """Get Control Plane URL from environment.

    Uses SDK-standard environment variable names for consistency.
    Configuration is managed externally (Makefile, CI/CD, etc.)
    This function just retrieves the configured value and fails fast if missing.

    Returns:
        Control plane URL

    Raises:
        RuntimeError: If GRAPH_OLAP_API_URL environment variable is not set

    Environment Variables:
        GRAPH_OLAP_API_URL: Full URL to control plane API (SDK standard)
            Local:      http://localhost:30081 (via OrbStack + nginx ingress)
            In-cluster: http://control-plane.graph-olap-local.svc.cluster.local:8080
    """
    url = os.environ.get("GRAPH_OLAP_API_URL")
    if not url:
        raise RuntimeError(
            "GRAPH_OLAP_API_URL environment variable not set. "
            "Configure your test environment:\n"
            "  Local: Run tests via 'make test' from tools/local-dev/\n"
            "  CI/CD: Ensure test environment configuration is loaded"
        )
    return url


# =============================================================================
# API Key Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def control_plane_url() -> str:
    """Get Control Plane URL for tests.

    Session-scoped because URL is constant across all tests.
    """
    return get_control_plane_url()


@pytest.fixture(scope="session")
def analyst_alice_api_key() -> str:
    """Get API key for analyst Alice.

    Session-scoped because key is constant across all tests.
    """
    return get_api_key_for_persona(TestPersona.ANALYST_ALICE)


@pytest.fixture(scope="session")
def analyst_bob_api_key() -> str:
    """Get API key for analyst Bob.

    Session-scoped because key is constant across all tests.
    """
    return get_api_key_for_persona(TestPersona.ANALYST_BOB)


@pytest.fixture(scope="session")
def admin_carol_api_key() -> str:
    """Get API key for admin Carol.

    Session-scoped because key is constant across all tests.
    """
    return get_api_key_for_persona(TestPersona.ADMIN_CAROL)


@pytest.fixture(scope="session")
def ops_dave_api_key() -> str:
    """Get API key for ops Dave.

    Session-scoped because key is constant across all tests.
    """
    return get_api_key_for_persona(TestPersona.OPS_DAVE)


# =============================================================================
# Client Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def graph_olap_client(control_plane_url: str, analyst_alice_api_key: str) -> Generator[GraphOLAPClient, None, None]:
    """Create GraphOLAP client for tests (as analyst Alice).

    Automatically closes client after tests complete.
    Uses API key authentication.
    """
    from graph_olap import GraphOLAPClient

    client = GraphOLAPClient(
        api_url=control_plane_url,
        api_key=analyst_alice_api_key,
    )

    logger.info(f"Created GraphOLAP client (analyst Alice) at {control_plane_url}")

    try:
        yield client
    finally:
        client.close()
        logger.info("Closed GraphOLAP client")


@pytest.fixture(scope="module")
def sdk_client(graph_olap_client: GraphOLAPClient) -> GraphOLAPClient:
    """Alias for graph_olap_client for backward compatibility."""
    return graph_olap_client


@pytest.fixture(scope="module")
def admin_client(control_plane_url: str, admin_carol_api_key: str) -> Generator[GraphOLAPClient, None, None]:
    """Create GraphOLAP client for admin Carol.

    Role is embedded in the JWT token.
    """
    from graph_olap import GraphOLAPClient

    client = GraphOLAPClient(
        api_url=control_plane_url,
        api_key=admin_carol_api_key,
    )
    logger.info(f"Created admin client (Carol) at {control_plane_url}")

    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="module")
def ops_client(control_plane_url: str, ops_dave_api_key: str) -> Generator[GraphOLAPClient, None, None]:
    """Create GraphOLAP client for ops Dave.

    Role is embedded in the JWT token.
    """
    from graph_olap import GraphOLAPClient

    client = GraphOLAPClient(
        api_url=control_plane_url,
        api_key=ops_dave_api_key,
    )
    logger.info(f"Created ops client (Dave) at {control_plane_url}")

    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="module")
def analyst_client(control_plane_url: str, analyst_alice_api_key: str) -> Generator[GraphOLAPClient, None, None]:
    """Create GraphOLAP client for analyst Alice."""
    from graph_olap import GraphOLAPClient

    client = GraphOLAPClient(
        api_url=control_plane_url,
        api_key=analyst_alice_api_key,
    )
    logger.info(f"Created analyst client (Alice) at {control_plane_url}")

    try:
        yield client
    finally:
        client.close()


# =============================================================================
# Resource Management Fixtures
# =============================================================================

@pytest.fixture
def resource_tracker(graph_olap_client: GraphOLAPClient) -> Generator[ResourceTracker, None, None]:
    """Provide resource tracker with automatic cleanup.

    This fixture ensures all resources created during a test are cleaned up,
    even if the test fails.

    Usage:
        def test_something(resource_tracker):
            mapping = resource_tracker.create_mapping(name="Test")
            # ... test code ...
            # Cleanup happens automatically
    """
    tracker = ResourceTracker(
        client=graph_olap_client,
        username="analyst_alice",  # For logging only - identity from API key
        fail_on_cleanup_error=True,
    )

    logger.info("Starting resource tracker for test")

    try:
        yield tracker
    finally:
        # Always cleanup, even if test fails
        logger.info("Cleaning up test resources")
        tracker.cleanup_all()

        # Check for cleanup failures
        failed = [r for r in tracker.cleanup_results if not r.success and not r.skipped]
        if failed:
            error_details = "\n".join(
                f"  - {r.resource.resource_type.value} {r.resource.resource_id}: {r.error}"
                for r in failed
            )
            pytest.fail(f"Resource cleanup failed:\n{error_details}")


@pytest.fixture(scope="session")
def seeded_ids(shared_snapshot: dict, shared_readonly_instance: str) -> dict[str, int]:
    """Get IDs from shared test resources.

    OPTIMIZED: Now uses real IDs from shared_snapshot and shared_readonly_instance
    instead of hardcoded placeholders. This allows notebooks to reuse existing
    resources instead of creating their own, saving ~5-10 minutes per test run.

    Returns:
        dict with mapping_id, snapshot_id, instance_id from shared fixtures
    """
    return {
        "mapping_id": shared_snapshot["mapping_id"],
        "snapshot_id": shared_snapshot["snapshot_id"],
        "instance_id": int(shared_readonly_instance),
    }


# =============================================================================
# Session-Scoped Shared Resources
# =============================================================================

# NOTE: Cleanup of orphaned test resources is handled by the Makefile.
# The pre-flight cleanup script (tools/local-dev/scripts/cleanup-test-resources.py)
# runs ONCE before pytest starts, avoiding race conditions with pytest-xdist.
#
# Why not a pytest fixture?
# - pytest-xdist runs session fixtures once PER WORKER, not once globally
# - This caused race conditions where Worker 2 would delete resources from Worker 1
# - Makefile cleanup runs ONCE, BEFORE any tests start - no race conditions
#
# Manual cleanup:
#   cd tools/local-dev && python3 ./scripts/cleanup-test-resources.py


@pytest.fixture(scope="session", autouse=True)
def configure_parallel_test_limits(control_plane_url: str, ops_dave_api_key: str) -> Generator[None, None, None]:
    """Configure instance limits for parallel test execution.

    Parallel tests require higher instance limits:
    - Session fixtures: 4 instances (3 pool + 1 shared_readonly)
    - Concurrent tests: 6 instances (crud, algorithm, workflow, authorization, validation, etc.)
    - Total needed: 10 instances (vs default limit of 5)

    This fixture:
    1. Gets current concurrency limits
    2. Increases per_analyst limit to 15 (cluster_total to 50)
    3. Yields to tests
    4. Restores original limits on teardown

    AUTOUSE: This fixture runs automatically for all test sessions.
    """
    from graph_olap import GraphOLAPClient

    logger.info("Configuring instance limits for parallel test execution")

    # Create ops client (Dave) to access config API
    ops_client = GraphOLAPClient(
        api_url=control_plane_url,
        api_key=ops_dave_api_key,
    )

    try:
        # Get current limits
        original_limits = ops_client.ops.get_concurrency_config()
        logger.info(
            f"Original limits: per_analyst={original_limits.per_analyst}, "
            f"cluster_total={original_limits.cluster_total}"
        )

        # Increase limits for parallel tests
        # - Session fixtures need 4 instances (pool + shared_readonly)
        # - Concurrent tests need up to 6 instances
        # - Total: 10 instances, so set limit to 15 for safety margin
        new_limits = ops_client.ops.update_concurrency_config(
            per_analyst=15,
            cluster_total=50
        )
        logger.info(
            f"Increased limits for parallel tests: per_analyst={new_limits.per_analyst}, "
            f"cluster_total={new_limits.cluster_total}"
        )

        yield

    finally:
        # Restore original limits
        try:
            restored = ops_client.ops.update_concurrency_config(
                per_analyst=original_limits.per_analyst,
                cluster_total=original_limits.cluster_total
            )
            logger.info(
                f"Restored original limits: per_analyst={restored.per_analyst}, "
                f"cluster_total={restored.cluster_total}"
            )
        except Exception as e:
            logger.warning(f"Failed to restore original limits: {e}")
        finally:
            ops_client.close()


@pytest.fixture(scope="session")
def shared_snapshot(control_plane_url: str, analyst_alice_api_key: str) -> Generator[dict, None, None]:
    """Create a shared mapping and instance for ALL E2E tests.

    SNAPSHOT FUNCTIONALITY DISABLED:
    Explicit snapshot creation has been disabled. We now create instances directly
    from mappings using create_and_wait(), which handles snapshot creation
    automatically in the background.

    This fixture:
    1. Creates ONE mapping with Person + KNOWS schema
    2. Creates ONE instance via create_and_wait() (snapshot created automatically)
    3. Extracts the auto-created snapshot ID for tests that need it
    4. All other fixtures and tests reuse this snapshot/instance

    Google TAP Best Practice: "Reuse immutable test data across tests"
    - Snapshots are immutable once exported
    - Safe to share across ALL instances
    - Saves ~10 minutes of redundant exports

    Yields:
        dict: {
            "snapshot_id": int,
            "mapping_id": int,
        }
    """
    from graph_olap import GraphOLAPClient
    from graph_olap.models.mapping import EdgeDefinition, NodeDefinition, PropertyDefinition

    logger.info("=" * 60)
    logger.info("Creating shared mapping for ALL E2E tests")
    logger.info("SNAPSHOT FUNCTIONALITY DISABLED - using create_and_wait()")
    logger.info("=" * 60)

    client = GraphOLAPClient(api_url=control_plane_url, api_key=analyst_alice_api_key)

    # Define standard Person/KNOWS schema used by all tests
    person_node = NodeDefinition(
        label="Person",
        sql="SELECT DISTINCT id, name, age FROM bigquery.graph_olap_e2e.persons",
        primary_key={"name": "id", "type": "STRING"},
        properties=[
            PropertyDefinition(name="name", type="STRING"),
            PropertyDefinition(name="age", type="INT64"),
        ]
    )

    knows_edge = EdgeDefinition(
        type="KNOWS",
        from_node="Person",
        to_node="Person",
        sql="SELECT DISTINCT from_id, to_id, since FROM bigquery.graph_olap_e2e.friendships",
        from_key="from_id",
        to_key="to_id",
        properties=[
            PropertyDefinition(name="since", type="INT64"),
        ]
    )

    mapping = None
    snapshot_id = None
    temp_instance = None

    try:
        # Create ONE mapping
        mapping = client.mappings.create(
            name="SharedE2EMapping",
            description="Single shared mapping for all E2E tests - eliminates redundant exports",
            node_definitions=[person_node],
            edge_definitions=[knows_edge],
        )
        logger.info(f"Created shared mapping: {mapping.name} (id={mapping.id})")

        # SNAPSHOT FUNCTIONALITY DISABLED
        # Create a temporary instance via create_and_wait() to trigger snapshot creation
        # The snapshot is created automatically in the background
        logger.info("Creating temporary instance to trigger snapshot creation...")
        temp_instance = client.instances.create_and_wait(
            mapping_id=mapping.id,
            name="SharedE2ESnapshotTrigger",
            wrapper_type=WrapperType.RYUGRAPH,
            timeout=300,
            poll_interval=5,
        )
        snapshot_id = temp_instance.snapshot_id
        logger.info(f"Auto-created snapshot: id={snapshot_id}")
        logger.info("This ONE snapshot will be used by ALL tests - no more redundant exports!")

        # Terminate the temporary instance (we only needed it to create the snapshot)
        # Other fixtures will create their own instances from this snapshot
        client.instances.terminate(temp_instance.id)
        logger.info(f"Terminated temporary instance {temp_instance.id}")
        temp_instance = None  # Mark as terminated

        # Yield snapshot info to all dependent fixtures
        yield {
            "snapshot_id": snapshot_id,
            "mapping_id": mapping.id,
        }

    finally:
        # Cleanup snapshot and mapping at end of session
        logger.info("Cleaning up shared snapshot and mapping")

        # Terminate temp instance if still running
        if temp_instance:
            try:
                client.instances.terminate(temp_instance.id)
                logger.info(f"Terminated temporary instance {temp_instance.id}")
            except Exception as e:
                logger.warning(f"Failed to terminate temporary instance: {e}")

        if snapshot_id:
            try:
                client.snapshots.delete(snapshot_id)
                logger.info(f"Deleted shared snapshot {snapshot_id}")
            except Exception as e:
                logger.error(f"Failed to delete shared snapshot: {e}")

        if mapping:
            try:
                client.mappings.delete(mapping.id)
                logger.info(f"Deleted shared mapping {mapping.id}")
            except Exception as e:
                logger.error(f"Failed to delete shared mapping: {e}")

        client.close()


@pytest.fixture(scope="session")
def shared_snapshot_id(shared_snapshot: dict) -> int:
    """Get the shared snapshot ID for tests that need it.

    Convenience fixture that extracts just the snapshot ID.
    """
    return shared_snapshot["snapshot_id"]


@pytest.fixture(scope="session")
def shared_mapping_id(shared_snapshot: dict) -> int:
    """Get the shared mapping ID for tests that need it.

    Convenience fixture that extracts just the mapping ID.
    """
    return shared_snapshot["mapping_id"]


@pytest.fixture(scope="session")
def shared_readonly_instance(
    shared_snapshot: dict,
    control_plane_url: str,
    analyst_alice_api_key: str,
) -> Generator[str, None, None]:
    """Create a shared read-only instance using the shared snapshot.

    OPTIMIZED: Now uses shared_snapshot instead of creating its own mapping/snapshot.
    Saves ~60s of redundant export time.

    Tests using this fixture:
    - sdk_query_test: Read-only Cypher queries
    - sdk_validation_test: Error handling, read-only validation
    - sdk_schema_test: Read-only schema metadata browsing

    Yields:
        str: Instance ID that can be passed to notebooks via INSTANCE_ID parameter
    """
    from graph_olap import GraphOLAPClient

    logger.info("Creating shared read-only instance (using shared_snapshot)")

    client = GraphOLAPClient(api_url=control_plane_url, api_key=analyst_alice_api_key)
    snapshot_id = shared_snapshot["snapshot_id"]

    instance = None
    try:
        # Create instance from shared snapshot (no redundant export!)
        instance = client.instances.create_and_wait(
            snapshot_id=snapshot_id,
            name="SharedReadOnlyInstance",
            wrapper_type=WrapperType.RYUGRAPH,
            timeout=180,
            poll_interval=5,
        )
        logger.info(f"Created shared instance: {instance.name} (id={instance.id}, status={instance.status})")
        logger.info(f"Instance URL: {instance.instance_url}")

        # Yield instance ID to tests
        yield str(instance.id)

    finally:
        # Cleanup instance only (snapshot/mapping cleaned up by shared_snapshot fixture)
        logger.info("Cleaning up shared read-only instance")
        if instance:
            try:
                client.instances.terminate(instance.id)
                logger.info(f"Terminated shared instance {instance.id}")
            except Exception as e:
                logger.error(f"Failed to terminate shared instance: {e}")

        client.close()


@pytest.fixture(scope="session")
def instance_pool(
    shared_snapshot: dict,
    control_plane_url: str,
    analyst_alice_api_key: str,
) -> Generator[dict[str, str], None, None]:
    """Create a pool of ready-to-use instances using the shared snapshot.

    OPTIMIZED: Now uses shared_snapshot instead of snapshot_pool.
    Eliminates redundant snapshot creation - saves ~60s.

    Pool Contents:
    - 3× Generic instances (Person + KNOWS graph)
    - All share the SAME snapshot (from shared_snapshot)
    - Each instance isolated (separate wrapper pods)

    Returns:
        dict with keys: "generic_1", "generic_2", "generic_3"
        Values are instance IDs (strings)
    """
    import concurrent.futures

    from graph_olap import GraphOLAPClient

    logger.info("Creating instance pool (using shared_snapshot)")

    client = GraphOLAPClient(api_url=control_plane_url, api_key=analyst_alice_api_key)

    # Use the single shared snapshot
    snapshot_id = shared_snapshot["snapshot_id"]
    logger.info(f"Using shared snapshot {snapshot_id} for all pool instances")

    instances = {}
    instance_objects = []

    def create_single_instance(index: int) -> tuple[int, object]:
        """Create one instance (uses existing client connection)."""
        try:
            instance = client.instances.create_and_wait(
                snapshot_id=snapshot_id,
                name=f"PoolInstance{index}",
                wrapper_type=WrapperType.RYUGRAPH,
                timeout=180,
                poll_interval=5,
            )
            logger.info(f"Pool instance {index} ready: {instance.name} (id={instance.id}, status={instance.status})")
            return (index, instance)
        except Exception as e:
            logger.error(f"Failed to create pool instance {index}: {e}")
            raise

    try:
        # Create 3 instances in parallel using ThreadPoolExecutor
        logger.info("Creating 3 pool instances in parallel...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all 3 instance creations
            futures = [
                executor.submit(create_single_instance, i)
                for i in range(1, 4)
            ]

            # Wait for all to complete
            for future in concurrent.futures.as_completed(futures):
                index, instance = future.result()
                instances[f"generic_{index}"] = str(instance.id)
                instance_objects.append(instance)

        logger.info(f"Instance pool created: {instances}")

        # Yield pool to tests
        yield instances

    finally:
        # Cleanup pool instances at end of session
        logger.info("Cleaning up instance pool")
        for key, instance_id in instances.items():
            try:
                client.instances.terminate(int(instance_id))
                logger.info(f"Terminated pool instance {key} (id={instance_id})")
            except Exception as e:
                logger.error(f"Failed to terminate pool instance {key}: {e}")

        client.close()
