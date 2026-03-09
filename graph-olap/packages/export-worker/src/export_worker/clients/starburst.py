"""Starburst client for executing UNLOAD queries.

This client handles:
- Connection management to Starburst REST API
- Building UNLOAD queries for Parquet export
- Submitting queries and polling for completion
- Error handling and retries
- Direct export via PyArrow (fallback when system.unload unavailable)

Three operation modes:
1. Async Python (K8s worker): submit_unload_async() + poll_query_async() with asyncio
2. Sync two-phase (Cloud Functions): submit_unload() + poll_query() called separately
3. Sync blocking (legacy): execute_unload() blocks until completion
4. Direct export: execute_and_export_async() for environments without system.unload
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import structlog
from google.cloud import storage
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from export_worker.exceptions import StarburstError

if TYPE_CHECKING:
    from export_worker.config import StarburstConfig

logger = structlog.get_logger()


@dataclass
class QuerySubmissionResult:
    """Result of submitting a query to Starburst."""

    query_id: str
    next_uri: str


@dataclass
class QueryPollResult:
    """Result of polling a Starburst query."""

    state: str  # RUNNING, FINISHED, FAILED
    next_uri: str | None  # None when FINISHED or FAILED
    error_message: str | None  # Set when FAILED


class StarburstClient:
    """Client for executing Starburst UNLOAD queries.

    Per ADR-025, all queries include client_tags for resource group routing.
    This enables Starburst to manage query concurrency server-side rather
    than requiring client-side semaphores.
    """

    def __init__(
        self,
        url: str,
        user: str,
        password: str,
        catalog: str = "bigquery",
        schema: str = "public",
        request_timeout: int = 30,
        client_tags: list[str] | None = None,
        source: str = "graph-olap-export-worker",
        gcp_project: str | None = None,
    ) -> None:
        """Initialize Starburst client.

        Args:
            url: Starburst REST API URL
            user: Username for authentication
            password: Password for authentication
            catalog: Default catalog
            schema: Default schema
            request_timeout: HTTP request timeout in seconds
            client_tags: Client tags for resource group routing (ADR-025)
            source: Source identifier for Starburst queries
            gcp_project: GCP project ID for direct export (PyArrow fallback)
        """
        self.url = url.rstrip("/")
        self.auth = (user, password)
        self.catalog = catalog
        self.schema = schema
        self.request_timeout = request_timeout
        self.client_tags = client_tags or ["graph-olap-export"]
        self.source = source
        self.gcp_project = gcp_project
        self._logger = logger.bind(component="starburst")

    @classmethod
    def from_config(cls, config: StarburstConfig, gcp_project: str | None = None) -> StarburstClient:
        """Create client from configuration object.

        Args:
            config: Starburst configuration
            gcp_project: GCP project ID for direct export (PyArrow fallback)
        """
        # Parse comma-separated client_tags string
        client_tags = [tag.strip() for tag in config.client_tags.split(",")]

        return cls(
            url=config.url,
            user=config.user,
            password=config.password.get_secret_value(),
            catalog=config.catalog,
            schema=config.schema_name,
            request_timeout=config.request_timeout_seconds,
            client_tags=client_tags,
            source=config.source,
            gcp_project=gcp_project,
        )

    def _get_headers(self, catalog: str) -> dict[str, str]:
        """Get HTTP headers for Starburst requests.

        Includes client_tags and source for resource group routing (ADR-025).
        """
        return {
            "X-Trino-Catalog": catalog,
            "X-Trino-Schema": self.schema,
            "X-Trino-Client-Tags": ",".join(self.client_tags),
            "X-Trino-Source": self.source,
            "Content-Type": "text/plain",
        }

    # -------------------------------------------------------------------------
    # Sync API - Used by Export Worker
    # -------------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
    )
    def submit_unload(
        self,
        sql: str,
        columns: list[str],
        destination: str,
        catalog: str | None = None,
    ) -> QuerySubmissionResult:
        """Submit an UNLOAD query to Starburst (fire-and-forget).

        Used by Export Submitter in the async architecture. Does NOT wait
        for query completion - returns immediately with query_id and next_uri
        for subsequent polling.

        Args:
            sql: Source SQL query
            columns: Column names in order (controls Parquet schema)
            destination: GCS destination path (gs://bucket/path/)
            catalog: Override default catalog

        Returns:
            QuerySubmissionResult with query_id and next_uri for polling.

        Raises:
            StarburstError: If submission fails.
        """
        unload_query = self._build_unload_query(sql, columns, destination)
        effective_catalog = catalog or self.catalog

        self._logger.info(
            "Submitting UNLOAD query",
            destination=destination,
            catalog=effective_catalog,
            column_count=len(columns),
            client_tags=self.client_tags,
        )

        with httpx.Client(auth=self.auth, timeout=self.request_timeout) as client:
            try:
                response = client.post(
                    f"{self.url}/v1/statement",
                    content=unload_query,
                    headers=self._get_headers(effective_catalog),
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise StarburstError(
                    f"Failed to submit query: {e.response.status_code}",
                    query=unload_query,
                ) from e

            result = response.json()

            # Check for immediate error
            if "error" in result:
                error = result["error"]
                raise StarburstError(
                    f"Query error: {error.get('message', 'Unknown error')}",
                    query=unload_query,
                    starburst_error_code=error.get("errorCode"),
                )

            query_id = result.get("id")
            next_uri = result.get("nextUri")

            if not query_id or not next_uri:
                raise StarburstError(
                    "Invalid response from Starburst: missing id or nextUri",
                    query=unload_query,
                )

            self._logger.info(
                "UNLOAD query submitted",
                query_id=query_id,
                destination=destination,
            )

            return QuerySubmissionResult(query_id=query_id, next_uri=next_uri)

    def poll_query(self, next_uri: str) -> QueryPollResult:
        """Poll a running Starburst query for status.

        Used by Export Poller in the async architecture. Makes a single
        HTTP request to check query status.

        Args:
            next_uri: The nextUri from the previous response.

        Returns:
            QueryPollResult with state, updated next_uri, and error if failed.

        Raises:
            StarburstError: If the poll request itself fails.
        """
        with httpx.Client(auth=self.auth, timeout=self.request_timeout) as client:
            try:
                response = client.get(next_uri)
                response.raise_for_status()
            except httpx.RequestError as e:
                raise StarburstError(f"Poll request failed: {e}") from e
            except httpx.HTTPStatusError as e:
                raise StarburstError(f"Poll request failed: {e.response.status_code}") from e

            result = response.json()

            # Check for error in response
            if "error" in result:
                error_msg = result["error"].get("message", "Unknown error")
                return QueryPollResult(
                    state="FAILED",
                    next_uri=None,
                    error_message=error_msg,
                )

            state = result.get("stats", {}).get("state", "UNKNOWN")
            new_next_uri = result.get("nextUri")

            if state == "FINISHED":
                self._logger.debug("Query finished")
                return QueryPollResult(state="FINISHED", next_uri=None, error_message=None)

            elif state == "FAILED":
                error_msg = result.get("error", {}).get("message", "Query failed")
                return QueryPollResult(state="FAILED", next_uri=None, error_message=error_msg)

            else:
                # QUEUED, PLANNING, STARTING, RUNNING, FINISHING
                return QueryPollResult(state="RUNNING", next_uri=new_next_uri, error_message=None)

    # -------------------------------------------------------------------------
    # Async Python API (K8s Worker) - Uses asyncio for concurrent processing
    # -------------------------------------------------------------------------

    async def submit_unload_async(
        self,
        sql: str,
        columns: list[str],
        destination: str,
        catalog: str | None = None,
    ) -> QuerySubmissionResult:
        """Submit an UNLOAD query to Starburst asynchronously.

        Used by K8s export worker for concurrent job processing.

        Args:
            sql: Source SQL query
            columns: Column names in order (controls Parquet schema)
            destination: GCS destination path (gs://bucket/path/)
            catalog: Override default catalog

        Returns:
            QuerySubmissionResult with query_id and next_uri for polling.

        Raises:
            StarburstError: If submission fails.
        """
        unload_query = self._build_unload_query(sql, columns, destination)
        effective_catalog = catalog or self.catalog

        self._logger.info(
            "Submitting UNLOAD query (async)",
            destination=destination,
            catalog=effective_catalog,
            column_count=len(columns),
            client_tags=self.client_tags,
        )

        async with httpx.AsyncClient(auth=self.auth, timeout=self.request_timeout) as client:
            try:
                response = await client.post(
                    f"{self.url}/v1/statement",
                    content=unload_query,
                    headers=self._get_headers(effective_catalog),
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise StarburstError(
                    f"Failed to submit query: {e.response.status_code}",
                    query=unload_query,
                ) from e
            except httpx.RequestError as e:
                raise StarburstError(f"Request failed: {e}") from e

            result = response.json()

            # Check for immediate error
            if "error" in result:
                error = result["error"]
                raise StarburstError(
                    f"Query error: {error.get('message', 'Unknown error')}",
                    query=unload_query,
                    starburst_error_code=error.get("errorCode"),
                )

            query_id = result.get("id")
            next_uri = result.get("nextUri")

            if not query_id or not next_uri:
                raise StarburstError(
                    "Invalid response from Starburst: missing id or nextUri",
                    query=unload_query,
                )

            self._logger.info(
                "UNLOAD query submitted (async)",
                query_id=query_id,
                destination=destination,
            )

            return QuerySubmissionResult(query_id=query_id, next_uri=next_uri)

    async def poll_query_async(self, next_uri: str) -> QueryPollResult:
        """Poll a running Starburst query for status asynchronously.

        Used by K8s export worker for non-blocking status checks.

        Args:
            next_uri: The nextUri from the previous response.

        Returns:
            QueryPollResult with state, updated next_uri, and error if failed.

        Raises:
            StarburstError: If the poll request itself fails.
        """
        async with httpx.AsyncClient(auth=self.auth, timeout=self.request_timeout) as client:
            try:
                response = await client.get(next_uri)
                response.raise_for_status()
            except httpx.RequestError as e:
                raise StarburstError(f"Poll request failed: {e}") from e
            except httpx.HTTPStatusError as e:
                raise StarburstError(f"Poll request failed: {e.response.status_code}") from e

            result = response.json()

            # Check for error in response
            if "error" in result:
                error_msg = result["error"].get("message", "Unknown error")
                return QueryPollResult(
                    state="FAILED",
                    next_uri=None,
                    error_message=error_msg,
                )

            state = result.get("stats", {}).get("state", "UNKNOWN")
            new_next_uri = result.get("nextUri")

            if state == "FINISHED":
                self._logger.debug("Query finished (async)")
                return QueryPollResult(state="FINISHED", next_uri=None, error_message=None)

            elif state == "FAILED":
                error_msg = result.get("error", {}).get("message", "Query failed")
                return QueryPollResult(state="FAILED", next_uri=None, error_message=error_msg)

            else:
                # QUEUED, PLANNING, STARTING, RUNNING, FINISHING
                return QueryPollResult(state="RUNNING", next_uri=new_next_uri, error_message=None)

    # -------------------------------------------------------------------------
    # Direct Export (PyArrow fallback for environments without system.unload)
    # -------------------------------------------------------------------------

    async def execute_and_export_async(
        self,
        sql: str,
        columns: list[str],
        destination: str,
        catalog: str | None = None,
    ) -> tuple[int, int]:
        """Execute query and export results directly to GCS as Parquet.

        This is a fallback for environments where system.unload is not available
        (e.g., Starburst Galaxy without a GCS catalog configured).

        Args:
            sql: Source SQL query
            columns: Column names in order (controls Parquet schema)
            destination: GCS destination path (gs://bucket/path/)
            catalog: Override default catalog

        Returns:
            Tuple of (row_count, size_bytes)

        Raises:
            StarburstError: If query execution or export fails
        """
        effective_catalog = catalog or self.catalog
        # Quote column names to handle reserved words
        column_list = ", ".join(f'"{col}"' for col in columns)
        select_query = f"SELECT {column_list} FROM ({sql})"

        self._logger.info(
            "Executing direct export (PyArrow fallback)",
            destination=destination,
            catalog=effective_catalog,
            column_count=len(columns),
        )

        # Execute query and collect all results
        all_data: list[list[Any]] = []
        result_columns: list[str] = []

        async with httpx.AsyncClient(auth=self.auth, timeout=self.request_timeout) as client:
            # Submit query
            try:
                response = await client.post(
                    f"{self.url}/v1/statement",
                    content=select_query,
                    headers=self._get_headers(effective_catalog),
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise StarburstError(
                    f"Failed to execute query: {e.response.status_code}",
                    query=select_query,
                ) from e

            result = response.json()
            if "error" in result:
                error = result["error"]
                raise StarburstError(
                    f"Query error: {error.get('message', 'Unknown error')}",
                    query=select_query,
                    starburst_error_code=error.get("errorCode"),
                )

            next_uri = result.get("nextUri")

            # Collect column names from first response
            if "columns" in result:
                result_columns = [col["name"] for col in result["columns"]]

            # Collect data rows
            if "data" in result:
                all_data.extend(result["data"])

            # Poll until complete
            while next_uri:
                try:
                    response = await client.get(next_uri, headers=self._get_headers(effective_catalog))
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    raise StarburstError(
                        f"Failed to poll query: {e.response.status_code}",
                        query=select_query,
                    ) from e

                result = response.json()
                if "error" in result:
                    error = result["error"]
                    raise StarburstError(
                        f"Query failed: {error.get('message', 'Unknown error')}",
                        query=select_query,
                        starburst_error_code=error.get("errorCode"),
                    )

                if "columns" in result and not result_columns:
                    result_columns = [col["name"] for col in result["columns"]]

                if "data" in result:
                    all_data.extend(result["data"])

                next_uri = result.get("nextUri")
                state = result.get("stats", {}).get("state", "RUNNING")
                if state in ("FINISHED", "FAILED"):
                    break

        if not all_data:
            self._logger.warning("Query returned no data", destination=destination)
            return (0, 0)

        # Build PyArrow table
        # Transpose data: list of rows -> dict of columns
        column_data: dict[str, list[Any]] = {col: [] for col in columns}
        for row in all_data:
            for i, col in enumerate(columns):
                if i < len(row):
                    column_data[col].append(row[i])
                else:
                    column_data[col].append(None)

        table = pa.table(column_data)

        # Write to GCS
        row_count, size_bytes = self._write_parquet_to_gcs(table, destination)

        self._logger.info(
            "Direct export completed",
            destination=destination,
            row_count=row_count,
            size_bytes=size_bytes,
        )

        return (row_count, size_bytes)

    def _write_parquet_to_gcs(self, table: pa.Table, gcs_path: str) -> tuple[int, int]:
        """Write PyArrow table to GCS as Parquet.

        Args:
            table: PyArrow table to write
            gcs_path: GCS destination (gs://bucket/path/)

        Returns:
            Tuple of (row_count, size_bytes)
        """
        # Parse GCS path
        if not gcs_path.startswith("gs://"):
            raise StarburstError(f"Invalid GCS path: {gcs_path}")

        path_without_prefix = gcs_path[5:]
        parts = path_without_prefix.split("/", 1)
        bucket_name = parts[0]
        blob_prefix = parts[1] if len(parts) > 1 else ""

        # Ensure trailing slash
        if blob_prefix and not blob_prefix.endswith("/"):
            blob_prefix += "/"

        # Create blob name
        blob_name = f"{blob_prefix}data.parquet"

        # Write to local temp file first, then upload
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            temp_path = f.name
            pq.write_table(table, temp_path, compression="snappy")

        try:
            # Get file size before upload
            size_bytes = os.path.getsize(temp_path)

            # Upload to GCS
            gcs_client = storage.Client(project=self.gcp_project)
            bucket = gcs_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(temp_path)

            self._logger.debug(
                "Uploaded Parquet to GCS",
                bucket=bucket_name,
                blob=blob_name,
                row_count=table.num_rows,
                size_bytes=size_bytes,
            )
        finally:
            # Clean up temp file
            os.unlink(temp_path)

        return (table.num_rows, size_bytes)

    # -------------------------------------------------------------------------
    # Query Building Utilities
    # -------------------------------------------------------------------------

    def _build_unload_query(self, sql: str, columns: list[str], destination: str) -> str:
        """Build the UNLOAD table function query.

        Args:
            sql: Source SQL query
            columns: Column names in order
            destination: GCS destination path

        Returns:
            Complete UNLOAD query string
        """
        # Quote column names to handle reserved words
        column_list = ", ".join(f'"{col}"' for col in columns)

        return f"""
SELECT * FROM TABLE(
    system.unload(
        input => TABLE(
            SELECT {column_list}
            FROM ({sql})
        ),
        location => '{destination}',
        format => 'PARQUET',
        compression => 'SNAPPY'
    )
)
""".strip()

    def validate_query(self, sql: str, catalog: str | None = None) -> list[dict]:
        """Validate a SQL query using EXPLAIN and return column metadata.

        Args:
            sql: SQL query to validate
            catalog: Override default catalog

        Returns:
            List of column metadata dicts with 'name' and 'type'

        Raises:
            StarburstError: If query is invalid
        """
        effective_catalog = catalog or self.catalog
        explain_query = f"DESCRIBE ({sql})"

        with httpx.Client(auth=self.auth, timeout=30.0) as client:
            try:
                response = client.post(
                    f"{self.url}/v1/statement",
                    content=explain_query,
                    headers={
                        "X-Trino-Catalog": effective_catalog,
                        "X-Trino-Schema": self.schema,
                        "Content-Type": "text/plain",
                    },
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise StarburstError(
                    f"Failed to validate query: {e.response.status_code}",
                    query=sql,
                ) from e

            result = response.json()

            if "error" in result:
                error = result["error"]
                raise StarburstError(
                    f"Invalid query: {error.get('message', 'Unknown error')}",
                    query=sql,
                    starburst_error_code=error.get("errorCode"),
                )

            # Collect column metadata from result
            columns = []
            next_uri = result.get("nextUri")

            while next_uri:
                response = client.get(next_uri, timeout=30.0)
                result = response.json()

                if "data" in result:
                    for row in result["data"]:
                        columns.append({"name": row[0], "type": row[1]})

                next_uri = result.get("nextUri")

            return columns
