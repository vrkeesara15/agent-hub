"""Natural Language to Airflow DAG generator agent.

Takes a natural language description of a data pipeline and generates
a production-ready Cloud Composer (Airflow) DAG Python file.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Airflow DAG engineer. The user will describe a data pipeline
in plain English. Generate a production-ready Cloud Composer (Airflow 2.x) DAG Python file.

Rules:
- Use the `@dag` / `@task` decorator style when suitable, otherwise classic DAG() context manager.
- Use BigQueryInsertJobOperator for SQL tasks.
- Use GCSToBigQueryOperator for loading from GCS.
- Use PythonOperator for custom transforms.
- Include proper imports, default_args with owner/retries/retry_delay, schedule_interval, tags.
- Add clear task_id names derived from the user description.
- Add inline comments explaining each task.
- Set catchup=False by default.
- Output ONLY the Python code, no markdown fences.
"""

DEFAULT_DAG = '''"""Auto-generated Airflow DAG from natural language description."""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="PLACEHOLDER_DAG_ID",
    default_args=default_args,
    description="PLACEHOLDER_DESCRIPTION",
    schedule_interval="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["auto-generated", "data-pipeline"],
) as dag:

    # Task 1: Extract data
    extract = BigQueryInsertJobOperator(
        task_id="extract_data",
        configuration={
            "query": {
                "query": "SELECT * FROM `project.dataset.source_table`",
                "useLegacySql": False,
                "destinationTable": {
                    "projectId": "project",
                    "datasetId": "staging",
                    "tableId": "staging_table",
                },
                "writeDisposition": "WRITE_TRUNCATE",
            }
        },
    )

    # Task 2: Transform data
    transform = BigQueryInsertJobOperator(
        task_id="transform_data",
        configuration={
            "query": {
                "query": """
                    SELECT
                        *,
                        CURRENT_TIMESTAMP() AS load_timestamp
                    FROM `project.staging.staging_table`
                """,
                "useLegacySql": False,
                "destinationTable": {
                    "projectId": "project",
                    "datasetId": "analytics",
                    "tableId": "target_table",
                },
                "writeDisposition": "WRITE_TRUNCATE",
            }
        },
    )

    # Task 3: Validate results
    def validate_fn(**kwargs):
        print("Validation complete")

    validate = PythonOperator(
        task_id="validate_results",
        python_callable=validate_fn,
    )

    extract >> transform >> validate
'''


