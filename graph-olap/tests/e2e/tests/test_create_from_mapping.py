"""E2E tests for create instance from mapping workflow.

Tests the complete create-from-mapping flow:
1. Create instance directly from mapping (without pre-creating snapshot)
2. System creates snapshot automatically
3. Instance transitions: waiting_for_snapshot -> starting -> running
4. Verify instance is accessible and queryable

This is the "Quick Graph" UX flow - one-click graph from mapping.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Generator

import pytest

from conftest import get_control_plane_url
from graph_olap_schemas import WrapperType

if TYPE_CHECKING:
    from graph_olap import GraphOLAPClient

logger = logging.getLogger(__name__)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def test_mapping(graph_olap_client: GraphOLAPClient) -> Generator[dict, None, None]:
    """Create a mapping for create-from-mapping tests.

    Creates a simple Person/KNOWS graph mapping without a pre-existing snapshot.
    This simulates the user experience where they have just created a mapping.
    """
    from graph_olap.models.mapping import EdgeDefinition, NodeDefinition, PropertyDefinition

    logger.info("Creating test mapping for create-from-mapping E2E tests")

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

    mapping = graph_olap_client.mappings.create(
        name="CreateFromMappingE2E",
        description="Mapping for create-from-mapping E2E tests",
        node_definitions=[person_node],
        edge_definitions=[knows_edge],
    )

    logger.info(f"Created test mapping: {mapping.name} (id={mapping.id})")

    try:
        yield {
            "id": mapping.id,
            "name": mapping.name,
            "version": mapping.current_version,
        }
    finally:
        # Cleanup mapping and any snapshots/instances
        logger.info("Cleaning up test mapping")
        try:
            # First get snapshots for THIS mapping (not other parallel workers' mappings)
            snapshots = graph_olap_client.snapshots.list(mapping_id=mapping.id)

            # Terminate instances for each snapshot (filtered by snapshot_id for isolation)
            for snapshot in snapshots:
                instances = graph_olap_client.instances.list(snapshot_id=snapshot.id)
                for instance in instances:
                    try:
                        graph_olap_client.instances.terminate(instance.id)
                        logger.info(f"Terminated instance {instance.id} (snapshot {snapshot.id})")
                    except Exception as e:
                        logger.warning(f"Failed to terminate instance {instance.id}: {e}")

            # Then delete the snapshots
            for snapshot in snapshots:
                try:
                    graph_olap_client.snapshots.delete(snapshot.id)
                    logger.info(f"Deleted snapshot {snapshot.id}")
                except Exception as e:
                    logger.warning(f"Failed to delete snapshot {snapshot.id}: {e}")

            # Finally delete the mapping
            graph_olap_client.mappings.delete(mapping.id)
            logger.info(f"Deleted mapping {mapping.id}")
        except Exception as e:
            logger.error(f"Failed to cleanup test mapping: {e}")


# =============================================================================
# E2E Tests
# =============================================================================


@pytest.mark.e2e
class TestCreateFromMappingE2E:
    """E2E tests for create instance from mapping workflow."""

    def test_create_instance_from_mapping_basic(
        self,
        graph_olap_client: GraphOLAPClient,
        test_mapping: dict,
    ):
        """Test basic create instance from mapping workflow.

        Steps:
        1. Call create() with mapping_id (no snapshot exists yet)
        2. Verify instance starts in waiting_for_snapshot status
        3. Poll until instance is running
        4. Verify instance is accessible
        """
        logger.info("Starting create from mapping basic E2E test")

        # Create instance from mapping (this creates snapshot automatically)
        instance = graph_olap_client.instances.create(
            mapping_id=test_mapping["id"],
            name="CreateFromMappingE2E-Basic",
            wrapper_type=WrapperType.FALKORDB,
        )

        logger.info(f"Created instance: {instance.id}, status: {instance.status}")

        # Instance should start in waiting_for_snapshot status
        assert instance.status in ("waiting_for_snapshot", "starting"), \
            f"Expected waiting_for_snapshot or starting, got {instance.status}"

        try:
            # Wait for instance to become running
            start_time = time.time()
            timeout = 600  # 10 minutes for snapshot export + instance startup

            while time.time() - start_time < timeout:
                instance = graph_olap_client.instances.get(instance.id)
                logger.info(f"Instance status: {instance.status}")

                if instance.status == "running":
                    break

                if instance.status == "failed":
                    pytest.fail(f"Instance failed: {instance.error_message}")

                time.sleep(10)  # Poll every 10 seconds
            else:
                pytest.fail(f"Instance did not become running within {timeout}s")

            # Verify instance is accessible
            assert instance.instance_url is not None, "Instance should have URL"
            logger.info(f"Instance is running at {instance.instance_url}")

        finally:
            # Cleanup
            try:
                graph_olap_client.instances.terminate(instance.id)
                logger.info(f"Terminated instance {instance.id}")
            except Exception as e:
                logger.warning(f"Failed to terminate instance: {e}")

    def test_create_from_mapping_and_wait(
        self,
        graph_olap_client: GraphOLAPClient,
        test_mapping: dict,
    ):
        """Test create_and_wait convenience method.

        This tests the full "Quick Graph" UX where user waits for graph to be ready.
        """
        logger.info("Starting create_and_wait E2E test")

        # Track progress during creation
        progress_updates = []

        def on_progress(phase: str, completed: int, total: int):
            progress_updates.append((phase, completed, total))
            logger.info(f"Progress: {phase} - {completed}/{total}")

        try:
            # Create instance and wait for it to be running
            instance = graph_olap_client.instances.create_and_wait(
                mapping_id=test_mapping["id"],
                name="CreateFromMappingE2E-AndWait",
                wrapper_type=WrapperType.RYUGRAPH,
                ttl="PT2H",  # 2 hour TTL
                timeout=600,  # 10 minutes
                poll_interval=10,
                on_progress=on_progress,
            )

            logger.info(f"Instance is running: {instance.id}")

            # Verify instance properties
            assert instance.status == "running"
            assert instance.instance_url is not None
            assert instance.wrapper_type == "ryugraph"

            # Verify progress was reported
            assert len(progress_updates) > 0, "Should have received progress updates"

            # Try connecting to the instance
            conn = graph_olap_client.instances.connect(instance.id)
            logger.info(f"Connected to instance: {conn}")

            # Execute a simple query
            result = conn.query("MATCH (n:Person) RETURN count(n) as count")
            logger.info(f"Query result: {result}")

            assert result is not None

        finally:
            # Cleanup
            try:
                graph_olap_client.instances.terminate(instance.id)
                logger.info(f"Terminated instance {instance.id}")
            except Exception as e:
                logger.warning(f"Failed to terminate instance: {e}")

    def test_create_from_mapping_with_specific_version(
        self,
        graph_olap_client: GraphOLAPClient,
        test_mapping: dict,
    ):
        """Test create with specific mapping version.

        Creates instance using explicit version instead of current.
        """
        logger.info("Starting create with specific version E2E test")

        try:
            # Create instance from specific mapping version
            instance = graph_olap_client.instances.create(
                mapping_id=test_mapping["id"],
                mapping_version=test_mapping["version"],  # Use current version explicitly
                name="CreateFromMappingE2E-SpecificVersion",
                wrapper_type=WrapperType.FALKORDB,
                description="Instance from specific mapping version",
            )

            logger.info(f"Created instance: {instance.id}, status: {instance.status}")

            # Wait for running
            final_instance = graph_olap_client.instances.wait_until_running(
                instance.id,
                timeout=600,
                poll_interval=10,
            )

            assert final_instance.status == "running"
            logger.info(f"Instance is running: {final_instance.id}")

        finally:
            # Cleanup
            try:
                graph_olap_client.instances.terminate(instance.id)
            except Exception as e:
                logger.warning(f"Failed to terminate instance: {e}")

    def test_create_from_mapping_lifecycle_settings(
        self,
        graph_olap_client: GraphOLAPClient,
        test_mapping: dict,
    ):
        """Test that lifecycle settings are applied correctly.

        Verifies TTL and inactivity_timeout are set on the instance.
        """
        logger.info("Starting create lifecycle settings E2E test")

        try:
            instance = graph_olap_client.instances.create(
                mapping_id=test_mapping["id"],
                name="CreateFromMappingE2E-Lifecycle",
                wrapper_type=WrapperType.FALKORDB,
                ttl="PT4H",  # 4 hours
                inactivity_timeout="PT1H",  # 1 hour inactivity
            )

            logger.info(f"Created instance: {instance.id}")

            # Verify lifecycle settings
            assert instance.ttl == "PT4H", f"Expected TTL PT4H, got {instance.ttl}"
            assert instance.inactivity_timeout == "PT1H", \
                f"Expected inactivity_timeout PT1H, got {instance.inactivity_timeout}"

            # Wait for instance to be running and verify settings persist
            final_instance = graph_olap_client.instances.wait_until_running(
                instance.id,
                timeout=600,
                poll_interval=10,
            )

            assert final_instance.ttl == "PT4H"
            assert final_instance.inactivity_timeout == "PT1H"
            logger.info("Lifecycle settings verified after instance startup")

        finally:
            try:
                graph_olap_client.instances.terminate(instance.id)
            except Exception as e:
                logger.warning(f"Failed to terminate instance: {e}")

    def test_create_from_mapping_invalid_mapping(
        self,
        graph_olap_client: GraphOLAPClient,
    ):
        """Test error handling for invalid mapping ID."""
        from graph_olap.exceptions import NotFoundError

        logger.info("Testing create with invalid mapping ID")

        with pytest.raises(NotFoundError) as exc_info:
            graph_olap_client.instances.create(
                mapping_id=999999,  # Non-existent
                name="ShouldFail",
                wrapper_type=WrapperType.FALKORDB,
            )

        assert "not found" in str(exc_info.value).lower() or "404" in str(exc_info.value)
        logger.info(f"Got expected error: {exc_info.value}")

    def test_create_from_mapping_invalid_version(
        self,
        graph_olap_client: GraphOLAPClient,
        test_mapping: dict,
    ):
        """Test error handling for invalid mapping version."""
        from graph_olap.exceptions import NotFoundError

        logger.info("Testing create with invalid version")

        with pytest.raises(NotFoundError) as exc_info:
            graph_olap_client.instances.create(
                mapping_id=test_mapping["id"],
                mapping_version=999,  # Non-existent version
                name="ShouldFail",
                wrapper_type=WrapperType.FALKORDB,
            )

        assert "not found" in str(exc_info.value).lower() or "version" in str(exc_info.value).lower()
        logger.info(f"Got expected error: {exc_info.value}")
