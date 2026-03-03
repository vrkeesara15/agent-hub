from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional

from agents.base import BaseAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Informatica-to-GCP Migration Agent for an enterprise data platform.
Your job is to analyze Informatica PowerCenter XML exports and convert them into modern
Google Cloud Platform solutions:

**Primary target: BigQuery ELT + Airflow orchestration**
- Convert Informatica mappings to BigQuery SQL (ELT approach)
- Generate Cloud Composer / Airflow DAGs for orchestration
- Use SQL-driven models wherever possible

**For complex transformations:**
- If logic is very complex (e.g., multi-step Java transformations), recommend Dataflow (Apache Beam)
- For heavy aggregations/joins, suggest PySpark on Dataproc

**Conversion rules:**
- Source Qualifier → BigQuery SELECT statement
- Expression transformation → BigQuery SQL expressions / CASE statements
- Filter transformation → WHERE clause
- Joiner transformation → JOIN clause
- Lookup transformation → LEFT JOIN or subquery
- Aggregator transformation → GROUP BY with aggregate functions
- Router transformation → CASE WHEN or UNION ALL
- Sequence Generator → ROW_NUMBER() / GENERATE_UUID()
- Sorter transformation → ORDER BY clause
- Rank transformation → ROW_NUMBER() / RANK() window function
- Union transformation → UNION ALL
- Normalizer → UNNEST() in BigQuery
- Stored Procedure → BigQuery scripting or Dataflow
- Update Strategy → MERGE statement (especially for SCD Type 2)

**SCD (Slowly Changing Dimensions):**
- Always suggest MERGE statements for SCD patterns
- Include effective_date, expiry_date, and is_current flag patterns

When generating the Airflow DAG:
- Use BigQueryInsertJobOperator for SQL tasks
- Use proper task dependencies matching the Informatica workflow
- Include error handling and retry logic
- Use Airflow Variables for project/dataset configuration