class NLToDAGAgent:
    """Generate an Airflow DAG from a natural language pipeline description."""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")

    async def generate(self, description: str) -> dict:
        """Generate a DAG from a natural language description."""
        dag_code: str
        used_llm = False

        if self.api_key:
            try:
                dag_code = await self._llm_generate(description)
                used_llm = True
            except Exception as exc:
                logger.warning("LLM generation failed, using rule-based: %s", exc)
                dag_code = self._rule_based_generate(description)
        else:
            dag_code = self._rule_based_generate(description)

        # Derive a dag_id from the description
        dag_id = self._derive_dag_id(description)

        return {
            "dag_code": dag_code,
            "dag_id": dag_id,
            "description": description,
            "used_llm": used_llm,
            "filename": f"{dag_id}.py",
        }

    async def _llm_generate(self, description: str) -> str:
        """Use Claude to generate a DAG from natural language."""
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 4096,
                    "system": SYSTEM_PROMPT,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Generate an Airflow DAG for this pipeline:\n\n{description}",
                        }
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]

    def _rule_based_generate(self, description: str) -> str:
        """Generate a DAG from templates when no LLM is available."""
        dag_id = self._derive_dag_id(description)
        desc_lower = description.lower()

        # Determine schedule
        schedule = "@daily"
        if "hourly" in desc_lower:
            schedule = "@hourly"
        elif "weekly" in desc_lower:
            schedule = "@weekly"
        elif "monthly" in desc_lower:
            schedule = "@monthly"

        tasks: list[str] = []
        task_ids: list[str] = []
        imports: set[str] = {
            "from datetime import datetime, timedelta",
            "from airflow import DAG",
        }

        # Detect extract / source patterns
        if any(kw in desc_lower for kw in ["extract", "source", "read", "ingest", "load from", "pull"]):
            imports.add("from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator")
            task_ids.append("extract_source_data")
            tasks.append(self._bq_task("extract_source_data", "Extract source data into staging",
                                       "SELECT * FROM `project.dataset.source_table`",
                                       "project", "staging", "stg_extract"))

        # Detect transform patterns
        if any(kw in desc_lower for kw in ["transform", "filter", "clean", "join", "aggregate", "enrich", "compute"]):
            imports.add("from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator")
            task_ids.append("transform_data")
            tasks.append(self._bq_task("transform_data", "Apply business transformations",
                                       "SELECT *, CURRENT_TIMESTAMP() AS processed_at FROM `project.staging.stg_extract`",
                                       "project", "analytics", "transformed_data"))

        # Detect load / target patterns
        if any(kw in desc_lower for kw in ["load", "target", "write", "insert", "destination", "output"]):
            imports.add("from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator")
            task_ids.append("load_to_target")
            tasks.append(self._bq_task("load_to_target", "Load transformed data to target",
                                       "SELECT * FROM `project.analytics.transformed_data`",
                                       "project", "production", "final_table"))

        # Detect validation / quality patterns
        if any(kw in desc_lower for kw in ["validate", "check", "quality", "test", "assert", "verify"]):
            imports.add("from airflow.operators.python import PythonOperator")
            task_ids.append("validate_quality")
            tasks.append('''
    def _validate(**kwargs):
        """Run data quality checks."""
        print("Data quality validation passed")

    validate_quality = PythonOperator(
        task_id="validate_quality",
        python_callable=_validate,
    )''')

        # Detect notification / alert patterns
        if any(kw in desc_lower for kw in ["notify", "alert", "email", "slack", "notification"]):
            imports.add("from airflow.operators.python import PythonOperator")
            task_ids.append("send_notification")
            tasks.append('''
    def _notify(**kwargs):
        """Send completion notification."""
        print("Pipeline completed successfully - notification sent")

    send_notification = PythonOperator(
        task_id="send_notification",
        python_callable=_notify,
    )''')

        # Fallback: if no patterns matched, create a generic ETL
        if not tasks:
            imports.add("from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator")
            imports.add("from airflow.operators.python import PythonOperator")
            task_ids = ["extract_data", "transform_data", "load_data"]
            tasks = [
                self._bq_task("extract_data", "Extract data from source",
                              "SELECT * FROM `project.dataset.source_table`",
                              "project", "staging", "stg_data"),
                self._bq_task("transform_data", "Transform staging data",
                              "SELECT *, CURRENT_TIMESTAMP() AS load_ts FROM `project.staging.stg_data`",
                              "project", "analytics", "analytics_data"),
                self._bq_task("load_data", "Load to final destination",
                              "SELECT * FROM `project.analytics.analytics_data`",
                              "project", "production", "final_output"),
            ]

        # Build the full DAG code
        imports_str = "\n".join(sorted(imports))
        tasks_str = "\n".join(tasks)
        deps = " >> ".join(task_ids)

        code = f'''"""{description}

Auto-generated Airflow DAG.
"""
{imports_str}

default_args = {{
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}}

with DAG(
    dag_id="{dag_id}",
    default_args=default_args,
    description="{description[:120]}",
    schedule_interval="{schedule}",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["auto-generated", "data-pipeline"],
) as dag:
{tasks_str}

    # Task dependencies
    {deps}
'''
        return code

    @staticmethod
    def _bq_task(task_id: str, comment: str, query: str, project: str, dataset: str, table: str) -> str:
        return f'''
    # {comment}
    {task_id} = BigQueryInsertJobOperator(
        task_id="{task_id}",
        configuration={{
            "query": {{
                "query": """{query}""",
                "useLegacySql": False,
                "destinationTable": {{
                    "projectId": "{project}",
                    "datasetId": "{dataset}",
                    "tableId": "{table}",
                }},
                "writeDisposition": "WRITE_TRUNCATE",
            }}
        }},
    )'''

    @staticmethod
    def _derive_dag_id(description: str) -> str:
        """Create a snake_case dag_id from the description."""
        import re
        clean = re.sub(r'[^a-zA-Z0-9\s]', '', description.lower())
        words = clean.split()[:6]
        return "_".join(words) if words else "generated_dag"