Always respond with valid JSON matching the requested schema."""

# Known Informatica transformation types and their GCP equivalents
TRANSFORMATION_MAP = {
    "Source Qualifier": {"gcp": "BigQuery SELECT", "type": "sql"},
    "Expression": {"gcp": "BigQuery SQL Expression / CASE", "type": "sql"},
    "Filter": {"gcp": "BigQuery WHERE clause", "type": "sql"},
    "Joiner": {"gcp": "BigQuery JOIN", "type": "sql"},
    "Lookup": {"gcp": "BigQuery LEFT JOIN / Subquery", "type": "sql"},
    "Aggregator": {"gcp": "BigQuery GROUP BY", "type": "sql"},
    "Router": {"gcp": "BigQuery CASE WHEN / UNION ALL", "type": "sql"},
    "Sequence Generator": {"gcp": "ROW_NUMBER() / GENERATE_UUID()", "type": "sql"},
    "Sorter": {"gcp": "BigQuery ORDER BY", "type": "sql"},
    "Rank": {"gcp": "ROW_NUMBER() / RANK()", "type": "sql"},
    "Union": {"gcp": "BigQuery UNION ALL", "type": "sql"},
    "Normalizer": {"gcp": "BigQuery UNNEST()", "type": "sql"},
    "Update Strategy": {"gcp": "BigQuery MERGE (SCD)", "type": "sql"},
    "Stored Procedure": {"gcp": "Dataflow / BigQuery Scripting", "type": "dataflow"},
    "Custom Transformation": {"gcp": "Dataflow (Apache Beam) / Dataproc PySpark", "type": "dataflow"},
    "Java Transformation": {"gcp": "Dataflow (Apache Beam)", "type": "dataflow"},
    "SQL Transformation": {"gcp": "BigQuery SQL", "type": "sql"},
    "Transaction Control": {"gcp": "Airflow task dependencies", "type": "airflow"},
    "Target": {"gcp": "BigQuery destination table", "type": "sql"},
    "Source": {"gcp": "BigQuery source table", "type": "sql"},
}

UNSUPPORTED_PATTERNS = [
    "Midstream Binary Reader",
    "Data Masking",
    "Address Validator",
    "HTTP Transformation",
    "Web Service Consumer",
    "Unconnected Lookup",
]


class InformaticaMigrationAgent(BaseAgent):
    name = "Informatica Migration"
    slug = "informatica-migration"
    system_prompt = SYSTEM_PROMPT

    async def migrate(self, xml_content: str, filename: str = "workflow.xml") -> dict:
        """Main entry point: parse Informatica XML and generate GCP migration artifacts."""

        # Step 1: Parse XML and extract components
        parsed = self._parse_xml(xml_content)
        if parsed.get("error"):
            return parsed

        # Step 2: Analyze transformations
        analysis = self._analyze_transformations(parsed)

        # Step 3: Try LLM for intelligent conversion
        if self.llm.client is not None:
            llm_result = await self._llm_convert(xml_content, parsed, analysis)
            if llm_result:
                return llm_result

        # Step 4: Rule-based fallback
        return self._rule_based_convert(parsed, analysis, filename)

    def _parse_xml(self, xml_content: str) -> dict:
        """Parse Informatica PowerCenter XML export."""
        try:
            root = ET.fromstring(xml_content.strip())
        except ET.ParseError as e:
            return {
                "error": f"Invalid XML: {str(e)}",
                "sources": [],
                "targets": [],
                "transformations": [],
                "mappings": [],
                "workflows": [],
                "sessions": [],
            }

        result = {
            "sources": [],
            "targets": [],
            "transformations": [],
            "mappings": [],
            "workflows": [],
            "sessions": [],
            "connectors": [],
        }

        # Parse SOURCE definitions
        for source in root.iter("SOURCE"):
            src = {
                "name": source.get("NAME", ""),
                "database_type": source.get("DATABASETYPE", source.get("DBDNAME", "")),
                "owner": source.get("OWNERNAME", ""),
                "columns": [],
            }
            for field in source.iter("SOURCEFIELD"):
                src["columns"].append({
                    "name": field.get("NAME", ""),
                    "datatype": field.get("DATATYPE", ""),
                    "precision": field.get("PRECISION", ""),
                    "scale": field.get("SCALE", ""),
                    "nullable": field.get("NULLABLE", ""),
                })
            result["sources"].append(src)

        # Parse TARGET definitions
        for target in root.iter("TARGET"):
            tgt = {
                "name": target.get("NAME", ""),
                "database_type": target.get("DATABASETYPE", target.get("DBDNAME", "")),
                "owner": target.get("OWNERNAME", ""),
                "columns": [],
            }
            for field in target.iter("TARGETFIELD"):
                tgt["columns"].append({
                    "name": field.get("NAME", ""),
                    "datatype": field.get("DATATYPE", ""),
                    "precision": field.get("PRECISION", ""),
                    "scale": field.get("SCALE", ""),
                    "nullable": field.get("NULLABLE", ""),
                    "key_type": field.get("KEYTYPE", ""),
                })
            result["targets"].append(tgt)

        # Parse TRANSFORMATION definitions
        for xform in root.iter("TRANSFORMATION"):
            tf = {
                "name": xform.get("NAME", ""),
                "type": xform.get("TYPE", ""),
                "description": xform.get("DESCRIPTION", ""),
                "fields": [],
                "properties": {},
            }
            for field in xform.iter("TRANSFORMFIELD"):
                tf["fields"].append({
                    "name": field.get("NAME", ""),
                    "datatype": field.get("DATATYPE", ""),
                    "expression": field.get("EXPRESSION", ""),
                    "porttype": field.get("PORTTYPE", ""),
                })
            for prop in xform.iter("TABLEATTRIBUTE"):
                tf["properties"][prop.get("NAME", "")] = prop.get("VALUE", "")
            result["transformations"].append(tf)

        # Parse MAPPING definitions
        for mapping in root.iter("MAPPING"):
            mp = {
                "name": mapping.get("NAME", ""),
                "description": mapping.get("DESCRIPTION", ""),
            }
            result["mappings"].append(mp)

        # Parse WORKFLOW
        for workflow in root.iter("WORKFLOW"):
            wf = {
                "name": workflow.get("NAME", ""),
                "description": workflow.get("DESCRIPTION", ""),
                "scheduler": {},
            }
            for sched in workflow.iter("SCHEDULER"):
                wf["scheduler"] = {
                    "type": sched.get("SCHEDULETYPE", ""),
                    "repeat": sched.get("REPEAT", ""),
                    "start_date": sched.get("STARTDATE", ""),
                    "start_time": sched.get("STARTTIME", ""),
                }
            result["workflows"].append(wf)

        # Parse SESSION
        for session in root.iter("SESSION"):
            sess = {
                "name": session.get("NAME", ""),
                "mapping_name": session.get("MAPPINGNAME", ""),
                "description": session.get("DESCRIPTION", ""),
            }
            result["sessions"].append(sess)

        # Parse CONNECTOR (data flow connections)
        for conn in root.iter("CONNECTOR"):
            result["connectors"].append({
                "from_instance": conn.get("FROMINSTANCE", ""),
                "from_field": conn.get("FROMFIELD", ""),
                "to_instance": conn.get("TOINSTANCE", ""),
                "to_field": conn.get("TOFIELD", ""),
            })

        return result

    def _analyze_transformations(self, parsed: dict) -> dict:
        """Analyze transformations and categorize them."""
        analysis = {
            "total_transformations": len(parsed["transformations"]),
            "sql_convertible": 0,
            "needs_dataflow": 0,
            "unsupported": [],
            "transformation_summary": [],
            "has_scd_pattern": False,
            "has_complex_logic": False,
            "complexity": "low",
        }

        for tf in parsed["transformations"]:
            tf_type = tf["type"]
            mapping = TRANSFORMATION_MAP.get(tf_type, {})
            gcp_equiv = mapping.get("gcp", "Manual review required")
            conv_type = mapping.get("type", "manual")

            # Check for unsupported patterns
            if tf_type in UNSUPPORTED_PATTERNS or any(u.lower() in tf_type.lower() for u in UNSUPPORTED_PATTERNS):
                analysis["unsupported"].append({
                    "name": tf["name"],
                    "type": tf_type,
                    "reason": f"{tf_type} is not directly supported in GCP. Requires manual conversion.",
                })

            if conv_type == "sql":
                analysis["sql_convertible"] += 1
            elif conv_type == "dataflow":
                analysis["needs_dataflow"] += 1
                analysis["has_complex_logic"] = True

            # Check for SCD patterns
            if tf_type == "Update Strategy" or "scd" in tf.get("description", "").lower():
                analysis["has_scd_pattern"] = True
            # Check expressions for SCD indicators
            for field in tf.get("fields", []):
                expr = field.get("expression", "").lower()
                if any(kw in expr for kw in ["effective_date", "expiry_date", "is_current",
                                               "dd_update", "dd_insert", "dd_delete"]):
                    analysis["has_scd_pattern"] = True

            analysis["transformation_summary"].append({
                "name": tf["name"],
                "type": tf_type,
                "gcp_equivalent": gcp_equiv,
                "convertible": conv_type,
                "field_count": len(tf.get("fields", [])),
            })

        # Determine complexity
        total = analysis["total_transformations"]
        if total > 15 or analysis["needs_dataflow"] > 2:
            analysis["complexity"] = "high"
        elif total > 7 or analysis["needs_dataflow"] > 0:
            analysis["complexity"] = "medium"
        else:
            analysis["complexity"] = "low"

        return analysis

    async def _llm_convert(self, xml_content: str, parsed: dict, analysis: dict) -> Optional[dict]:
        """Use LLM for intelligent conversion."""
        try:
            import json

            # Build a concise summary for the LLM (XML can be too large)
            summary = self._build_summary_for_llm(parsed, analysis)

            prompt = (
                f"Convert this Informatica workflow to GCP.\n\n"
                f"**Workflow Summary:**\n{summary}\n\n"
                f"**Analysis:**\n"
                f"- Total transformations: {analysis['total_transformations']}\n"
                f"- SQL convertible: {analysis['sql_convertible']}\n"
                f"- Needs Dataflow: {analysis['needs_dataflow']}\n"
                f"- Has SCD pattern: {analysis['has_scd_pattern']}\n"
                f"- Complexity: {analysis['complexity']}\n\n"
                "Generate:\n"
                "1. BigQuery SQL for each transformation\n"
                "2. A complete Airflow DAG Python file\n"
                "3. List any unsupported patterns\n"
                "4. Suggest MERGE statement if SCD detected\n\n"
                "Respond with valid JSON:\n"
                "{\n"
                '  "bigquery_sql": "-- Complete BigQuery SQL",\n'
                '  "airflow_dag": "# Complete Airflow DAG Python code",\n'
                '  "transformation_map": [{"informatica": "...", "gcp": "...", "type": "sql|dataflow|airflow", "sql": "..."}],\n'
                '  "unsupported_patterns": [{"pattern": "...", "suggestion": "..."}],\n'
                '  "scd_merge": "-- MERGE statement if SCD detected, else empty string",\n'
                '  "summary": "Brief migration summary",\n'
                '  "complexity": "low|medium|high",\n'
                '  "recommendations": ["recommendation1", "recommendation2"]\n'
                "}"
            )

            # Run sync Anthropic SDK call in thread pool to avoid blocking event loop
            def _sync_call():
                return self.llm.client.messages.create(
                    model=self.llm.model,
                    max_tokens=8192,
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )

            api_response = await asyncio.wait_for(
                asyncio.to_thread(_sync_call),
                timeout=120,
            )
            text = api_response.content[0].text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [ln for ln in lines if not ln.strip().startswith("```")]
                text = "\n".join(lines)
            result = json.loads(text)

            # Merge with our parsed data
            result["sources"] = [s["name"] for s in parsed["sources"]]
            result["targets"] = [t["name"] for t in parsed["targets"]]
            result["workflow_name"] = parsed["workflows"][0]["name"] if parsed["workflows"] else "unknown"
            result["analysis"] = analysis

            return result
        except Exception as exc:
            logger.warning("LLM conversion failed: %s", exc)
            return None

    def _build_summary_for_llm(self, parsed: dict, analysis: dict) -> str:
        """Build a concise textual summary for the LLM."""
        parts = []

        if parsed["workflows"]:
            parts.append(f"Workflow: {parsed['workflows'][0]['name']}")
        if parsed["mappings"]:
            parts.append(f"Mapping: {parsed['mappings'][0]['name']}")

        if parsed["sources"]:
            src_names = [s["name"] for s in parsed["sources"]]
            parts.append(f"Sources: {', '.join(src_names)}")
            # Include columns of first source
            if parsed["sources"][0]["columns"]:
                cols = [c["name"] for c in parsed["sources"][0]["columns"][:10]]
                parts.append(f"  Source columns: {', '.join(cols)}")

        if parsed["targets"]:
            tgt_names = [t["name"] for t in parsed["targets"]]
            parts.append(f"Targets: {', '.join(tgt_names)}")
            if parsed["targets"][0]["columns"]:
                cols = [c["name"] for c in parsed["targets"][0]["columns"][:10]]
                parts.append(f"  Target columns: {', '.join(cols)}")

        parts.append(f"\nTransformations ({len(parsed['transformations'])}):")
        for tf in parsed["transformations"]:
            line = f"  - {tf['name']} (type: {tf['type']})"
            if tf.get("fields"):
                expr_fields = [f for f in tf["fields"] if f.get("expression")]
                if expr_fields:
                    exprs = [f"{f['name']} = {f['expression']}" for f in expr_fields[:5]]
                    line += f"\n    Expressions: {'; '.join(exprs)}"
            parts.append(line)

        if parsed["connectors"]:
            parts.append(f"\nData flow connections ({len(parsed['connectors'])}):")
            for conn in parsed["connectors"][:10]:
                parts.append(f"  {conn['from_instance']}.{conn['from_field']} → {conn['to_instance']}.{conn['to_field']}")

        return "\n".join(parts)

    def _rule_based_convert(self, parsed: dict, analysis: dict, filename: str) -> dict:
        """Rule-based conversion when LLM is unavailable."""

        # Generate BigQuery SQL
        bq_sql = self._generate_bigquery_sql(parsed, analysis)

        # Generate Airflow DAG
        airflow_dag = self._generate_airflow_dag(parsed, analysis)

        # Generate MERGE for SCD if detected
        scd_merge = ""
        if analysis["has_scd_pattern"] and parsed["targets"]:
            scd_merge = self._generate_scd_merge(parsed)

        # Build transformation map
        transformation_map = []
        for tf_summary in analysis["transformation_summary"]:
            transformation_map.append({
                "informatica": f"{tf_summary['name']} ({tf_summary['type']})",
                "gcp": tf_summary["gcp_equivalent"],
                "type": tf_summary["convertible"],
                "sql": "",
            })

        # Unsupported patterns
        unsupported = []
        for u in analysis["unsupported"]:
            unsupported.append({
                "pattern": f"{u['name']} ({u['type']})",
                "suggestion": u["reason"],
            })

        # Recommendations
        recommendations = self._build_recommendations(analysis, parsed)

        return {
            "bigquery_sql": bq_sql,
            "airflow_dag": airflow_dag,
            "transformation_map": transformation_map,
            "unsupported_patterns": unsupported,
            "scd_merge": scd_merge,
            "summary": self._build_migration_summary(parsed, analysis),
            "complexity": analysis["complexity"],
            "recommendations": recommendations,
            "sources": [s["name"] for s in parsed["sources"]],
            "targets": [t["name"] for t in parsed["targets"]],
            "workflow_name": parsed["workflows"][0]["name"] if parsed["workflows"] else filename,
            "analysis": analysis,
        }

    def _generate_bigquery_sql(self, parsed: dict, analysis: dict) -> str:
        """Generate BigQuery SQL from parsed Informatica components."""
        lines = [
            "-- ============================================================",
            "-- BigQuery SQL generated from Informatica workflow",
            f"-- Sources: {', '.join(s['name'] for s in parsed['sources'])}",
            f"-- Targets: {', '.join(t['name'] for t in parsed['targets'])}",
            "-- ============================================================",
            "",
        ]

        # Build source SELECT
        if parsed["sources"]:
            src = parsed["sources"][0]
            cols = [c["name"] for c in src["columns"]] if src["columns"] else ["*"]

            lines.append(f"-- Step 1: Extract from source ({src['name']})")
            lines.append("CREATE OR REPLACE TABLE `project.dataset.staging_{name}` AS".format(
                name=src["name"].lower()
            ))
            lines.append("SELECT")
            lines.append("  " + ",\n  ".join(cols))
            lines.append(f"FROM `project.dataset.{src['name'].lower()}`")
            lines.append(";")
            lines.append("")

        # Build transformation SQL
        step = 2
        for tf in parsed["transformations"]:
            tf_type = tf["type"]

            if tf_type in ("Expression", "SQL Transformation"):
                lines.append(f"-- Step {step}: {tf['name']} ({tf_type})")
                lines.append(f"CREATE OR REPLACE TABLE `project.dataset.transform_{tf['name'].lower()}` AS")
                lines.append("SELECT")
                expr_fields = []
                for field in tf.get("fields", []):
                    expr = field.get("expression", "")
                    name = field.get("name", "unknown")
                    if expr:
                        # Convert Informatica expressions to BigQuery
                        expr_bq = self._convert_expression(expr)
                        expr_fields.append(f"  {expr_bq} AS {name}")
                    else:
                        expr_fields.append(f"  {name}")
                if expr_fields:
                    lines.append(",\n".join(expr_fields))
                else:
                    lines.append("  *")
                lines.append(f"FROM `project.dataset.staging_{parsed['sources'][0]['name'].lower()}`" if parsed["sources"] else "FROM source_table")
                lines.append(";")
                lines.append("")
                step += 1

            elif tf_type == "Filter":
                lines.append(f"-- Step {step}: {tf['name']} (Filter)")
                filter_cond = tf.get("properties", {}).get("Filter Condition", "1=1")
                lines.append(f"-- Filter condition: {filter_cond}")
                lines.append(f"DELETE FROM `project.dataset.staging` WHERE NOT ({filter_cond});")
                lines.append("")
                step += 1

            elif tf_type == "Aggregator":
                lines.append(f"-- Step {step}: {tf['name']} (Aggregator → GROUP BY)")
                lines.append(f"CREATE OR REPLACE TABLE `project.dataset.agg_{tf['name'].lower()}` AS")
                group_fields = []
                agg_fields = []
                for field in tf.get("fields", []):
                    expr = field.get("expression", "")
                    name = field.get("name", "")
                    port = field.get("porttype", "")
                    if "OUTPUT" in port.upper() and expr:
                        agg_fields.append(f"  {self._convert_expression(expr)} AS {name}")
                    elif name:
                        group_fields.append(name)
                lines.append("SELECT")
                all_fields = [f"  {g}" for g in group_fields] + agg_fields
                lines.append(",\n".join(all_fields) if all_fields else "  *")
                lines.append("FROM source_table")
                if group_fields:
                    lines.append(f"GROUP BY {', '.join(group_fields)}")
                lines.append(";")
                lines.append("")
                step += 1

            elif tf_type == "Joiner":
                lines.append(f"-- Step {step}: {tf['name']} (Joiner → JOIN)")
                join_type = tf.get("properties", {}).get("Join Type", "Normal Join")
                bq_join = "INNER JOIN" if "Normal" in join_type else "LEFT OUTER JOIN" if "Master" in join_type else "FULL OUTER JOIN"
                join_cond = tf.get("properties", {}).get("Join Condition", "a.id = b.id")
                lines.append(f"-- Join type: {join_type} → {bq_join}")
                lines.append(f"-- JOIN ... ON {join_cond}")
                lines.append("")
                step += 1

            elif tf_type == "Lookup":
                lines.append(f"-- Step {step}: {tf['name']} (Lookup → LEFT JOIN)")
                lookup_sql = tf.get("properties", {}).get("Lookup Sql Override", "")
                if lookup_sql:
                    lines.append(f"-- Lookup SQL: {lookup_sql}")
                lines.append("-- LEFT JOIN lookup_table ON key = key")
                lines.append("")
                step += 1

            elif tf_type == "Router":
                lines.append(f"-- Step {step}: {tf['name']} (Router → CASE WHEN)")
                lines.append("-- Use CASE WHEN to route records:")
                for prop_name, prop_val in tf.get("properties", {}).items():
                    if "Group Filter" in prop_name:
                        lines.append(f"--   WHEN {prop_val} THEN ...")
                lines.append("")
                step += 1

            elif tf_type == "Sequence Generator":
                lines.append(f"-- Step {step}: {tf['name']} (Sequence → ROW_NUMBER)")
                lines.append("-- ROW_NUMBER() OVER (ORDER BY <key>) AS sequence_id")
                lines.append("-- Or: GENERATE_UUID() for unique identifiers")
                lines.append("")
                step += 1

        # Final target load
        if parsed["targets"]:
            tgt = parsed["targets"][0]
            lines.append(f"-- Final: Load into target ({tgt['name']})")
            tgt_cols = [c["name"] for c in tgt["columns"]] if tgt["columns"] else ["*"]
            lines.append(f"INSERT INTO `project.dataset.{tgt['name'].lower()}`")
            lines.append(f"  ({', '.join(tgt_cols)})")
            lines.append("SELECT")
            lines.append("  " + ",\n  ".join(tgt_cols))
            lines.append("FROM `project.dataset.final_staging`")
            lines.append(";")

        return "\n".join(lines)

    def _generate_airflow_dag(self, parsed: dict, analysis: dict) -> str:
        """Generate Airflow DAG from parsed Informatica components."""
        wf_name = parsed["workflows"][0]["name"] if parsed["workflows"] else "informatica_migration"
        dag_id = re.sub(r'[^a-zA-Z0-9_]', '_', wf_name.lower())

        # Determine schedule from Informatica scheduler
        schedule = "@daily"
        if parsed["workflows"] and parsed["workflows"][0].get("scheduler"):
            sched = parsed["workflows"][0]["scheduler"]
            repeat = sched.get("repeat", "").lower()
            if "hour" in repeat:
                schedule = "@hourly"
            elif "week" in repeat:
                schedule = "@weekly"
            elif "month" in repeat:
                schedule = "@monthly"

        sources = [s["name"] for s in parsed["sources"]]
        targets = [t["name"] for t in parsed["targets"]]

        lines = [
            '"""',
            f"Airflow DAG: {wf_name}",
            f"Auto-generated from Informatica workflow",
            f"Sources: {', '.join(sources)}",
            f"Targets: {', '.join(targets)}",
            '"""',
            "",
            "from datetime import datetime, timedelta",
            "from airflow import DAG",
            "from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator",
            "from airflow.operators.dummy import DummyOperator",
            "",
            "# Configuration",
            'PROJECT_ID = "{{ var.value.gcp_project_id }}"',
            'DATASET = "{{ var.value.bq_dataset }}"',
            "",
            "default_args = {",
            '    "owner": "data-engineering",',
            '    "depends_on_past": False,',
            '    "email_on_failure": True,',
            '    "email_on_retry": False,',
            "    \"retries\": 2,",
            '    "retry_delay": timedelta(minutes=5),',
            "}",
            "",
            f'with DAG(',
            f'    dag_id="{dag_id}",',
            "    default_args=default_args,",
            f'    description="Migrated from Informatica: {wf_name}",',
            f'    schedule_interval="{schedule}",',
            '    start_date=datetime(2025, 1, 1),',
            "    catchup=False,",
            f'    tags=["informatica-migration", "bigquery"],',
            ") as dag:",
            "",
            '    start = DummyOperator(task_id="start")',
            '    end = DummyOperator(task_id="end")',
            "",
        ]

        # Generate task for each transformation step
        task_names = []
        step = 1
        for tf in parsed["transformations"]:
            tf_type = tf["type"]
            mapping = TRANSFORMATION_MAP.get(tf_type, {})
            if mapping.get("type") != "sql":
                continue

            task_id = re.sub(r'[^a-zA-Z0-9_]', '_', tf["name"].lower())
            task_names.append(task_id)

            lines.append(f'    # Step {step}: {tf["name"]} ({tf_type})')
            lines.append(f'    {task_id} = BigQueryInsertJobOperator(')
            lines.append(f'        task_id="{task_id}",')
            lines.append("        configuration={")
            lines.append('            "query": {')
            lines.append(f'                "query": """')
            lines.append(f'                    -- {tf_type}: {tf["name"]}')
            lines.append(f'                    SELECT * FROM `{{{{ var.value.gcp_project_id }}}}.{{{{ var.value.bq_dataset }}}}.staging`')
            lines.append('                """,')
            lines.append('                "useLegacySql": False,')
            lines.append("            }")
            lines.append("        },")
            lines.append("    )")
            lines.append("")
            step += 1

        # Add target load task
        if parsed["targets"]:
            tgt = parsed["targets"][0]
            task_id = f"load_{re.sub(r'[^a-zA-Z0-9_]', '_', tgt['name'].lower())}"
            task_names.append(task_id)
            lines.append(f'    # Final: Load into {tgt["name"]}')
            lines.append(f'    {task_id} = BigQueryInsertJobOperator(')
            lines.append(f'        task_id="{task_id}",')
            lines.append("        configuration={")
            lines.append('            "query": {')
            lines.append(f'                "query": "INSERT INTO `{{{{ var.value.gcp_project_id }}}}.{{{{ var.value.bq_dataset }}}}.{tgt["name"].lower()}` SELECT * FROM staging",')
            lines.append('                "useLegacySql": False,')
            lines.append("            }")
            lines.append("        },")
            lines.append("    )")
            lines.append("")

        # Build task dependencies
        if task_names:
            lines.append("    # Task dependencies")
            lines.append(f"    start >> {task_names[0]}")
            for i in range(len(task_names) - 1):
                lines.append(f"    {task_names[i]} >> {task_names[i + 1]}")
            lines.append(f"    {task_names[-1]} >> end")
        else:
            lines.append("    start >> end")

        return "\n".join(lines)

    def _generate_scd_merge(self, parsed: dict) -> str:
        """Generate a MERGE statement for SCD Type 2 pattern."""
        tgt = parsed["targets"][0] if parsed["targets"] else {"name": "target_table", "columns": []}
        src = parsed["sources"][0] if parsed["sources"] else {"name": "source_table", "columns": []}

        tgt_name = tgt["name"].lower()
        src_name = src["name"].lower()
        key_cols = [c["name"] for c in tgt.get("columns", []) if c.get("key_type") in ("PRIMARY KEY", "PRIMARY")]
        if not key_cols:
            key_cols = [tgt["columns"][0]["name"]] if tgt.get("columns") else ["id"]

        all_cols = [c["name"] for c in tgt.get("columns", [])]
        non_key_cols = [c for c in all_cols if c not in key_cols]

        merge_key = " AND ".join(f"target.{k} = source.{k}" for k in key_cols)
        update_cols = ", ".join(f"target.{c} = source.{c}" for c in non_key_cols[:5])
        insert_cols = ", ".join(all_cols[:10])
        insert_vals = ", ".join(f"source.{c}" for c in all_cols[:10])

        return f"""-- SCD Type 2 MERGE statement
-- Generated from Informatica Update Strategy transformation
MERGE INTO `project.dataset.{tgt_name}` AS target
USING `project.dataset.{src_name}_staging` AS source
ON {merge_key}

-- Update existing records: close the current version
WHEN MATCHED AND (
  {' OR '.join(f'target.{c} != source.{c}' for c in non_key_cols[:3]) or '1=1'}
) THEN UPDATE SET
  {update_cols},
  target.effective_end_date = CURRENT_TIMESTAMP(),
  target.is_current = FALSE

-- Insert new records
WHEN NOT MATCHED THEN INSERT (
  {insert_cols},
  effective_start_date,
  effective_end_date,
  is_current
) VALUES (
  {insert_vals},
  CURRENT_TIMESTAMP(),
  TIMESTAMP('9999-12-31'),
  TRUE
);"""

    def _convert_expression(self, expr: str) -> str:
        """Convert Informatica expression syntax to BigQuery SQL."""
        converted = expr
        # Common Informatica function conversions
        replacements = {
            r'\bIIF\s*\(': "IF(",
            r'\bDECODE\s*\(': "CASE ",
            r'\bTO_CHAR\s*\(': "CAST(",
            r'\bTO_DATE\s*\(': "PARSE_DATE(",
            r'\bTO_INTEGER\s*\(': "CAST(",
            r'\bTO_DECIMAL\s*\(': "CAST(",
            r'\bSYSDATE\b': "CURRENT_TIMESTAMP()",
            r'\bSESSSTARTTIME\b': "CURRENT_TIMESTAMP()",
            r'\bLTRIM\s*\(': "LTRIM(",
            r'\bRTRIM\s*\(': "RTRIM(",
            r'\bSUBSTR\s*\(': "SUBSTR(",
            r'\bINSTR\s*\(': "STRPOS(",
            r'\bLENGTH\s*\(': "LENGTH(",
            r'\bIS_SPACES\s*\(': "TRIM(",
            r'\bREG_REPLACE\s*\(': "REGEXP_REPLACE(",
            r'\bREG_MATCH\s*\(': "REGEXP_CONTAINS(",
            r'\bADD_TO_DATE\s*\(': "DATE_ADD(",
        }
        for pattern, replacement in replacements.items():
            converted = re.sub(pattern, replacement, converted, flags=re.IGNORECASE)
        return converted

    def _build_recommendations(self, analysis: dict, parsed: dict) -> list:
        """Build migration recommendations."""
        recs = []

        if analysis["complexity"] == "high":
            recs.append("This is a complex workflow. Consider breaking it into smaller, independently schedulable DAGs.")

        if analysis["needs_dataflow"] > 0:
            recs.append(f"{analysis['needs_dataflow']} transformation(s) require Dataflow (Apache Beam) or Dataproc PySpark due to complexity.")

        if analysis["has_scd_pattern"]:
            recs.append("SCD pattern detected. Use BigQuery MERGE statements for incremental loads with history tracking.")

        if len(parsed["sources"]) > 3:
            recs.append("Multiple data sources detected. Consider using BigQuery federated queries for external sources.")

        if analysis["unsupported"]:
            recs.append(f"{len(analysis['unsupported'])} unsupported pattern(s) require manual review and custom implementation.")

        recs.append("Set up Airflow Variables for project_id, dataset, and connection details before deploying the DAG.")
        recs.append("Test the BigQuery SQL statements individually before enabling the full DAG.")

        return recs

    def _build_migration_summary(self, parsed: dict, analysis: dict) -> str:
        """Build a human-readable migration summary."""
        parts = []
        parts.append(f"Migration from Informatica to GCP BigQuery + Airflow.")
        parts.append(f"Found {len(parsed['sources'])} source(s), {len(parsed['targets'])} target(s), "
                      f"and {analysis['total_transformations']} transformation(s).")
        parts.append(f"Complexity: {analysis['complexity'].upper()}.")
        parts.append(f"{analysis['sql_convertible']} transformation(s) can be converted to BigQuery SQL.")
        if analysis['needs_dataflow'] > 0:
            parts.append(f"{analysis['needs_dataflow']} transformation(s) need Dataflow/Dataproc.")
        if analysis['has_scd_pattern']:
            parts.append("SCD pattern detected — MERGE statement generated.")
        if analysis['unsupported']:
            parts.append(f"{len(analysis['unsupported'])} unsupported pattern(s) flagged for manual review.")
        return " ".join(parts)
