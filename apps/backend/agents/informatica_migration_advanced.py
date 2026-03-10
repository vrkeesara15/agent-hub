from __future__ import annotations

import asyncio
import json
import logging
import re
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from dataclasses import dataclass
from functools import partial
from typing import Optional

from agents.base import BaseAgent

logger = logging.getLogger(__name__)

ADVANCED_SYSTEM_PROMPT = """You are the Advanced Informatica-to-GCP Migration Agent for an enterprise data platform.
You specialize in converting COMPLEX Informatica PowerCenter XML exports with hundreds of mappings,
thousands of transformations, and tens of thousands of connectors.

**Primary target: BigQuery ELT + Airflow orchestration**

You will receive ONE MAPPING at a time with its specific transformations and data flow.
Generate precise BigQuery SQL for that mapping only.

**Conversion rules:**
- Source Qualifier → BigQuery SELECT statement
- Expression transformation → BigQuery SQL expressions / CASE statements
- Filter transformation → WHERE clause
- Joiner transformation → JOIN clause (use connector graph to determine join tables)
- Lookup transformation → LEFT JOIN or subquery
- Aggregator transformation → GROUP BY with aggregate functions
- Router transformation → CASE WHEN or UNION ALL
- Sequence Generator → ROW_NUMBER() / GENERATE_UUID()
- Sorter → ORDER BY clause
- Rank → ROW_NUMBER() / RANK() window function
- Union → UNION ALL
- Normalizer → UNNEST() in BigQuery
- Update Strategy → MERGE statement (especially for SCD Type 2)
- Transaction Control → Airflow task dependencies

**Important:**
- Convert ALL Informatica expressions to BigQuery SQL syntax
- Replace $$parameters with @param_name for BigQuery parameterized queries
- Include comments explaining each transformation step
- Handle Teradata-specific SQL dialect (QUALIFY, MINUS, ZEROIFNULL, etc.)

Always respond with valid JSON matching the requested schema."""

# Known Informatica transformation types and their GCP equivalents
TRANSFORMATION_MAP = {
    "Source Qualifier": {"gcp": "BigQuery SELECT", "type": "sql"},
    "Expression": {"gcp": "BigQuery SQL Expression / CASE", "type": "sql"},
    "Filter": {"gcp": "BigQuery WHERE clause", "type": "sql"},
    "Joiner": {"gcp": "BigQuery JOIN", "type": "sql"},
    "Lookup": {"gcp": "BigQuery LEFT JOIN / Subquery", "type": "sql"},
    "Lookup Procedure": {"gcp": "BigQuery LEFT JOIN / Subquery", "type": "sql"},
    "Aggregator": {"gcp": "BigQuery GROUP BY", "type": "sql"},
    "Router": {"gcp": "BigQuery CASE WHEN / UNION ALL", "type": "sql"},
    "Sequence Generator": {"gcp": "ROW_NUMBER() / GENERATE_UUID()", "type": "sql"},
    "Sorter": {"gcp": "BigQuery ORDER BY", "type": "sql"},
    "Rank": {"gcp": "ROW_NUMBER() / RANK()", "type": "sql"},
    "Union": {"gcp": "BigQuery UNION ALL", "type": "sql"},
    "Normalizer": {"gcp": "BigQuery UNNEST()", "type": "sql"},
    "Update Strategy": {"gcp": "BigQuery MERGE (SCD)", "type": "sql"},
    "Mapplet": {"gcp": "BigQuery SQL (inlined)", "type": "sql"},
    "Input Transformation": {"gcp": "BigQuery SQL (mapplet port)", "type": "sql"},
    "Output Transformation": {"gcp": "BigQuery SQL (mapplet port)", "type": "sql"},
    "Stored Procedure": {"gcp": "Dataflow / BigQuery Scripting", "type": "dataflow"},
    "Custom Transformation": {"gcp": "Dataflow (Apache Beam) / Dataproc PySpark", "type": "dataflow"},
    "Java Transformation": {"gcp": "Dataflow (Apache Beam)", "type": "dataflow"},
    "SQL Transformation": {"gcp": "BigQuery SQL", "type": "sql"},
    "Transaction Control": {"gcp": "Airflow task dependencies", "type": "airflow"},
    "Decision": {"gcp": "Airflow BranchPythonOperator", "type": "airflow"},
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

# Expanded expression conversion map (30+ patterns)
EXPRESSION_CONVERSIONS = {
    # Conditional
    r'\bIIF\s*\(': "IF(",
    r'\bDECODE\s*\(': "CASE ",
    # String functions
    r'\bTO_CHAR\s*\(': "CAST(",
    r'\bLTRIM\s*\(': "LTRIM(",
    r'\bRTRIM\s*\(': "RTRIM(",
    r'\bLPAD\s*\(': "LPAD(",
    r'\bRPAD\s*\(': "RPAD(",
    r'\bSUBSTR\s*\(': "SUBSTR(",
    r'\bINSTR\s*\(': "STRPOS(",
    r'\bLENGTH\s*\(': "LENGTH(",
    r'\bUPPER\s*\(': "UPPER(",
    r'\bLOWER\s*\(': "LOWER(",
    r'\bCONCAT\s*\(': "CONCAT(",
    r'\bREPLACESTR\s*\(': "REPLACE(",
    r'\bREPLACECHR\s*\(': "REGEXP_REPLACE(",
    r'\bREG_REPLACE\s*\(': "REGEXP_REPLACE(",
    r'\bREG_MATCH\s*\(': "REGEXP_CONTAINS(",
    r'\bREVERSE\s*\(': "REVERSE(",
    r'\bINITCAP\s*\(': "INITCAP(",
    # Numeric functions
    r'\bROUND\s*\(': "ROUND(",
    r'\bTRUNC\s*\(': "TRUNC(",
    r'\bABS\s*\(': "ABS(",
    r'\bPOWER\s*\(': "POWER(",
    r'\bMOD\s*\(': "MOD(",
    r'\bCEIL\s*\(': "CEIL(",
    r'\bFLOOR\s*\(': "FLOOR(",
    r'\bSIGN\s*\(': "SIGN(",
    # Date functions
    r'\bTO_DATE\s*\(': "PARSE_DATE(",
    r'\bADD_TO_DATE\s*\(': "DATE_ADD(",
    r'\bDATE_DIFF\s*\(': "DATE_DIFF(",
    r'\bGET_DATE_PART\s*\(': "EXTRACT(",
    r'\bLAST_DAY\s*\(': "LAST_DAY(",
    r'\bSET_DATE_PART\s*\(': "DATE_TRUNC(",
    r'\bSYSDATE\b': "CURRENT_TIMESTAMP()",
    r'\bSESSSTARTTIME\b': "CURRENT_TIMESTAMP()",
    # Type conversion
    r'\bTO_INTEGER\s*\(': "CAST(",
    r'\bTO_FLOAT\s*\(': "CAST(",
    r'\bTO_DECIMAL\s*\(': "CAST(",
    r'\bTO_BIGINT\s*\(': "CAST(",
    # Null handling — ISNULL(x) → (x IS NULL) requires special handling
    # We mark it for post-processing; simple regex can't rewrite ISNULL(x) to (x) IS NULL
    r'\bISNULL\s*\(': "_ISNULL_BQ(",
    r'\bNVL\s*\(': "IFNULL(",
    r'\bNVL2\s*\(': "IF(",
    # Validation — IS_NUMBER(x) → SAFE_CAST(x AS FLOAT64) IS NOT NULL
    r'\bIS_SPACES\s*\(': "TRIM(",
    r'\bIS_NUMBER\s*\(': "_IS_NUMBER_BQ(",
    # Error handling
    r'\bERROR\s*\(': "ERROR(",
    r'\bABORT\s*\(': "ERROR(",
    # Teradata-specific
    r'\bZEROIFNULL\s*\(': "IFNULL(",
    r'\bNULLIFZERO\s*\(': "NULLIF(",
    r'\bQUALIFY\b': "QUALIFY",
    r'\bMINUS\b': "EXCEPT DISTINCT",
}

# Informatica → BigQuery data type mapping
INFORMATICA_TO_BIGQUERY_TYPE_MAP: dict[str, str] = {
    "string": "STRING",
    "varchar": "STRING",
    "char": "STRING",
    "text": "STRING",
    "nstring": "STRING",
    "ntext": "STRING",
    "long": "STRING",
    "integer": "INT64",
    "int": "INT64",
    "small integer": "INT64",
    "smallint": "INT64",
    "bigint": "INT64",
    "short integer": "INT64",
    "number": "NUMERIC",
    "decimal": "NUMERIC",
    "numeric": "NUMERIC",
    "double": "FLOAT64",
    "float": "FLOAT64",
    "real": "FLOAT64",
    "date": "DATE",
    "date/time": "TIMESTAMP",
    "datetime": "TIMESTAMP",
    "timestamp": "TIMESTAMP",
    "binary": "BYTES",
    "blob": "BYTES",
    "clob": "STRING",
    "boolean": "BOOL",
}


@dataclass
class TableNamingConfig:
    """Configurable table naming strategy for generated SQL."""

    project: str = "project"
    dataset: str = "dataset"
    source_project: str = ""
    source_dataset: str = ""
    prefix_staging: str = "staging_"
    prefix_transform: str = "transform_"
    prefix_filtered: str = "filtered_"
    prefix_agg: str = "agg_"
    prefix_sorted: str = "sorted_"
    prefix_seq: str = "seq_"
    prefix_joined: str = "joined_"
    prefix_lookup: str = "with_lkp_"
    prefix_routed: str = "routed_"
    use_temp_tables: bool = False

    def format_table(self, prefix: str, name: str, is_source: bool = False) -> str:
        """Build fully qualified table name."""
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())
        proj = (self.source_project or self.project) if is_source else self.project
        ds = (self.source_dataset or self.dataset) if is_source else self.dataset
        return f"`{proj}.{ds}.{prefix}{sanitized}`"

    def create_stmt(self) -> str:
        """Return CREATE TEMP TABLE or CREATE OR REPLACE TABLE."""
        return "CREATE TEMP TABLE" if self.use_temp_tables else "CREATE OR REPLACE TABLE"


# Pre-compile all regex patterns ONCE at module load (avoids re-compiling 480K+ times)
_COMPILED_CONVERSIONS = [
    (re.compile(pattern, re.IGNORECASE), replacement)
    for pattern, replacement in EXPRESSION_CONVERSIONS.items()
]
_PARAM_RE = re.compile(r'\$\$(\w+)')

# Expression conversion cache — many expressions repeat across mappings
_expression_cache: dict[str, str] = {}


class InformaticaMigrationAdvancedAgent(BaseAgent):
    name = "Informatica Migration Advanced"
    slug = "informatica-migration-advanced"
    system_prompt = ADVANCED_SYSTEM_PROMPT

    def _heavy_parse_and_analyze(self, xml_content: str) -> dict:
        """CPU-bound: parse XML, build graph, analyze. Runs in thread pool."""
        parsed = self._parse_xml(xml_content)
        if parsed.get("error"):
            return {"parsed": parsed, "error": True}

        connector_graph = self._build_connector_graph(parsed)
        parameters = self._extract_parameters(parsed)
        analysis = self._analyze_transformations(parsed)
        mapping_groups = self._group_by_mapping(parsed, connector_graph)

        return {
            "parsed": parsed,
            "connector_graph": connector_graph,
            "parameters": parameters,
            "analysis": analysis,
            "mapping_groups": mapping_groups,
            "error": False,
        }

    async def migrate(
        self, xml_content: str, filename: str = "workflow.xml",
        parameter_overrides: dict[str, str] | None = None,
        parameter_file_content: str | None = None,
        table_naming_config: dict | None = None,
        enable_reconciliation: bool = True,
        reconciliation_threshold_pct: float = 5.0,
    ) -> dict:
        """Main entry: parse, build connector graph, process per-mapping, score."""

        # Steps 1-5: Run heavy CPU-bound parsing in thread pool
        prep = await asyncio.to_thread(self._heavy_parse_and_analyze, xml_content)
        if prep["error"]:
            return prep["parsed"]

        parsed = prep["parsed"]
        connector_graph = prep["connector_graph"]
        parameters = prep["parameters"]
        analysis = prep["analysis"]
        mapping_groups = prep["mapping_groups"]

        # Merge parameter overrides from .par file and/or explicit overrides
        if parameter_file_content:
            par_values = self._parse_parameter_file(parameter_file_content)
            merged_overrides = {**par_values, **(parameter_overrides or {})}
        else:
            merged_overrides = parameter_overrides or {}
        if merged_overrides:
            parameters = self._merge_parameter_overrides(parameters, merged_overrides)

        # Store configs for use by helper methods
        self._current_parsed = parsed
        self._mapping_confidences = []
        self._naming_config = (
            TableNamingConfig(**table_naming_config) if table_naming_config else TableNamingConfig()
        )
        self._enable_reconciliation = enable_reconciliation
        self._reconciliation_threshold_pct = reconciliation_threshold_pct

        # Step 6: Process mappings — LLM-assisted when available, else rule-based
        LLM_CONCURRENCY = 10

        # Step 6a: Deduplicate regional variants (structurally identical mappings)
        rep_groups, variant_map = self._detect_regional_groups(mapping_groups)
        total_variants = sum(len(v) for v in variant_map.values())

        if self.llm.client is not None:
            # ── LLM path: send representatives through LLM with concurrency limit ──
            llm_semaphore = asyncio.Semaphore(LLM_CONCURRENCY)

            async def _process_with_llm(mapping_name, group):
                async with llm_semaphore:
                    mg_cg = group.get("connector_graph", connector_graph)
                    return await self._process_mapping(
                        mapping_name, group, parsed, mg_cg, parameters
                    )

            logger.info(
                "Processing %d unique mappings with LLM (concurrency=%d, %d variants deduped)",
                len(rep_groups), LLM_CONCURRENCY, total_variants,
            )

            tasks = [
                _process_with_llm(name, group)
                for name, group in rep_groups.items()
            ]
            rep_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Expand with templated variants
            results = []
            for r in rep_results:
                if isinstance(r, Exception):
                    results.append(r)
                    continue
                results.append(r)
                rep_name = r["mapping_name"]
                if rep_name in variant_map:
                    for var_name, var_group in variant_map[rep_name]:
                        results.append(self._clone_result_for_variant(
                            r, rep_groups[rep_name], var_name, var_group
                        ))
        else:
            # ── No LLM: fast rule-based path in thread pool ──
            def _process_all_rule_based():
                _results = []
                for name, group in rep_groups.items():
                    try:
                        mg_cg = group.get("connector_graph", connector_graph)
                        r = self._process_mapping_rule_only_sync(
                            name, group, parsed, mg_cg, parameters
                        )
                        _results.append(r)
                    except Exception as exc:
                        logger.warning("Mapping processing failed for %s: %s", name, exc)
                return _results

            logger.info(
                "Processing %d unique mappings (rule-based, no LLM, %d variants deduped)",
                len(rep_groups), total_variants,
            )
            rep_results = await asyncio.to_thread(_process_all_rule_based)

            # Expand with templated variants
            results = []
            rep_by_name = {}
            for r in rep_results:
                results.append(r)
                rep_by_name[r["mapping_name"]] = r
            for rep_name, variants in variant_map.items():
                if rep_name in rep_by_name:
                    for var_name, var_group in variants:
                        results.append(self._clone_result_for_variant(
                            rep_by_name[rep_name], rep_groups.get(rep_name, {}),
                            var_name, var_group
                        ))

        mapping_results = []
        all_sql_parts = []
        expression_comparisons = []

        for r in results:
            if isinstance(r, Exception):
                logger.warning("Mapping processing failed: %s", r)
                continue
            mapping_results.append(r)
            if r.get("sql"):
                all_sql_parts.append(f"-- ========== Mapping: {r['mapping_name']} ==========\n{r['sql']}")
            expression_comparisons.extend(r.get("expression_comparisons", []))

        # Step 7: Combine results
        combined_sql = "\n\n".join(all_sql_parts) if all_sql_parts else "-- No SQL generated"

        # Step 8: Generate Airflow DAG
        airflow_dag = self._generate_airflow_dag(parsed, analysis, mapping_results)

        # Step 9: Generate SCD MERGE
        scd_merge = ""
        if analysis["has_scd_pattern"] and parsed["targets"]:
            scd_merge = self._generate_scd_merge(parsed)

        # Step 10: Build transformation map
        transformation_map = []
        for tf_summary in analysis["transformation_summary"]:
            transformation_map.append({
                "informatica": f"{tf_summary['name']} ({tf_summary['type']})",
                "gcp": tf_summary["gcp_equivalent"],
                "type": tf_summary["convertible"],
                "sql": "",
            })

        # Step 11: Build unsupported list
        unsupported = []
        for u in analysis["unsupported"]:
            unsupported.append({
                "pattern": f"{u['name']} ({u['type']})",
                "suggestion": u["reason"],
            })

        # Step 11b: Validate all generated SQL
        all_validations = []
        for mr in mapping_results:
            if mr.get("sql"):
                tgt_cols = []
                for mg_name, mg in mapping_groups.items():
                    if mg_name == mr["mapping_name"]:
                        for tgt in mg.get("targets", []):
                            tgt_cols.extend(c["name"] for c in tgt.get("columns", []))
                        break
                warnings = self._validate_sql(mr["sql"], mr["mapping_name"], tgt_cols[:5])
                all_validations.extend(warnings)
                mr["validation_warnings"] = warnings

        # Step 12: Calculate scorecard
        scorecard = self._calculate_scorecard(
            parsed, analysis, mapping_results, parameters, expression_comparisons
        )

        # Step 13: Recommendations
        recommendations = self._build_recommendations(analysis, parsed, scorecard)

        # Step 14: Trim payload for large migrations to keep response small
        # Cap expression_comparisons to first 500 (frontend paginates anyway)
        total_expr_count = len(expression_comparisons)
        trimmed_comparisons = expression_comparisons[:500]

        # Strip expression_comparisons from individual mapping_results to avoid duplication
        for mr in mapping_results:
            mr.pop("expression_comparisons", None)

        # Step 15: Build per-mapping SQL files dict for the sql/ folder
        mapping_sql_files = {}
        for mr in mapping_results:
            if mr.get("sql"):
                sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', mr["mapping_name"].lower())
                mapping_sql_files[f"{sanitized}.sql"] = mr["sql"]

        logger.info(
            "Migration complete: %d mapping_results, %d sql_files, %d sql_parts in combined",
            len(mapping_results), len(mapping_sql_files), len(all_sql_parts),
        )

        return {
            # Standard fields (compatible with base response)
            "bigquery_sql": combined_sql,
            "airflow_dag": airflow_dag,
            "transformation_map": transformation_map,
            "unsupported_patterns": unsupported,
            "scd_merge": scd_merge,
            "summary": self._build_migration_summary(parsed, analysis, scorecard),
            "complexity": analysis["complexity"],
            "recommendations": recommendations,
            "sources": [s["name"] for s in parsed["sources"]],
            "targets": [t["name"] for t in parsed["targets"]],
            "workflow_name": parsed["workflows"][0]["name"] if parsed["workflows"] else filename,
            "analysis": analysis,
            # Advanced-only fields
            "scorecard": scorecard,
            "mapping_results": mapping_results,
            "parameters": parameters,
            "expression_comparisons": trimmed_comparisons,
            "expression_comparisons_total": total_expr_count,
            "mapping_sql_files": mapping_sql_files,
            "validation_warnings": all_validations,
            "mapping_confidence": self._mapping_confidences,
            "confidence_summary": self._build_confidence_summary(),
        }

    # ── XML Parsing ──────────────────────────────────────────────

    def _parse_xml(self, xml_content: str) -> dict:
        """Parse Informatica PowerCenter XML export."""
        try:
            root = ET.fromstring(xml_content.strip())
        except ET.ParseError as e:
            return {
                "error": f"Invalid XML: {str(e)}",
                "sources": [], "targets": [], "transformations": [],
                "mappings": [], "workflows": [], "sessions": [], "connectors": [],
            }

        result = {
            "sources": [], "targets": [], "transformations": [],
            "mappings": [], "workflows": [], "sessions": [], "connectors": [],
            "mapplets": [], "worklets": [], "workflow_links": [],
            "task_instances": [], "command_tasks": [],
            "event_wait_tasks": [], "decision_tasks": [],
        }

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

        for mapping_elem in root.iter("MAPPING"):
            mp = {
                "name": mapping_elem.get("NAME", ""),
                "description": mapping_elem.get("DESCRIPTION", ""),
                "mapping_transformations": [],
                "mapping_connectors": [],
                "source_instance_names": [],
                "target_instance_names": [],
                "mapplet_instance_names": [],
                "instances": [],
            }

            # Parse per-mapping inline transformations (direct children only)
            for xform in mapping_elem.findall("TRANSFORMATION"):
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
                        "group": field.get("GROUP", ""),
                    })
                for prop in xform.iter("TABLEATTRIBUTE"):
                    tf["properties"][prop.get("NAME", "")] = prop.get("VALUE", "")
                mp["mapping_transformations"].append(tf)

            # Parse per-mapping instances to find source/target/mapplet references
            for inst in mapping_elem.findall("INSTANCE"):
                inst_type = (inst.get("TYPE") or "").upper()
                tf_name = inst.get("TRANSFORMATION_NAME", "")
                inst_name = inst.get("NAME", "")
                inst_record = {
                    "name": inst_name,
                    "type": inst_type,
                    "transformation_name": tf_name,
                    "transformation_type": inst.get("TRANSFORMATION_TYPE", ""),
                }
                mp["instances"].append(inst_record)
                if inst_type == "SOURCE" and tf_name:
                    mp["source_instance_names"].append(tf_name)
                elif inst_type == "TARGET" and tf_name:
                    mp["target_instance_names"].append(tf_name)
                elif inst_type == "MAPPLET" or inst.get("TRANSFORMATION_TYPE", "") == "Mapplet":
                    mp["mapplet_instance_names"].append(tf_name)

            # Parse per-mapping connectors (direct children only)
            for conn in mapping_elem.findall("CONNECTOR"):
                mp["mapping_connectors"].append({
                    "from_instance": conn.get("FROMINSTANCE", ""),
                    "from_field": conn.get("FROMFIELD", ""),
                    "to_instance": conn.get("TOINSTANCE", ""),
                    "to_field": conn.get("TOFIELD", ""),
                })

            result["mappings"].append(mp)

        # Parse MAPPLET definitions (reusable transformation sub-graphs)
        for mapplet_elem in root.iter("MAPPLET"):
            mplt = {
                "name": mapplet_elem.get("NAME", ""),
                "description": mapplet_elem.get("DESCRIPTION", ""),
                "transformations": [],
                "connectors": [],
                "input_ports": [],   # Input Transformation fields
                "output_ports": [],  # Output Transformation fields
            }
            for xform in mapplet_elem.findall("TRANSFORMATION"):
                tf = {
                    "name": xform.get("NAME", ""),
                    "type": xform.get("TYPE", ""),
                    "description": xform.get("DESCRIPTION", ""),
                    "fields": [],
                    "properties": {},
                }
                for field in xform.iter("TRANSFORMFIELD"):
                    fd = {
                        "name": field.get("NAME", ""),
                        "datatype": field.get("DATATYPE", ""),
                        "expression": field.get("EXPRESSION", ""),
                        "porttype": field.get("PORTTYPE", ""),
                        "group": field.get("GROUP", ""),
                    }
                    tf["fields"].append(fd)
                    # Capture input/output ports for inlining
                    if xform.get("TYPE") == "Input Transformation":
                        mplt["input_ports"].append(fd)
                    elif xform.get("TYPE") == "Output Transformation":
                        mplt["output_ports"].append(fd)
                for prop in xform.iter("TABLEATTRIBUTE"):
                    tf["properties"][prop.get("NAME", "")] = prop.get("VALUE", "")
                mplt["transformations"].append(tf)
            for conn in mapplet_elem.findall("CONNECTOR"):
                mplt["connectors"].append({
                    "from_instance": conn.get("FROMINSTANCE", ""),
                    "from_field": conn.get("FROMFIELD", ""),
                    "to_instance": conn.get("TOINSTANCE", ""),
                    "to_field": conn.get("TOFIELD", ""),
                })
            result["mapplets"].append(mplt)

        # Parse WORKLET definitions (sub-workflows)
        for worklet_elem in root.iter("WORKLET"):
            wklt = {
                "name": worklet_elem.get("NAME", ""),
                "description": worklet_elem.get("DESCRIPTION", ""),
                "tasks": [],
                "links": [],
            }
            for task_inst in worklet_elem.iter("TASKINSTANCE"):
                wklt["tasks"].append({
                    "name": task_inst.get("NAME", ""),
                    "type": task_inst.get("TASKTYPE", ""),
                    "task_name": task_inst.get("TASKNAME", ""),
                    "is_valid": task_inst.get("ISVALID", "YES"),
                    "reusable": task_inst.get("REUSABLE", "NO"),
                })
            for link in worklet_elem.iter("WORKFLOWLINK"):
                wklt["links"].append({
                    "from_task": link.get("FROMTASK", ""),
                    "to_task": link.get("TOTASK", ""),
                    "condition": link.get("CONDITION", ""),
                })
            result["worklets"].append(wklt)

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
            # Parse task instances within the workflow
            for task_inst in workflow.iter("TASKINSTANCE"):
                ti = {
                    "name": task_inst.get("NAME", ""),
                    "type": task_inst.get("TASKTYPE", ""),
                    "task_name": task_inst.get("TASKNAME", ""),
                    "is_valid": task_inst.get("ISVALID", "YES"),
                    "reusable": task_inst.get("REUSABLE", "NO"),
                    "workflow": wf["name"],
                }
                result["task_instances"].append(ti)

            # Parse workflow links (dependency edges)
            for link in workflow.iter("WORKFLOWLINK"):
                result["workflow_links"].append({
                    "from_task": link.get("FROMTASK", ""),
                    "to_task": link.get("TOTASK", ""),
                    "condition": link.get("CONDITION", ""),
                    "workflow": wf["name"],
                })

            result["workflows"].append(wf)

        # Parse tasks: Command, Event Wait, Decision
        for cmd in root.iter("TASK"):
            task_type = cmd.get("TYPE", "").upper()
            if task_type == "COMMAND":
                cmd_task = {
                    "name": cmd.get("NAME", ""),
                    "type": "COMMAND",
                    "description": cmd.get("DESCRIPTION", ""),
                    "commands": [],
                }
                for attr in cmd.iter("ATTRIBUTE"):
                    if attr.get("NAME", "").startswith("CmdLine"):
                        cmd_task["commands"].append(attr.get("VALUE", ""))
                result["command_tasks"].append(cmd_task)

            elif task_type == "EVENT WAIT":
                ew_task = {
                    "name": cmd.get("NAME", ""),
                    "type": "EVENT_WAIT",
                    "description": cmd.get("DESCRIPTION", ""),
                    "filewatch_name": "",
                    "delete_file": False,
                    "user_defined_event": False,
                }
                for attr in cmd.iter("ATTRIBUTE"):
                    attr_name = attr.get("NAME", "")
                    attr_value = attr.get("VALUE", "")
                    if attr_name == "Filewatch name":
                        ew_task["filewatch_name"] = attr_value
                    elif attr_name == "Delete Filewatch file":
                        ew_task["delete_file"] = attr_value.upper() == "YES"
                    elif attr_name == "User Defined Event":
                        ew_task["user_defined_event"] = attr_value.upper() == "YES"
                result["event_wait_tasks"].append(ew_task)

            elif task_type == "DECISION":
                dec_task = {
                    "name": cmd.get("NAME", ""),
                    "type": "DECISION",
                    "description": cmd.get("DESCRIPTION", ""),
                    "conditions": [],
                }
                for attr in cmd.iter("ATTRIBUTE"):
                    attr_name = attr.get("NAME", "")
                    attr_value = attr.get("VALUE", "")
                    if "condition" in attr_name.lower() or attr_name == "Decision Name":
                        dec_task["conditions"].append({
                            "name": attr_name,
                            "condition": attr_value,
                        })
                result["decision_tasks"].append(dec_task)

        # Parse sessions with transformation overrides (Pre/Post SQL)
        for session in root.iter("SESSION"):
            sess = {
                "name": session.get("NAME", ""),
                "mapping_name": session.get("MAPPINGNAME", ""),
                "description": session.get("DESCRIPTION", ""),
                "transformation_overrides": {},
                "parameter_filename": "",
            }
            # Session-level attributes
            for attr in session.iter("ATTRIBUTE"):
                if attr.get("NAME", "") == "Parameter Filename":
                    sess["parameter_filename"] = attr.get("VALUE", "")

            # SESSTRANSFORMATIONINST overrides
            for sti in session.iter("SESSTRANSFORMATIONINST"):
                inst_name = sti.get("TRANSFORMATIONNAME", "") or sti.get("SINSTANCENAME", "")
                overrides = {}
                for tattr in sti.iter("TABLEATTRIBUTE"):
                    ta_name = tattr.get("NAME", "")
                    ta_value = tattr.get("VALUE", "")
                    if ta_name in ("Pre SQL", "Post SQL", "Sql Query", "Source Filter",
                                   "Table Name Prefix", "Target Table Name", "Owner Name"):
                        # Decode XML-encoded newlines
                        ta_value = (ta_value.replace("&#xD;&#xA;", "\n")
                                    .replace("&#xA;", "\n").replace("&#xD;", "\n"))
                        overrides[ta_name] = ta_value
                if overrides:
                    sess["transformation_overrides"][inst_name] = overrides

            result["sessions"].append(sess)

        for conn in root.iter("CONNECTOR"):
            result["connectors"].append({
                "from_instance": conn.get("FROMINSTANCE", ""),
                "from_field": conn.get("FROMFIELD", ""),
                "to_instance": conn.get("TOINSTANCE", ""),
                "to_field": conn.get("TOFIELD", ""),
            })

        return result

    # ── Connector Graph ──────────────────────────────────────────

    def _build_connector_graph_from_connectors(self, connectors: list) -> dict:
        """Build a directed graph from a list of connector dicts.

        Returns:
            {
                "instance_edges": {from_instance: set(to_instance, ...)},
                "field_map": {(from_inst, from_field): (to_inst, to_field)},
                "reverse_edges": {to_instance: set(from_instance, ...)},
                "instance_fields_in": {instance: [field_name, ...]},
                "instance_fields_out": {instance: [field_name, ...]},
            }
        """
        instance_edges = defaultdict(set)
        reverse_edges = defaultdict(set)
        field_map = {}
        instance_fields_in = defaultdict(list)
        instance_fields_out = defaultdict(list)

        for conn in connectors:
            from_inst = conn["from_instance"]
            from_field = conn["from_field"]
            to_inst = conn["to_instance"]
            to_field = conn["to_field"]

            instance_edges[from_inst].add(to_inst)
            reverse_edges[to_inst].add(from_inst)
            field_map[(from_inst, from_field)] = (to_inst, to_field)
            instance_fields_out[from_inst].append(from_field)
            instance_fields_in[to_inst].append(to_field)

        return {
            "instance_edges": dict(instance_edges),
            "reverse_edges": dict(reverse_edges),
            "field_map": field_map,
            "instance_fields_in": dict(instance_fields_in),
            "instance_fields_out": dict(instance_fields_out),
        }

    def _build_connector_graph(self, parsed: dict) -> dict:
        """Build a directed graph from connectors for data flow understanding."""
        return self._build_connector_graph_from_connectors(parsed.get("connectors", []))

    # ── Parameter Extraction ─────────────────────────────────────

    def _extract_parameters(self, parsed: dict) -> list:
        """Extract $$parameter variables from expressions and workflow attributes."""
        param_registry = {}  # name -> {default_value, used_in_mappings, type_guess}

        # Scan all transformation expressions for $$variables
        for tf in parsed["transformations"]:
            for field in tf.get("fields", []):
                expr = field.get("expression", "")
                if not expr:
                    continue
                matches = re.findall(r'\$\$(\w+)', expr)
                for param_name in matches:
                    if param_name not in param_registry:
                        param_registry[param_name] = {
                            "name": param_name,
                            "default_value": "",
                            "used_in_mappings": [],
                            "type_guess": "string",
                        }
                    # Try to guess type from context
                    if any(kw in expr.lower() for kw in ["date", "time", "dt"]):
                        param_registry[param_name]["type_guess"] = "date"
                    elif any(kw in expr.lower() for kw in ["count", "num", "id", "amt", "amount"]):
                        param_registry[param_name]["type_guess"] = "number"

        # Scan workflow/session attributes for parameter filenames
        for wf in parsed.get("workflows", []):
            for attr_name, attr_val in wf.items():
                if isinstance(attr_val, str):
                    matches = re.findall(r'\$\$(\w+)', attr_val)
                    for param_name in matches:
                        if param_name not in param_registry:
                            param_registry[param_name] = {
                                "name": param_name,
                                "default_value": "",
                                "used_in_mappings": [],
                                "type_guess": "string",
                            }

        # Scan transformation properties for parameter references
        for tf in parsed["transformations"]:
            for prop_name, prop_val in tf.get("properties", {}).items():
                if isinstance(prop_val, str):
                    matches = re.findall(r'\$\$(\w+)', prop_val)
                    for param_name in matches:
                        if param_name not in param_registry:
                            param_registry[param_name] = {
                                "name": param_name,
                                "default_value": "",
                                "used_in_mappings": [],
                                "type_guess": "string",
                            }

        return list(param_registry.values())

    # ── Data Type Mapping ────────────────────────────────────────

    def _map_datatype_to_bigquery(
        self, informatica_type: str, precision: str = "", scale: str = "",
        for_ddl: bool = False,
    ) -> str:
        """Map an Informatica data type to BigQuery type.

        Handles precision/scale for NUMERIC types and falls back to STRING for unknowns.
        When ``for_ddl=True``, appends precision/scale annotation as a comment hint
        (e.g. ``NUMERIC  /* p=12,s=2 */``) for documentation in DDL comments.
        """
        normalized = informatica_type.strip().lower()
        bq_type = INFORMATICA_TO_BIGQUERY_TYPE_MAP.get(normalized, "")

        if not bq_type:
            logger.debug("Unmapped Informatica type '%s', defaulting to STRING", informatica_type)
            return "STRING"

        # NUMERIC with precision/scale
        if bq_type == "NUMERIC" and precision:
            try:
                p = int(precision)
                s = int(scale) if scale else 0
                # BigQuery NUMERIC is 38,9 max; BIGNUMERIC for larger
                if p > 0 and s >= 0:
                    if p > 29 or s > 9:
                        return "BIGNUMERIC"
                    if for_ddl:
                        return f"NUMERIC  /* p={p},s={s} */"
                    return "NUMERIC"
            except (ValueError, TypeError):
                pass

        return bq_type

    # ── Parameter File Parsing ───────────────────────────────────

    @staticmethod
    def _parse_parameter_file(par_content: str) -> dict[str, str]:
        """Parse an Informatica .par parameter file.

        Format: [folder.workflow.session.]$$PARAM_NAME=value
        Also handles: $$PARAM_NAME=value and PARAM_NAME=value
        Lines starting with # are comments.
        """
        params = {}
        for line in par_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Remove optional section prefix [folder.wf.session.]
            cleaned = re.sub(r'^\[.*?\]\.?', '', line)
            # Match $$PARAM=value or PARAM=value
            match = re.match(r'\$?\$?(\w+)\s*=\s*(.*)', cleaned)
            if match:
                params[match.group(1)] = match.group(2).strip()
        return params

    def _merge_parameter_overrides(
        self, parameters: list, overrides: dict[str, str],
    ) -> list:
        """Merge parameter overrides into the extracted parameter list."""
        param_by_name = {p["name"]: p for p in parameters}
        for name, value in overrides.items():
            if name in param_by_name:
                param_by_name[name]["default_value"] = value
            else:
                # Infer type from value
                type_guess = "string"
                if value.replace(".", "").replace("-", "").isdigit():
                    type_guess = "number"
                elif re.match(r'\d{4}-\d{2}-\d{2}', value):
                    type_guess = "date"
                param_by_name[name] = {
                    "name": name,
                    "default_value": value,
                    "used_in_mappings": [],
                    "type_guess": type_guess,
                }
        return list(param_by_name.values())

    def _generate_declare_statements(self, parameters: list) -> str:
        """Generate BigQuery DECLARE statements for parameters with known values."""
        declares = []
        for p in parameters:
            val = p.get("default_value", "")
            if not val:
                continue
            name = p["name"]
            tg = p.get("type_guess", "string")
            if tg == "number":
                bq_type = "INT64"
                declares.append(f"DECLARE @{name} {bq_type} DEFAULT {val};")
            elif tg == "date":
                bq_type = "DATE"
                declares.append(f"DECLARE @{name} {bq_type} DEFAULT DATE '{val}';")
            else:
                declares.append(f"DECLARE @{name} STRING DEFAULT '{val}';")
        return "\n".join(declares)

    # ── Session Override Extraction ───────────────────────────────

    def _get_session_sql_overrides(
        self, parsed: dict, mapping_name: str,
    ) -> dict:
        """Get Pre SQL / Post SQL / Sql Query overrides from the SESSION for a mapping.

        Returns: {instance_name: {"Pre SQL": ..., "Post SQL": ..., "Sql Query": ...}}
        """
        for sess in parsed.get("sessions", []):
            if sess.get("mapping_name") == mapping_name:
                return sess.get("transformation_overrides", {})
        return {}

    # ── Transformation Analysis ──────────────────────────────────

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
            "total_connectors": len(parsed.get("connectors", [])),
            "total_mappings": len(parsed.get("mappings", [])),
            "total_sources": len(parsed.get("sources", [])),
            "total_targets": len(parsed.get("targets", [])),
        }

        for tf in parsed["transformations"]:
            tf_type = tf["type"]
            mapping = TRANSFORMATION_MAP.get(tf_type, {})
            gcp_equiv = mapping.get("gcp", "Manual review required")
            conv_type = mapping.get("type", "manual")

            if tf_type in UNSUPPORTED_PATTERNS or any(
                u.lower() in tf_type.lower() for u in UNSUPPORTED_PATTERNS
            ):
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

            # SCD detection (enhanced)
            if tf_type == "Update Strategy" or "scd" in tf.get("description", "").lower():
                analysis["has_scd_pattern"] = True
            for field in tf.get("fields", []):
                expr = field.get("expression", "").lower()
                name = field.get("name", "").lower()
                if any(kw in expr for kw in [
                    "effective_date", "expiry_date", "is_current",
                    "dd_update", "dd_insert", "dd_delete",
                    "effective_start", "effective_end", "current_flag",
                ]):
                    analysis["has_scd_pattern"] = True
                if any(kw in name for kw in [
                    "effective_date", "expiry_date", "is_current",
                    "effective_start", "effective_end", "current_flag",
                ]):
                    analysis["has_scd_pattern"] = True

            analysis["transformation_summary"].append({
                "name": tf["name"],
                "type": tf_type,
                "gcp_equivalent": gcp_equiv,
                "convertible": conv_type,
                "field_count": len(tf.get("fields", [])),
            })

        total = analysis["total_transformations"]
        if total > 15 or analysis["needs_dataflow"] > 2:
            analysis["complexity"] = "high"
        elif total > 7 or analysis["needs_dataflow"] > 0:
            analysis["complexity"] = "medium"
        else:
            analysis["complexity"] = "low"

        return analysis

    # ── Mapping Grouping ─────────────────────────────────────────

    def _group_by_mapping(self, parsed: dict, connector_graph: dict) -> dict:
        """Group transformations by mapping using per-mapping parsed data.

        Each MAPPING element in the XML contains its own TRANSFORMATION and
        CONNECTOR children.  We use these directly instead of BFS on a global
        connector graph, so each mapping gets only its own transformations.
        """
        source_by_name = {s["name"]: s for s in parsed["sources"]}
        target_by_name = {t["name"]: t for t in parsed["targets"]}

        mapping_groups = {}

        if parsed["mappings"]:
            for mp in parsed["mappings"]:
                mp_name = mp["name"]

                # Use per-mapping transformations parsed from MAPPING children
                transformations = mp.get("mapping_transformations", [])

                # Match sources by INSTANCE TYPE="SOURCE" references
                sources = [
                    source_by_name[n]
                    for n in mp.get("source_instance_names", [])
                    if n in source_by_name
                ]

                # Match targets by INSTANCE TYPE="TARGET" references
                targets = [
                    target_by_name[n]
                    for n in mp.get("target_instance_names", [])
                    if n in target_by_name
                ]

                # Build per-mapping connector graph from MAPPING's own CONNECTORs
                mp_connectors = mp.get("mapping_connectors", [])
                mp_connector_graph = (
                    self._build_connector_graph_from_connectors(mp_connectors)
                    if mp_connectors
                    else connector_graph
                )

                mapping_groups[mp_name] = {
                    "transformations": transformations if transformations else parsed["transformations"],
                    "sources": sources if sources else parsed["sources"],
                    "targets": targets if targets else parsed["targets"],
                    "description": mp.get("description", ""),
                    "connector_graph": mp_connector_graph,
                    "mapplet_instance_names": mp.get("mapplet_instance_names", []),
                    "instances": mp.get("instances", []),
                }
        else:
            # No explicit mappings: treat all transformations as one group
            mapping_groups["default_mapping"] = {
                "transformations": parsed["transformations"],
                "sources": parsed["sources"],
                "targets": parsed["targets"],
                "description": "",
                "connector_graph": connector_graph,
            }

        return mapping_groups

    # ── Regional Deduplication ────────────────────────────────────

    def _detect_regional_groups(self, mapping_groups: dict) -> tuple:
        """Detect structurally identical mappings for deduplication.

        Mappings with the same transformation signature (sorted types + field
        counts) are assumed to be regional variants (e.g. N/S/P/W patterns).
        Only one representative per group is processed; variants get templated SQL.

        Returns:
            (representative_groups, variant_map)
            - representative_groups: {name: group} — mappings to process
            - variant_map: {rep_name: [(variant_name, variant_group), ...]}
        """
        if len(mapping_groups) <= 1:
            return dict(mapping_groups), {}

        # Build structural signature per mapping — include expression content for safety
        signatures = {}
        for name, group in mapping_groups.items():
            tfs = group.get("transformations", [])
            sig_parts = []
            for tf in tfs:
                # Include type, field count, and a hash of expression content
                expr_hash = hash(tuple(
                    f.get("expression", "")[:50] for f in tf.get("fields", [])
                    if f.get("expression")
                ))
                sig_parts.append((tf["type"], len(tf.get("fields", [])), expr_hash))
            sig = tuple(sorted(sig_parts))
            signatures[name] = sig

        # Group by signature
        sig_groups = defaultdict(list)
        for name, sig in signatures.items():
            sig_groups[sig].append(name)

        representative_groups = {}
        variant_map = {}

        for sig, names in sig_groups.items():
            rep = names[0]
            representative_groups[rep] = mapping_groups[rep]
            if len(names) > 1:
                variant_map[rep] = [
                    (n, mapping_groups[n]) for n in names[1:]
                ]

        if variant_map:
            total_variants = sum(len(v) for v in variant_map.values())
            logger.info(
                "Regional dedup: %d unique patterns -> %d representatives + %d variants",
                len(sig_groups), len(representative_groups), total_variants,
            )

        return representative_groups, variant_map

    def _clone_result_for_variant(
        self, rep_result: dict, rep_group: dict,
        var_name: str, var_group: dict,
    ) -> dict:
        """Clone a representative mapping result for a regional variant."""
        rep_name = rep_result["mapping_name"]
        sql = rep_result.get("sql", "")
        if sql:
            sql = self._template_variant_sql(
                sql, rep_group, var_group, rep_name, var_name
            )

        return {
            "mapping_name": var_name,
            "status": rep_result.get("status", "converted"),
            "sql": sql,
            "transformations_used": rep_result.get("transformations_used", 0),
            "transformations_converted": rep_result.get("transformations_converted", 0),
            "expressions_converted": rep_result.get("expressions_converted", 0),
            "expressions_total": rep_result.get("expressions_total", 0),
            "issues": list(rep_result.get("issues", [])),
            "expression_comparisons": [],
            "used_llm": rep_result.get("used_llm", False),
            "regional_variant_of": rep_name,
        }

    def _template_variant_sql(
        self, sql: str, rep_group: dict, var_group: dict,
        rep_name: str, var_name: str,
    ) -> str:
        """Create variant SQL by replacing source/target/mapping name references."""
        result = sql

        # Replace mapping name references
        result = result.replace(rep_name, var_name)
        result = result.replace(rep_name.lower(), var_name.lower())

        # Replace source table names
        rep_sources = [s["name"] for s in rep_group.get("sources", [])]
        var_sources = [s["name"] for s in var_group.get("sources", [])]
        for rs, vs in zip(rep_sources, var_sources):
            if rs != vs:
                result = result.replace(rs, vs)
                result = result.replace(rs.lower(), vs.lower())

        # Replace target table names
        rep_targets = [t["name"] for t in rep_group.get("targets", [])]
        var_targets = [t["name"] for t in var_group.get("targets", [])]
        for rt, vt in zip(rep_targets, var_targets):
            if rt != vt:
                result = result.replace(rt, vt)
                result = result.replace(rt.lower(), vt.lower())

        return result

    # ── Per-Mapping Processing ───────────────────────────────────

    async def _process_mapping(
        self, mapping_name: str, group: dict, parsed: dict,
        connector_graph: dict, parameters: list,
    ) -> dict:
        """Process a single mapping: try LLM, fall back to rule-based."""
        transformations = group["transformations"]
        sources = group["sources"]
        targets = group["targets"]

        # Collect expressions for comparison
        expression_comparisons = []
        total_expressions = 0
        converted_expressions = 0

        for tf in transformations:
            for field in tf.get("fields", []):
                original_expr = field.get("expression", "")
                if not original_expr:
                    continue
                total_expressions += 1
                converted_expr = self._convert_expression(original_expr, parameters)
                status = "converted" if converted_expr != original_expr else "partial"
                if original_expr == converted_expr:
                    status = "failed"
                else:
                    converted_expressions += 1
                expression_comparisons.append({
                    "original": original_expr,
                    "converted": converted_expr,
                    "status": status,
                    "mapping": mapping_name,
                })

        # Try LLM conversion for this mapping
        sql = None
        used_llm = False
        if self.llm.client is not None:
            sql = await self._llm_convert_mapping(
                mapping_name, group, connector_graph, parameters
            )
            if sql:
                used_llm = True

        # Fall back to rule-based
        if not sql:
            sql = self._rule_based_mapping_sql(
                mapping_name, group, connector_graph, parameters
            )

        tf_converted = sum(
            1 for tf in transformations
            if TRANSFORMATION_MAP.get(tf["type"], {}).get("type") == "sql"
        )

        issues = []
        for tf in transformations:
            tf_type = tf["type"]
            if tf_type in UNSUPPORTED_PATTERNS or TRANSFORMATION_MAP.get(tf_type, {}).get("type") == "dataflow":
                issues.append(f"Cannot auto-convert {tf['name']} ({tf_type}) - requires manual review")

        return {
            "mapping_name": mapping_name,
            "status": "converted" if tf_converted == len(transformations) else
                      "partial" if tf_converted > 0 else "failed",
            "sql": sql,
            "transformations_used": len(transformations),
            "transformations_converted": tf_converted,
            "expressions_converted": converted_expressions,
            "expressions_total": total_expressions,
            "issues": issues,
            "expression_comparisons": expression_comparisons,
            "used_llm": used_llm,
        }

    def _process_mapping_rule_only_sync(
        self, mapping_name: str, group: dict, parsed: dict,
        connector_graph: dict, parameters: list,
    ) -> dict:
        """Process a mapping using only rule-based conversion (no LLM). Fast path. Sync."""
        transformations = group["transformations"]

        # Collect expressions for comparison
        expression_comparisons = []
        total_expressions = 0
        converted_expressions = 0
        for tf in transformations:
            for field in tf.get("fields", []):
                original_expr = field.get("expression", "")
                if not original_expr:
                    continue
                total_expressions += 1
                converted_expr = self._convert_expression(original_expr, parameters)
                if converted_expr != original_expr:
                    converted_expressions += 1
                    status = "converted"
                else:
                    status = "failed"
                expression_comparisons.append({
                    "original": original_expr,
                    "converted": converted_expr,
                    "status": status,
                    "mapping": mapping_name,
                })

        session_overrides = self._get_session_sql_overrides(
            parsed, mapping_name
        )
        sql = self._rule_based_mapping_sql(
            mapping_name, group, connector_graph, parameters,
            naming=getattr(self, '_naming_config', None),
            session_overrides=session_overrides,
        )

        tf_converted = sum(
            1 for tf in transformations
            if TRANSFORMATION_MAP.get(tf["type"], {}).get("type") == "sql"
        )

        issues = []
        for tf in transformations:
            tf_type = tf["type"]
            if tf_type in UNSUPPORTED_PATTERNS or TRANSFORMATION_MAP.get(tf_type, {}).get("type") == "dataflow":
                issues.append(f"Cannot auto-convert {tf['name']} ({tf_type}) - requires manual review")

        return {
            "mapping_name": mapping_name,
            "status": "converted" if tf_converted == len(transformations) else
                      "partial" if tf_converted > 0 else "failed",
            "sql": sql,
            "transformations_used": len(transformations),
            "transformations_converted": tf_converted,
            "expressions_converted": converted_expressions,
            "expressions_total": total_expressions,
            "issues": issues,
            "expression_comparisons": expression_comparisons,
            "used_llm": False,
        }

    def _sync_llm_call(self, system: str, prompt: str) -> str:
        """Synchronous LLM call to run in a thread pool."""
        api_response = self.llm.client.messages.create(
            model=self.llm.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return api_response.content[0].text.strip()

    async def _llm_convert_mapping(
        self, mapping_name: str, group: dict,
        connector_graph: dict, parameters: list,
    ) -> Optional[str]:
        """Use LLM to convert a single mapping to BigQuery SQL."""
        try:
            summary = self._build_mapping_summary(mapping_name, group, connector_graph, parameters)

            prompt = (
                f"Convert this single Informatica mapping to BigQuery SQL.\n\n"
                f"**Mapping: {mapping_name}**\n"
                f"{group.get('description', '')}\n\n"
                f"{summary}\n\n"
                f"Generate ONLY the BigQuery SQL for this mapping.\n"
                f"Replace any $$parameter references with @param_name.\n"
                f"Convert ALL Informatica expressions to BigQuery SQL syntax.\n\n"
                f"Respond with valid JSON:\n"
                f'{{"sql": "-- Complete BigQuery SQL for mapping {mapping_name}"}}'
            )

            # Run sync Anthropic SDK call in thread pool to avoid blocking event loop
            text = await asyncio.wait_for(
                asyncio.to_thread(self._sync_llm_call, self.system_prompt, prompt),
                timeout=45,  # 45s per mapping — must fit within Railway's 120s total
            )
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [ln for ln in lines if not ln.strip().startswith("```")]
                text = "\n".join(lines)

            result = json.loads(text)
            return result.get("sql", "")
        except asyncio.TimeoutError:
            logger.warning("LLM mapping conversion timed out for %s", mapping_name)
            return None
        except Exception as exc:
            logger.warning("LLM mapping conversion failed for %s: %s", mapping_name, exc)
            return None

    def _build_mapping_summary(
        self, mapping_name: str, group: dict,
        connector_graph: dict, parameters: list,
    ) -> str:
        """Build a concise summary of a single mapping for LLM."""
        parts = []

        if group["sources"]:
            src_names = [s["name"] for s in group["sources"]]
            parts.append(f"Sources: {', '.join(src_names)}")
            for src in group["sources"]:
                if src["columns"]:
                    # No column cap — send ALL columns so LLM can generate complete schema
                    cols = [c["name"] for c in src["columns"]]
                    parts.append(f"  {src['name']} columns ({len(cols)}): {', '.join(cols)}")

        if group["targets"]:
            tgt_names = [t["name"] for t in group["targets"]]
            parts.append(f"Targets: {', '.join(tgt_names)}")
            for tgt in group["targets"]:
                if tgt["columns"]:
                    # No column cap — send ALL target columns for complete coverage
                    cols = [f"{c['name']} ({c.get('datatype', '')})" for c in tgt["columns"]]
                    parts.append(f"  {tgt['name']} columns ({len(cols)}): {', '.join(cols)}")

        parts.append(f"\nTransformations ({len(group['transformations'])}):")
        for tf in group["transformations"]:
            line = f"  - {tf['name']} (type: {tf['type']})"
            if tf.get("fields"):
                expr_fields = [f for f in tf["fields"] if f.get("expression")]
                if expr_fields:
                    # No expression cap — send ALL expressions for complex mappings
                    exprs = [f"{f['name']} = {f['expression']}" for f in expr_fields[:20]]
                    line += f"\n    Expressions ({len(expr_fields)}): {'; '.join(exprs)}"
                    if len(expr_fields) > 20:
                        line += f"\n    ... and {len(expr_fields) - 20} more expressions"
            if tf.get("properties"):
                # Include key properties (especially Group Filter Conditions for Routers)
                props = [f"{k}={v}" for k, v in list(tf["properties"].items())[:10]]
                line += f"\n    Properties: {'; '.join(props)}"
            parts.append(line)

        # Show relevant data flow from connector graph
        instance_edges = connector_graph.get("instance_edges", {})
        tf_names = {tf["name"] for tf in group["transformations"]}
        flow_parts = []
        for tf_name in tf_names:
            if tf_name in instance_edges:
                downstream = [d for d in instance_edges[tf_name] if d in tf_names or d in {t["name"] for t in group["targets"]}]
                if downstream:
                    flow_parts.append(f"  {tf_name} → {', '.join(downstream)}")
        if flow_parts:
            parts.append(f"\nData Flow:")
            parts.extend(flow_parts)

        if parameters:
            param_names = [p["name"] for p in parameters[:10]]
            parts.append(f"\nParameters: {', '.join(param_names)}")

        return "\n".join(parts)

    # ── Mapplet Inlining ──────────────────────────────────────────

    def _get_mapplet_by_name(self, parsed: dict, name: str) -> dict | None:
        """Find a mapplet definition by name."""
        for mplt in parsed.get("mapplets", []):
            if mplt["name"] == name:
                return mplt
        return None

    def _inline_mapplets(self, group: dict, parsed: dict) -> list:
        """Inline mapplet transformations into the mapping's transformation list.

        For each mapplet instance referenced in the mapping, find the mapplet
        definition and add its transformations (Expression, Lookup, Aggregator,
        etc.) to the mapping's pipeline with prefixed names.
        """
        transformations = list(group.get("transformations", []))
        mapplet_names = group.get("mapplet_instance_names", [])
        if not mapplet_names:
            # Also detect from instances list
            for inst in group.get("instances", []):
                if inst.get("transformation_type") == "Mapplet" or inst.get("type") == "MAPPLET":
                    mapplet_names.append(inst.get("transformation_name", ""))

        for mplt_name in mapplet_names:
            mplt = self._get_mapplet_by_name(parsed, mplt_name)
            if not mplt:
                continue
            for tf in mplt.get("transformations", []):
                # Skip Input/Output Transformation wrappers, inline the real logic
                if tf["type"] in ("Input Transformation", "Output Transformation"):
                    continue
                inlined = dict(tf)
                inlined["name"] = f"{mplt_name}__{tf['name']}"
                inlined["_from_mapplet"] = mplt_name
                transformations.append(inlined)

        return transformations

    # ── Column Lineage Tracking ──────────────────────────────────

    def _build_column_lineage(self, group: dict, connector_graph: dict) -> dict:
        """Trace column lineage from sources through transformations to targets.

        Returns:
            {
                target_name: {
                    target_col: {
                        "source": source_instance,
                        "source_col": source_field,
                        "transformations": [(tf_name, expression), ...],
                        "final_expr": "BigQuery expression",
                    }
                }
            }
        """
        field_map = connector_graph.get("field_map", {})
        lineage = {}

        for tgt in group.get("targets", []):
            tgt_name = tgt["name"]
            lineage[tgt_name] = {}
            for col in tgt.get("columns", []):
                col_name = col["name"]
                lineage[tgt_name][col_name] = {
                    "source": None,
                    "source_col": None,
                    "transformations": [],
                    "final_expr": col_name,
                    "resolved": False,
                }

        # Build reverse field map: (to_inst, to_field) -> (from_inst, from_field)
        reverse_field = {}
        for (fi, ff), (ti, tf_field) in field_map.items():
            reverse_field[(ti, tf_field)] = (fi, ff)

        # For each target column, trace back through connectors
        for tgt in group.get("targets", []):
            tgt_name = tgt["name"]
            for col in tgt.get("columns", []):
                col_name = col["name"]
                # Walk backwards from target
                current = (tgt_name, col_name)
                path = []
                visited = set()
                while current in reverse_field and current not in visited:
                    visited.add(current)
                    prev = reverse_field[current]
                    path.append(prev)
                    current = prev
                if path:
                    origin = path[-1]
                    lineage[tgt_name][col_name]["source"] = origin[0]
                    lineage[tgt_name][col_name]["source_col"] = origin[1]
                    lineage[tgt_name][col_name]["resolved"] = True

        return lineage

    def _resolve_target_columns(self, group: dict, connector_graph: dict,
                                 parameters: list) -> dict:
        """For each target, build the full SELECT column list with expressions.

        Returns: {target_name: [(col_name, sql_expression), ...]}
        """
        lineage = self._build_column_lineage(group, connector_graph)
        field_map = connector_graph.get("field_map", {})
        # Build transformation lookup by name
        tf_by_name = {tf["name"]: tf for tf in group.get("transformations", [])}

        result = {}
        for tgt in group.get("targets", []):
            tgt_name = tgt["name"]
            cols = []
            tgt_lineage = lineage.get(tgt_name, {})
            for col in tgt.get("columns", []):
                col_name = col["name"]
                col_info = tgt_lineage.get(col_name, {})
                if col_info.get("resolved") and col_info.get("source_col"):
                    cols.append((col_name, col_info["source_col"]))
                else:
                    # Try to find via field expressions in transformations
                    found = False
                    for tf in group.get("transformations", []):
                        for f in tf.get("fields", []):
                            if f["name"] == col_name and f.get("expression"):
                                expr = self._convert_expression(f["expression"], parameters)
                                cols.append((col_name, expr))
                                found = True
                                break
                        if found:
                            break
                    if not found:
                        cols.append((col_name, f"NULL /* TODO: resolve {col_name} */"))
            result[tgt_name] = cols
        return result

    # ── Lookup Condition Parser ──────────────────────────────────

    def _extract_lookup_condition(self, tf: dict, connector_graph: dict,
                                   prev_table: str) -> tuple:
        """Extract the actual lookup table and JOIN condition from a Lookup transformation.

        Returns: (lookup_table_name, join_condition_sql, lookup_output_fields)
        """
        # 1. Check for Lookup SQL Override
        lookup_sql_override = tf.get("properties", {}).get("Lookup Sql Override", "")

        # 2. Get lookup table from properties
        lookup_table = tf.get("properties", {}).get("Lookup table name", "")
        if not lookup_table:
            # Try to derive from transformation name (e.g., LKP_ALV_REF_EXUSOC -> ALV_REF_EXUSOC)
            name = tf.get("name", "")
            if name.startswith("LKP_"):
                lookup_table = name[4:]
            elif name.startswith("lkp_"):
                lookup_table = name[4:]

        # 3. Parse CONDITION attribute from the lookup
        condition = tf.get("properties", {}).get("Lookup condition", "")
        if not condition:
            # Build condition from connector graph: input ports map to lookup keys
            reverse_edges = connector_graph.get("reverse_edges", {})
            instance_fields_in = connector_graph.get("instance_fields_in", {})
            tf_name = tf["name"]

            # Find fields that are INPUT ports (these are the join keys)
            input_fields = []
            output_fields = []
            for field in tf.get("fields", []):
                port = field.get("porttype", "").upper()
                if "INPUT" in port and "OUTPUT" not in port:
                    input_fields.append(field["name"])
                elif "OUTPUT" in port or "LOOKUP" in port:
                    output_fields.append(field["name"])

            # Build join condition from input fields
            if input_fields:
                conditions = []
                for f in input_fields:
                    # The input field in the lookup matches a column from the main flow
                    conditions.append(f"a.{f} = lkp_{tf_name[-20:]}.{f}")
                condition = " AND ".join(conditions)

        if not condition:
            condition = "1=1 /* TODO: resolve lookup join condition */"

        # Get output fields from lookup
        output_fields = []
        for field in tf.get("fields", []):
            port = field.get("porttype", "").upper()
            if "OUTPUT" in port or "RETURN" in port:
                output_fields.append(field["name"])

        return lookup_table, condition, output_fields

    # ── Router Group Parser ──────────────────────────────────────

    def _extract_router_groups(self, tf: dict, parameters: list) -> list:
        """Extract router output groups with their filter conditions.

        Returns: [(group_name, condition_sql), ...]
        """
        groups = []

        # Method 1: From TABLEATTRIBUTE properties (Group Filter Condition)
        for prop_name, prop_val in tf.get("properties", {}).items():
            if "Group Filter" in prop_name and prop_val:
                # Extract group name from property name pattern
                # e.g., "Group Filter Condition/PROCESSED" -> "PROCESSED"
                parts = prop_name.split("/")
                group_name = parts[-1] if len(parts) > 1 else f"GROUP_{len(groups)}"
                converted = self._convert_expression(prop_val, parameters)
                groups.append((group_name, converted))

        # Method 2: From TRANSFORMFIELD GROUP attribute
        if not groups:
            seen_groups = {}
            for field in tf.get("fields", []):
                grp = field.get("group", "")
                if grp and grp != "INPUT" and grp not in seen_groups:
                    # Look for filter expression in properties
                    seen_groups[grp] = True

        # Method 3: Check for output groups in field definitions
        if not groups:
            group_names = set()
            for field in tf.get("fields", []):
                grp = field.get("group", "")
                if grp and grp != "INPUT" and grp != "OUTPUT":
                    group_names.add(grp)
            for gn in sorted(group_names):
                groups.append((gn, f"/* TODO: define condition for {gn} */"))

        return groups

    # ── Variable Port Resolution ─────────────────────────────────

    def _resolve_variable_ports(self, tf: dict, parameters: list) -> dict:
        """Resolve LOCAL VARIABLE ports in a transformation.

        LOCAL VARIABLE ports are intermediate calculations (e.g., v_EFFECTIVE_DT)
        that are evaluated before OUTPUT ports. Their expressions must be inlined
        into any OUTPUT expression that references them.

        Returns: {var_name: converted_bigquery_expression}
        """
        variables = {}
        for field in tf.get("fields", []):
            porttype = field.get("porttype", "").upper()
            if "LOCAL VARIABLE" in porttype or "VARIABLE" in porttype:
                name = field.get("name", "")
                expr = field.get("expression", "").strip()
                if name and expr:
                    # Convert the variable's own expression first
                    converted = self._convert_expression(expr, parameters)
                    variables[name] = converted
                elif name:
                    # Variable port with no expression — passthrough
                    variables[name] = name

        # Resolve inter-variable dependencies (variable referencing another variable)
        # Do up to 3 passes to handle chains like v_A -> v_B -> v_C
        for _ in range(3):
            changed = False
            for var_name, var_expr in list(variables.items()):
                for other_name, other_expr in variables.items():
                    if other_name != var_name and other_name in var_expr:
                        # Replace reference with the resolved expression
                        new_expr = re.sub(
                            r'\b' + re.escape(other_name) + r'\b',
                            f'({other_expr})',
                            var_expr
                        )
                        if new_expr != var_expr:
                            variables[var_name] = new_expr
                            changed = True
            if not changed:
                break

        return variables

    def _substitute_variables_in_expr(self, expr: str, variables: dict) -> str:
        """Replace variable port references in an expression with their resolved values."""
        result = expr
        for var_name, var_expr in variables.items():
            # Replace whole-word occurrences of the variable name
            result = re.sub(
                r'\b' + re.escape(var_name) + r'\b',
                f'({var_expr})',
                result
            )
        return result

    # ── Topological Sort ──────────────────────────────────────────

    def _topological_sort_transformations(
        self, transformations: list, connector_graph: dict
    ) -> list:
        """Sort transformations in data-flow order using Kahn's algorithm.

        Uses the connector graph's instance_edges to determine dependencies.
        Falls back to original order if cycle detected or graph is disconnected.
        Source Qualifiers are always placed first.
        """
        instance_edges = connector_graph.get("instance_edges", {})
        tf_names = {tf["name"] for tf in transformations}
        tf_by_name = {tf["name"]: tf for tf in transformations}

        # Separate source qualifiers (always first) from others
        source_quals = [tf for tf in transformations if tf["type"] == "Source Qualifier"]
        other_tfs = [tf for tf in transformations if tf["type"] != "Source Qualifier"]
        other_names = {tf["name"] for tf in other_tfs}

        if not other_tfs:
            return transformations

        # Build adjacency and in-degree for non-source-qualifier transformations
        adj = defaultdict(set)  # from -> set(to)
        in_degree = defaultdict(int)

        for from_inst, to_insts in instance_edges.items():
            for to_inst in to_insts:
                # Only consider edges between transformations in this mapping
                if from_inst in other_names and to_inst in other_names:
                    if to_inst not in adj[from_inst]:
                        adj[from_inst].add(to_inst)
                        in_degree[to_inst] += 1
                # Edges from source qualifier to a transformation
                elif from_inst in tf_names and to_inst in other_names:
                    # These inform in_degree but source quals are already placed first
                    pass

        # Initialize in_degree for all nodes (including those with 0 incoming)
        for name in other_names:
            if name not in in_degree:
                in_degree[name] = 0

        # Kahn's algorithm
        queue = deque([n for n in other_names if in_degree.get(n, 0) == 0])
        sorted_names = []

        while queue:
            node = queue.popleft()
            sorted_names.append(node)
            for neighbor in adj.get(node, set()):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If not all nodes were visited, there's a cycle — fall back to original order
        if len(sorted_names) != len(other_names):
            logger.warning(
                "Topological sort incomplete (%d/%d) — possible cycle. Using original order.",
                len(sorted_names), len(other_names)
            )
            return transformations

        # Rebuild the transformation list in topological order
        sorted_tfs = list(source_quals)
        for name in sorted_names:
            if name in tf_by_name:
                sorted_tfs.append(tf_by_name[name])

        # Append any transformations that weren't in the graph (safety net)
        sorted_set = {tf["name"] for tf in sorted_tfs}
        for tf in transformations:
            if tf["name"] not in sorted_set:
                sorted_tfs.append(tf)

        return sorted_tfs

    # ── Router-to-Target Mapping ──────────────────────────────────

    def _resolve_router_to_target_map(
        self, router_tf: dict, connector_graph: dict, targets: list
    ) -> dict:
        """Trace router output groups to their downstream target tables.

        Follows instance_edges from the Router through intermediate transformations
        until a Target instance is found.

        Returns: {target_table_name: router_group_table_name}
        """
        instance_edges = connector_graph.get("instance_edges", {})
        target_names = {t["name"].lower() for t in targets}
        router_name = router_tf["name"]

        # Get direct downstream instances of the router
        direct_downstream = instance_edges.get(router_name, set())

        # For each downstream path, trace to a target
        group_to_target = {}
        for downstream in direct_downstream:
            # BFS from this downstream node to find a target
            visited = set()
            queue = deque([downstream])
            found_target = None
            while queue and not found_target:
                current = queue.popleft()
                if current in visited:
                    continue
                visited.add(current)
                if current.lower() in target_names:
                    found_target = current
                    break
                # Follow edges further
                for next_inst in instance_edges.get(current, set()):
                    if next_inst not in visited:
                        queue.append(next_inst)

            if found_target:
                # Try to match downstream to a router group
                # Router groups in field attributes have group names
                for field in router_tf.get("fields", []):
                    grp = field.get("group", "")
                    if grp and grp != "INPUT":
                        # Check if this group connects to this downstream path
                        group_to_target[found_target.lower()] = grp.lower()

        return group_to_target

    # ── Rule-Based Per-Mapping SQL ───────────────────────────────

    def _rule_based_mapping_sql(
        self, mapping_name: str, group: dict,
        connector_graph: dict, parameters: list,
        naming: TableNamingConfig | None = None,
        session_overrides: dict | None = None,
    ) -> str:
        """Generate BigQuery SQL for a single mapping using rule-based conversion."""
        naming = naming or TableNamingConfig()
        # Inline mapplet transformations into the pipeline
        all_transformations = self._inline_mapplets(group, self._current_parsed or {})
        # Create a working copy of the group with inlined transformations
        group = dict(group)
        group["transformations"] = all_transformations

        # Apply topological sort to process transformations in data-flow order
        all_transformations = self._topological_sort_transformations(
            all_transformations, connector_graph
        )
        group["transformations"] = all_transformations

        lines = [
            f"-- ============================================================",
            f"-- BigQuery SQL for mapping: {mapping_name}",
            f"-- Sources: {', '.join(s['name'] for s in group['sources'])}",
            f"-- Targets: {', '.join(t['name'] for t in group['targets'])}",
            f"-- Transformations: {len(all_transformations)} (including inlined mapplets)",
            f"-- Processing order: topologically sorted by data flow",
            f"-- ============================================================",
            "",
        ]

        # Emit DECLARE statements for parameters with known values
        declares = self._generate_declare_statements(parameters)
        if declares:
            lines.append("-- Parameter declarations")
            lines.append(declares)
            lines.append("")

        # Emit Pre-SQL from session overrides
        for inst_name, ovr in (session_overrides or {}).items():
            pre_sql = ovr.get("Pre SQL", "").strip()
            if pre_sql:
                lines.append(f"-- Pre-SQL from session (instance: {inst_name})")
                lines.append(self._convert_expression(pre_sql, parameters))
                lines.append(";")
                lines.append("")

        # Build source extracts for ALL sources (not just first)
        for i, src in enumerate(group["sources"]):
            cols = [c["name"] for c in src["columns"]] if src["columns"] else ["*"]
            src_tbl = naming.format_table(naming.prefix_staging, src['name'], is_source=True)
            lines.append(f"-- Step {i + 1}: Extract from source ({src['name']})")
            lines.append(f"{naming.create_stmt()} {src_tbl} AS")
            lines.append("SELECT")
            lines.append("  " + ",\n  ".join(cols))
            lines.append(f"FROM {naming.format_table('', src['name'], is_source=True)}")
            lines.append(";")
            lines.append("")

        # Process transformations
        step = len(group["sources"]) + 1
        prev_table = f"{naming.prefix_staging}{group['sources'][0]['name'].lower()}" if group["sources"] else "source_table"

        # Track router group → target table mappings for multi-target routing
        router_group_tables = {}  # {target_name_lower: router_group_table_name}

        for tf in group["transformations"]:
            tf_type = tf["type"]

            if tf_type in ("Expression", "SQL Transformation"):
                lines.append(f"-- Step {step}: {tf['name']} ({tf_type})")
                table_name = f"transform_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}"
                lines.append(f"{naming.create_stmt()} {naming.format_table('', table_name)} AS")
                lines.append("SELECT")

                # Resolve LOCAL VARIABLE ports first
                var_ports = self._resolve_variable_ports(tf, parameters)
                if var_ports:
                    lines.append(f"  -- Variable ports resolved: {', '.join(var_ports.keys())}")

                expr_fields = []
                for field in tf.get("fields", []):
                    porttype = field.get("porttype", "").upper()
                    # Skip LOCAL VARIABLE ports — they are resolved inline
                    if "LOCAL VARIABLE" in porttype or "VARIABLE" in porttype:
                        continue
                    expr = field.get("expression", "")
                    name = field.get("name", "unknown")
                    if expr:
                        # Substitute variable port references before converting
                        if var_ports:
                            expr = self._substitute_variables_in_expr(expr, var_ports)
                        expr_bq = self._convert_expression(expr, parameters)
                        expr_fields.append(f"  {expr_bq} AS {name}")
                    else:
                        expr_fields.append(f"  {name}")
                lines.append(",\n".join(expr_fields) if expr_fields else "  *")
                lines.append(f"FROM {naming.format_table('', prev_table)}")
                lines.append(";")
                lines.append("")
                prev_table = table_name
                step += 1

            elif tf_type == "Filter":
                lines.append(f"-- Step {step}: {tf['name']} (Filter)")
                filter_cond = tf.get("properties", {}).get("Filter Condition", "1=1")
                filter_cond = self._convert_expression(filter_cond, parameters)
                table_name = f"filtered_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}"
                lines.append(f"{naming.create_stmt()} {naming.format_table('', table_name)} AS")
                lines.append(f"SELECT * FROM {naming.format_table('', prev_table)}")
                lines.append(f"WHERE {filter_cond};")
                lines.append("")
                prev_table = table_name
                step += 1

            elif tf_type == "Aggregator":
                lines.append(f"-- Step {step}: {tf['name']} (Aggregator → GROUP BY)")
                table_name = f"agg_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}"
                lines.append(f"{naming.create_stmt()} {naming.format_table('', table_name)} AS")
                group_fields = []
                agg_fields = []
                for field in tf.get("fields", []):
                    expr = field.get("expression", "").strip()
                    name = field.get("name", "")
                    port = field.get("porttype", "").upper()

                    if "OUTPUT" in port and expr:
                        # Output port with expression: this is an aggregate calculation
                        converted = self._convert_expression(expr, parameters)
                        agg_fields.append(f"  {converted} AS {name}")
                    elif "OUTPUT" in port and not expr:
                        # Output port without expression: likely a SUM/COUNT aggregate
                        # In Informatica, output-only ports on aggregators are implicitly aggregated
                        # Check if this is a pass-through group-by or an aggregate
                        if "INPUT" in port:
                            # INPUT/OUTPUT = group-by column
                            group_fields.append(name)
                        else:
                            # Pure OUTPUT = aggregate (default SUM)
                            agg_fields.append(f"  SUM({name}) AS {name}")
                    elif "INPUT" in port and "OUTPUT" in port:
                        # INPUT/OUTPUT = group-by column (pass-through)
                        group_fields.append(name)
                    elif "INPUT" in port:
                        # Input-only: this feeds aggregation, check if name matches an output
                        # It's a source column for aggregation, not directly selected
                        pass
                    elif name:
                        # Default: treat as group-by
                        group_fields.append(name)

                # If no agg_fields detected but we have group_fields, look for
                # output ports that should be summed (common in Informatica aggregators)
                if not agg_fields and group_fields:
                    output_only = [f for f in tf.get("fields", [])
                                   if "OUTPUT" in f.get("porttype", "").upper()
                                   and "INPUT" not in f.get("porttype", "").upper()
                                   and f.get("name")]
                    for f in output_only:
                        agg_fields.append(f"  SUM({f['name']}) AS {f['name']}")

                lines.append("SELECT")
                all_fields = [f"  {g}" for g in group_fields] + agg_fields
                lines.append(",\n".join(all_fields) if all_fields else "  *")
                lines.append(f"FROM {naming.format_table('', prev_table)}")
                if group_fields:
                    lines.append(f"GROUP BY {', '.join(group_fields)}")
                lines.append(";")
                lines.append("")
                prev_table = table_name
                step += 1

            elif tf_type == "Joiner":
                lines.append(f"-- Step {step}: {tf['name']} (Joiner → JOIN)")
                join_type = tf.get("properties", {}).get("Join Type", "Normal Join")
                bq_join = ("INNER JOIN" if "Normal" in join_type
                           else "LEFT OUTER JOIN" if "Master" in join_type
                           else "FULL OUTER JOIN")
                join_cond = tf.get("properties", {}).get("Join Condition", "a.id = b.id")
                join_cond = self._convert_expression(join_cond, parameters)

                # Use connector graph to find join sources
                reverse = connector_graph.get("reverse_edges", {})
                join_sources = list(reverse.get(tf["name"], set()))

                table_name = f"joined_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}"
                lines.append(f"{naming.create_stmt()} {naming.format_table('', table_name)} AS")
                if len(join_sources) >= 2:
                    lines.append(f"SELECT * FROM {naming.format_table('', join_sources[0].lower())}")
                    lines.append(f"{bq_join} {naming.format_table('', join_sources[1].lower())}")
                else:
                    lines.append(f"SELECT * FROM {naming.format_table('', prev_table)}")
                    lines.append(f"{bq_join} lookup_table")
                lines.append(f"ON {join_cond};")
                lines.append("")
                prev_table = table_name
                step += 1

            elif tf_type in ("Lookup", "Lookup Procedure"):
                lines.append(f"-- Step {step}: {tf['name']} (Lookup → LEFT JOIN)")
                lookup_table, join_condition, output_fields = self._extract_lookup_condition(
                    tf, connector_graph, prev_table
                )
                lookup_sql_override = tf.get("properties", {}).get("Lookup Sql Override", "")
                lkp_alias = f"lkp_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())[-30:]}"
                table_name = f"with_lkp_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}"

                # Build output column list from lookup
                lkp_select_cols = []
                for field in tf.get("fields", []):
                    port = field.get("porttype", "").upper()
                    if "OUTPUT" in port or "RETURN" in port:
                        lkp_select_cols.append(f"{lkp_alias}.{field['name']}")

                lines.append(f"{naming.create_stmt()} {naming.format_table('', table_name)} AS")
                if lkp_select_cols:
                    lines.append(f"SELECT a.*, {', '.join(lkp_select_cols)}")
                else:
                    lines.append(f"SELECT a.*, {lkp_alias}.*")
                lines.append(f"FROM {naming.format_table('', prev_table)} a")

                if lookup_sql_override:
                    converted_sql = self._convert_expression(lookup_sql_override, parameters)
                    lines.append(f"LEFT JOIN ({converted_sql}) {lkp_alias}")
                elif lookup_table:
                    lines.append(f"LEFT JOIN {naming.format_table('', lookup_table.lower())} {lkp_alias}")
                else:
                    lines.append(f"LEFT JOIN {naming.format_table('', tf['name'].lower())} {lkp_alias}")

                # Use the parsed condition
                if join_condition and "TODO" not in join_condition:
                    # Replace raw field refs with aliased refs
                    converted_cond = self._convert_expression(join_condition, parameters)
                    lines.append(f"ON {converted_cond}")
                else:
                    # Build from input port fields
                    input_fields = [f for f in tf.get("fields", [])
                                    if "INPUT" in f.get("porttype", "").upper()
                                    and "OUTPUT" not in f.get("porttype", "").upper()]
                    if input_fields:
                        conds = [f"a.{f['name']} = {lkp_alias}.{f['name']}" for f in input_fields[:5]]
                        lines.append(f"ON {' AND '.join(conds)}")
                    else:
                        lines.append(f"ON {join_condition}")
                lines.append(";")
                lines.append("")
                prev_table = table_name
                step += 1

            elif tf_type == "Router":
                lines.append(f"-- Step {step}: {tf['name']} (Router → CASE WHEN / filtered inserts)")
                router_groups = self._extract_router_groups(tf, parameters)

                # Resolve router group → target table mapping for multi-target routing
                rtr_target_map = self._resolve_router_to_target_map(
                    tf, connector_graph, group["targets"]
                )

                # Collect all generated group table names for target wiring
                group_table_names = {}  # {group_name_lower: table_name}

                if router_groups:
                    # Generate a CREATE TABLE per router output group
                    for grp_name, grp_condition in router_groups:
                        grp_table = f"routed_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}_{grp_name.lower()}"
                        group_table_names[grp_name.lower()] = grp_table
                        lines.append(f"-- Router group: {grp_name}")
                        lines.append(f"{naming.create_stmt()} {naming.format_table('', grp_table)} AS")
                        lines.append(f"SELECT *")
                        lines.append(f"FROM {naming.format_table('', prev_table)}")
                        if "TODO" not in grp_condition and grp_condition.strip():
                            lines.append(f"WHERE {grp_condition}")
                        else:
                            lines.append(f"WHERE {grp_condition}")
                        lines.append(";")
                        lines.append("")

                    # Default group: all records not matching any named group
                    if len(router_groups) > 0:
                        default_table = f"routed_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}_default"
                        group_table_names["default"] = default_table
                        all_conditions = [c for _, c in router_groups if "TODO" not in c]
                        if all_conditions:
                            negated = " AND ".join(f"NOT ({c})" for c in all_conditions)
                            lines.append(f"-- Router group: DEFAULT (unmatched records)")
                            lines.append(f"{naming.create_stmt()} {naming.format_table('', default_table)} AS")
                            lines.append(f"SELECT * FROM {naming.format_table('', prev_table)}")
                            lines.append(f"WHERE {negated};")
                            lines.append("")
                else:
                    # Fallback: extract groups from field GROUP attributes
                    group_names = set()
                    for field in tf.get("fields", []):
                        grp = field.get("group", "")
                        if grp and grp != "INPUT":
                            group_names.add(grp)
                    for gn in sorted(group_names):
                        grp_table = f"routed_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}_{gn.lower()}"
                        group_table_names[gn.lower()] = grp_table
                        lines.append(f"-- Router group: {gn}")
                        lines.append(f"{naming.create_stmt()} {naming.format_table('', grp_table)} AS")
                        lines.append(f"SELECT * FROM {naming.format_table('', prev_table)}")
                        lines.append(f"WHERE /* TODO: define filter for group {gn} */;")
                        lines.append("")

                    if not group_names:
                        lines.append(f"-- WARNING: No router groups found. Manual review required.")
                        lines.append("")

                # Wire router groups to target tables
                # If a target is mapped to a group, record its specific source table
                for tgt_name_lower, grp_name_lower in rtr_target_map.items():
                    if grp_name_lower in group_table_names:
                        router_group_tables[tgt_name_lower] = group_table_names[grp_name_lower]
                        lines.append(f"-- Router routing: target '{tgt_name_lower}' ← group '{grp_name_lower}'")

                # Also try to match by group name similarity to target name
                for tgt in group["targets"]:
                    tgt_lower = tgt["name"].lower()
                    if tgt_lower not in router_group_tables:
                        # Try matching group names to target names
                        for gn_lower, gt_name in group_table_names.items():
                            if gn_lower != "default" and (
                                gn_lower in tgt_lower or tgt_lower in gn_lower
                            ):
                                router_group_tables[tgt_lower] = gt_name
                                lines.append(f"-- Router routing (name match): target '{tgt_lower}' ← group '{gn_lower}'")
                                break

                if router_group_tables:
                    lines.append("")

                # prev_table stays the same (downstream picks specific group tables)
                step += 1

            elif tf_type == "Sequence Generator":
                lines.append(f"-- Step {step}: {tf['name']} (Sequence → ROW_NUMBER)")
                seq_col = "sequence_id"
                for field in tf.get("fields", []):
                    if "NEXTVAL" in field.get("name", "").upper() or "OUTPUT" in field.get("porttype", "").upper():
                        seq_col = field["name"]
                        break
                table_name = f"seq_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}"
                lines.append(f"{naming.create_stmt()} {naming.format_table('', table_name)} AS")
                lines.append(f"SELECT *, ROW_NUMBER() OVER (ORDER BY 1) AS {seq_col}")
                lines.append(f"FROM {naming.format_table('', prev_table)}")
                lines.append(";")
                lines.append("")
                prev_table = table_name
                step += 1

            elif tf_type == "Sorter":
                lines.append(f"-- Step {step}: {tf['name']} (Sorter → ORDER BY)")
                # Extract sort key columns from fields
                sort_keys = []
                for field in tf.get("fields", []):
                    name = field.get("name", "")
                    if name:
                        sort_keys.append(name)
                table_name = f"sorted_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}"
                lines.append(f"{naming.create_stmt()} {naming.format_table('', table_name)} AS")
                lines.append(f"SELECT * FROM {naming.format_table('', prev_table)}")
                if sort_keys:
                    lines.append(f"ORDER BY {', '.join(sort_keys[:10])}")
                lines.append(";")
                lines.append("")
                prev_table = table_name
                step += 1

            elif tf_type == "Rank":
                lines.append(f"-- Step {step}: {tf['name']} (Rank → RANK/ROW_NUMBER)")
                lines.append("-- RANK() OVER (PARTITION BY group_col ORDER BY rank_col)")
                lines.append("")
                step += 1

            elif tf_type == "Union":
                lines.append(f"-- Step {step}: {tf['name']} (Union → UNION ALL)")
                reverse = connector_graph.get("reverse_edges", {})
                union_sources = list(reverse.get(tf["name"], set()))
                if union_sources:
                    table_name = f"union_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}"
                    lines.append(f"{naming.create_stmt()} {naming.format_table('', table_name)} AS")
                    for idx, us in enumerate(union_sources):
                        if idx > 0:
                            lines.append("UNION ALL")
                        lines.append(f"SELECT * FROM {naming.format_table('', us.lower())}")
                    lines.append(";")
                    prev_table = table_name
                lines.append("")
                step += 1

            elif tf_type == "Update Strategy":
                lines.append(f"-- Step {step}: {tf['name']} (Update Strategy)")
                lines.append("-- DML operation determined by Update Strategy flags:")
                for field in tf.get("fields", []):
                    expr = field.get("expression", "")
                    if expr:
                        lines.append(f"--   {field['name']} = {expr}")
                lines.append("-- (Applied via MERGE in final target load)")
                lines.append("")
                step += 1

            elif tf_type == "Source Qualifier":
                # Source Qualifiers often contain custom SQL overrides
                sq_sql = tf.get("properties", {}).get("Sql Query", "")
                # Check session override for Sql Query
                if session_overrides and tf["name"] in session_overrides:
                    sq_override = session_overrides[tf["name"]].get("Sql Query", "")
                    if sq_override:
                        sq_sql = sq_override
                user_filter = tf.get("properties", {}).get("User Defined Join", "")
                source_filter = tf.get("properties", {}).get("Source Filter", "")
                if sq_sql or user_filter or source_filter:
                    lines.append(f"-- Step {step}: {tf['name']} (Source Qualifier with custom SQL)")
                    table_name = f"sq_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}"
                    lines.append(f"{naming.create_stmt()} {naming.format_table('', table_name)} AS")
                    if sq_sql:
                        converted_sq = self._convert_expression(sq_sql, parameters)
                        lines.append(converted_sq)
                    else:
                        lines.append(f"SELECT * FROM {naming.format_table('', prev_table)}")
                        if user_filter:
                            lines.append(f"/* User Defined Join: {self._convert_expression(user_filter, parameters)} */")
                        if source_filter:
                            lines.append(f"WHERE {self._convert_expression(source_filter, parameters)}")
                    lines.append(";")
                    lines.append("")
                    prev_table = table_name
                    step += 1

            elif tf_type in ("Input Transformation", "Output Transformation", "Mapplet"):
                # Mapplet boundary transformations — logic is inlined from mapplet definitions
                lines.append(f"-- Step {step}: {tf['name']} ({tf_type} — inlined from mapplet)")
                step += 1

        # Resolve full column lineage for targets
        target_columns = self._resolve_target_columns(group, connector_graph, parameters)

        # Detect Update Strategy for DML type
        has_update_strategy = any(
            tf["type"] == "Update Strategy" for tf in group["transformations"]
        )
        # Check session treat-as from properties (Data driven vs Insert)
        is_data_driven = has_update_strategy

        # Final target loads for ALL targets with full column coverage
        for tgt in group["targets"]:
            tgt_name = tgt["name"]
            tgt_cols_full = [c["name"] for c in tgt["columns"]] if tgt["columns"] else ["*"]
            resolved_cols = target_columns.get(tgt_name, [])

            # Multi-target router routing: use the specific router group table if mapped
            target_source_table = router_group_tables.get(
                tgt_name.lower(), prev_table
            )
            if target_source_table != prev_table:
                lines.append(f"-- Note: This target is fed by router group table '{target_source_table}'")

            lines.append(f"-- Final: Load into target ({tgt_name})")
            lines.append(f"-- Target has {len(tgt_cols_full)} columns")
            lines.append("")

            # Add idempotency: DELETE before INSERT for non-SCD loads
            if not is_data_driven:
                lines.append(f"-- Idempotency: Clean target before load")
                lines.append(f"-- Adjust the WHERE clause to match your load partition/date key")
                key_cols = [c["name"] for c in tgt.get("columns", [])
                            if c.get("key_type") in ("PRIMARY KEY", "PRIMARY")]
                if key_cols:
                    lines.append(f"DELETE FROM {naming.format_table('', tgt_name.lower())}")
                    lines.append(f"WHERE {key_cols[0]} IN (SELECT {key_cols[0]} FROM {naming.format_table('', target_source_table)});")
                else:
                    lines.append(f"-- TRUNCATE TABLE {naming.format_table('', tgt_name.lower())};  -- Uncomment for full refresh")
                lines.append("")

            if is_data_driven:
                # Use MERGE for data-driven (Update Strategy) sessions
                key_cols = [c["name"] for c in tgt.get("columns", [])
                            if c.get("key_type") in ("PRIMARY KEY", "PRIMARY")]
                if not key_cols and tgt_cols_full:
                    key_cols = [tgt_cols_full[0]]  # fallback to first column

                merge_key = " AND ".join(f"tgt.{k} = src.{k}" for k in key_cols)
                update_cols = [c for c in tgt_cols_full if c not in key_cols]

                lines.append(f"MERGE {naming.format_table('', tgt_name.lower())} AS tgt")
                lines.append(f"USING {naming.format_table('', target_source_table)} AS src")
                lines.append(f"ON {merge_key}")
                lines.append("WHEN MATCHED THEN UPDATE SET")
                if update_cols:
                    lines.append("  " + ",\n  ".join(f"tgt.{c} = src.{c}" for c in update_cols[:30]))
                    if len(update_cols) > 30:
                        lines.append(f"  /* ... and {len(update_cols) - 30} more columns */")
                else:
                    lines.append("  /* TODO: specify update columns */")
                lines.append("WHEN NOT MATCHED THEN INSERT (")
                lines.append("  " + ",\n  ".join(tgt_cols_full))
                lines.append(") VALUES (")
                if resolved_cols:
                    # Use resolved lineage for values
                    val_exprs = []
                    resolved_dict = {name: expr for name, expr in resolved_cols}
                    for col in tgt_cols_full:
                        val_exprs.append(f"  src.{resolved_dict.get(col, col)}"
                                          if col in resolved_dict
                                          else f"  src.{col}")
                    lines.append(",\n".join(val_exprs))
                else:
                    lines.append("  " + ",\n  ".join(f"src.{c}" for c in tgt_cols_full))
                lines.append(");")
            else:
                # Standard INSERT INTO with full column list
                lines.append(f"INSERT INTO {naming.format_table('', tgt_name.lower())} (")
                lines.append("  " + ",\n  ".join(tgt_cols_full))
                lines.append(")")
                lines.append("SELECT")
                if resolved_cols:
                    select_exprs = []
                    for col_name, col_expr in resolved_cols:
                        if col_expr != col_name:
                            select_exprs.append(f"  {col_expr} AS {col_name}")
                        else:
                            select_exprs.append(f"  {col_name}")
                    lines.append(",\n".join(select_exprs))
                else:
                    lines.append("  " + ",\n  ".join(tgt_cols_full))
                lines.append(f"FROM {naming.format_table('', target_source_table)}")
                lines.append(";")
            lines.append("")

        # Emit DDL comment blocks for target table schemas (data type mapping)
        for tgt in group["targets"]:
            tgt_name = tgt["name"]
            if tgt.get("columns"):
                lines.append(f"-- DDL: Target table schema for {tgt_name}")
                lines.append(f"-- CREATE TABLE IF NOT EXISTS {naming.format_table('', tgt_name.lower())} (")
                for col in tgt["columns"]:
                    bq_type = self._map_datatype_to_bigquery(
                        col.get("datatype", ""), col.get("precision", ""), col.get("scale", ""),
                        for_ddl=True,
                    )
                    lines.append(f"--   {col['name']} {bq_type},")
                lines.append(f"-- );")
                lines.append("")

        # Emit Post-SQL from session overrides
        for inst_name, ovr in (session_overrides or {}).items():
            post_sql = ovr.get("Post SQL", "").strip()
            if post_sql:
                lines.append(f"-- Post-SQL from session (instance: {inst_name})")
                lines.append(self._convert_expression(post_sql, parameters))
                lines.append(";")
                lines.append("")

        # Calculate per-mapping confidence score
        sql_output = "\n".join(lines)
        confidence = self._calculate_mapping_confidence(
            mapping_name, sql_output, group, connector_graph
        )

        # Embed confidence score as SQL comment header
        score_header = [
            f"-- CONFIDENCE: {confidence['score']}/100 ({confidence['tier']})",
            f"-- Dimensions: expr={confidence['dimensions']['expression_coverage']}% "
            f"col={confidence['dimensions']['column_coverage']}% "
            f"dml={confidence['dimensions']['dml_completeness']}% "
            f"join={confidence['dimensions']['join_accuracy']}% "
            f"tf={confidence['dimensions']['transformation_coverage']}%",
        ]
        if confidence["issues"]:
            score_header.append(f"-- Issues: {'; '.join(confidence['issues'][:5])}")
        score_header.append("")

        # Store confidence for collection by migrate()
        self._mapping_confidences.append(confidence)

        return "\n".join(score_header + lines)

    # ── Recursive Expression Parser (AST-based) ─────────────────

    def _tokenize_expression(self, expr: str) -> list:
        """Tokenize an Informatica expression into a list of tokens.

        Token types: IDENT, NUMBER, STRING, OP, LPAREN, RPAREN, COMMA, PARAM, LKP_REF
        """
        tokens = []
        i = 0
        n = len(expr)
        while i < n:
            ch = expr[i]

            # Whitespace
            if ch in (' ', '\t', '\n', '\r'):
                i += 1
                continue

            # String literal (single-quoted)
            if ch == "'":
                j = i + 1
                while j < n and expr[j] != "'":
                    if expr[j] == '\\':
                        j += 1  # skip escaped char
                    j += 1
                j = min(j + 1, n)
                tokens.append({"type": "STRING", "value": expr[i:j]})
                i = j
                continue

            # Lookup reference :LKP.NAME(field)
            if ch == ':' and i + 1 < n and expr[i + 1:i + 5].upper() == 'LKP.':
                j = i + 5
                while j < n and (expr[j].isalnum() or expr[j] == '_'):
                    j += 1
                lkp_name = expr[i + 5:j]
                tokens.append({"type": "LKP_REF", "value": lkp_name})
                i = j
                continue

            # Parameter $$NAME
            if ch == '$' and i + 1 < n and expr[i + 1] == '$':
                j = i + 2
                while j < n and (expr[j].isalnum() or expr[j] == '_'):
                    j += 1
                tokens.append({"type": "PARAM", "value": expr[i + 2:j]})
                i = j
                continue

            # Number
            if ch.isdigit() or (ch == '.' and i + 1 < n and expr[i + 1].isdigit()):
                j = i
                while j < n and (expr[j].isdigit() or expr[j] == '.'):
                    j += 1
                tokens.append({"type": "NUMBER", "value": expr[i:j]})
                i = j
                continue

            # Identifier or keyword
            if ch.isalpha() or ch == '_':
                j = i
                while j < n and (expr[j].isalnum() or expr[j] == '_'):
                    j += 1
                tokens.append({"type": "IDENT", "value": expr[i:j]})
                i = j
                continue

            # Parentheses / comma
            if ch == '(':
                tokens.append({"type": "LPAREN", "value": "("})
                i += 1
                continue
            if ch == ')':
                tokens.append({"type": "RPAREN", "value": ")"})
                i += 1
                continue
            if ch == ',':
                tokens.append({"type": "COMMA", "value": ","})
                i += 1
                continue

            # Multi-char operators
            if i + 1 < n:
                two = expr[i:i + 2]
                if two in ('||', '>=', '<=', '<>', '!=', ':='):
                    tokens.append({"type": "OP", "value": two})
                    i += 2
                    continue

            # Single-char operators
            if ch in ('+', '-', '*', '/', '=', '<', '>', '%', '!'):
                tokens.append({"type": "OP", "value": ch})
                i += 1
                continue

            # Anything else — pass through
            tokens.append({"type": "OTHER", "value": ch})
            i += 1

        return tokens

    def _parse_expression_ast(self, tokens: list, pos: int = 0) -> tuple:
        """Recursive descent parser for Informatica expressions.

        Returns: (ast_node, next_position)
        AST node types:
        - {"type": "call", "name": str, "args": [nodes]}
        - {"type": "literal", "value": str, "kind": "string"|"number"|"ident"|"param"}
        - {"type": "binop", "op": str, "left": node, "right": node}
        - {"type": "lkp_ref", "name": str, "args": [nodes]}
        """
        if pos >= len(tokens):
            return {"type": "literal", "value": "", "kind": "ident"}, pos

        return self._parse_or_expr(tokens, pos)

    def _parse_or_expr(self, tokens: list, pos: int) -> tuple:
        """Parse OR expressions (lowest precedence)."""
        left, pos = self._parse_and_expr(tokens, pos)
        while pos < len(tokens) and tokens[pos]["type"] == "IDENT" and tokens[pos]["value"].upper() == "OR":
            pos += 1
            right, pos = self._parse_and_expr(tokens, pos)
            left = {"type": "binop", "op": "OR", "left": left, "right": right}
        return left, pos

    def _parse_and_expr(self, tokens: list, pos: int) -> tuple:
        """Parse AND expressions."""
        left, pos = self._parse_comparison(tokens, pos)
        while pos < len(tokens) and tokens[pos]["type"] == "IDENT" and tokens[pos]["value"].upper() == "AND":
            pos += 1
            right, pos = self._parse_comparison(tokens, pos)
            left = {"type": "binop", "op": "AND", "left": left, "right": right}
        return left, pos

    def _parse_comparison(self, tokens: list, pos: int) -> tuple:
        """Parse comparison expressions (=, <>, !=, <, >, <=, >=)."""
        left, pos = self._parse_concat(tokens, pos)
        while pos < len(tokens) and tokens[pos]["type"] == "OP" and tokens[pos]["value"] in ('=', '<>', '!=', '<', '>', '<=', '>='):
            op = tokens[pos]["value"]
            pos += 1
            right, pos = self._parse_concat(tokens, pos)
            left = {"type": "binop", "op": op, "left": left, "right": right}
        return left, pos

    def _parse_concat(self, tokens: list, pos: int) -> tuple:
        """Parse string concatenation (||)."""
        left, pos = self._parse_additive(tokens, pos)
        parts = [left]
        while pos < len(tokens) and tokens[pos]["type"] == "OP" and tokens[pos]["value"] == "||":
            pos += 1
            right, pos = self._parse_additive(tokens, pos)
            parts.append(right)
        if len(parts) > 1:
            return {"type": "concat", "parts": parts}, pos
        return left, pos

    def _parse_additive(self, tokens: list, pos: int) -> tuple:
        """Parse addition and subtraction."""
        left, pos = self._parse_multiplicative(tokens, pos)
        while pos < len(tokens) and tokens[pos]["type"] == "OP" and tokens[pos]["value"] in ('+', '-'):
            op = tokens[pos]["value"]
            pos += 1
            right, pos = self._parse_multiplicative(tokens, pos)
            left = {"type": "binop", "op": op, "left": left, "right": right}
        return left, pos

    def _parse_multiplicative(self, tokens: list, pos: int) -> tuple:
        """Parse multiplication, division, modulo."""
        left, pos = self._parse_unary(tokens, pos)
        while pos < len(tokens) and tokens[pos]["type"] == "OP" and tokens[pos]["value"] in ('*', '/', '%'):
            op = tokens[pos]["value"]
            pos += 1
            right, pos = self._parse_unary(tokens, pos)
            left = {"type": "binop", "op": op, "left": left, "right": right}
        return left, pos

    def _parse_unary(self, tokens: list, pos: int) -> tuple:
        """Parse unary operators (NOT, -)."""
        if pos < len(tokens):
            if tokens[pos]["type"] == "IDENT" and tokens[pos]["value"].upper() == "NOT":
                pos += 1
                operand, pos = self._parse_primary(tokens, pos)
                return {"type": "unary", "op": "NOT", "operand": operand}, pos
            if tokens[pos]["type"] == "OP" and tokens[pos]["value"] == "-":
                pos += 1
                operand, pos = self._parse_primary(tokens, pos)
                return {"type": "unary", "op": "-", "operand": operand}, pos
        return self._parse_primary(tokens, pos)

    def _parse_primary(self, tokens: list, pos: int) -> tuple:
        """Parse primary expressions: literals, identifiers, function calls, parenthesized exprs."""
        if pos >= len(tokens):
            return {"type": "literal", "value": "", "kind": "ident"}, pos

        tok = tokens[pos]

        # Lookup reference :LKP.NAME(args)
        if tok["type"] == "LKP_REF":
            lkp_name = tok["value"]
            pos += 1
            args = []
            if pos < len(tokens) and tokens[pos]["type"] == "LPAREN":
                pos += 1  # skip (
                args, pos = self._parse_arg_list(tokens, pos)
                if pos < len(tokens) and tokens[pos]["type"] == "RPAREN":
                    pos += 1  # skip )
            return {"type": "lkp_ref", "name": lkp_name, "args": args}, pos

        # Parameter $$NAME
        if tok["type"] == "PARAM":
            pos += 1
            return {"type": "literal", "value": tok["value"], "kind": "param"}, pos

        # Number literal
        if tok["type"] == "NUMBER":
            pos += 1
            return {"type": "literal", "value": tok["value"], "kind": "number"}, pos

        # String literal
        if tok["type"] == "STRING":
            pos += 1
            return {"type": "literal", "value": tok["value"], "kind": "string"}, pos

        # Parenthesized expression
        if tok["type"] == "LPAREN":
            pos += 1  # skip (
            inner, pos = self._parse_or_expr(tokens, pos)
            if pos < len(tokens) and tokens[pos]["type"] == "RPAREN":
                pos += 1  # skip )
            return inner, pos

        # Identifier — could be a function call or plain identifier
        if tok["type"] == "IDENT":
            name = tok["value"]
            pos += 1
            # Check for function call: IDENT(
            if pos < len(tokens) and tokens[pos]["type"] == "LPAREN":
                pos += 1  # skip (
                args, pos = self._parse_arg_list(tokens, pos)
                if pos < len(tokens) and tokens[pos]["type"] == "RPAREN":
                    pos += 1  # skip )
                return {"type": "call", "name": name, "args": args}, pos
            return {"type": "literal", "value": name, "kind": "ident"}, pos

        # Anything else — pass through
        pos += 1
        return {"type": "literal", "value": tok["value"], "kind": "other"}, pos

    def _parse_arg_list(self, tokens: list, pos: int) -> tuple:
        """Parse a comma-separated argument list (inside function call parens)."""
        args = []
        if pos < len(tokens) and tokens[pos]["type"] == "RPAREN":
            return args, pos  # empty arg list

        arg, pos = self._parse_or_expr(tokens, pos)
        args.append(arg)

        while pos < len(tokens) and tokens[pos]["type"] == "COMMA":
            pos += 1  # skip comma
            arg, pos = self._parse_or_expr(tokens, pos)
            args.append(arg)

        return args, pos

    def _ast_to_bigquery(self, node: dict, parameters: list | None = None) -> str:
        """Convert an AST node to BigQuery SQL string.

        Handles Informatica-specific function conversions:
        - IIF → IF
        - DECODE → CASE
        - ISNULL → IS NULL
        - IS_NUMBER → SAFE_CAST ... IS NOT NULL
        - ADD_TO_DATE → DATE_ADD with INTERVAL
        - || → CONCAT
        - :LKP references → lookup placeholders
        """
        if not node:
            return ""

        node_type = node.get("type", "")

        if node_type == "literal":
            kind = node.get("kind", "")
            val = node.get("value", "")
            if kind == "param":
                return f"@{val}"
            return val

        if node_type == "unary":
            op = node["op"]
            operand = self._ast_to_bigquery(node["operand"], parameters)
            if op == "NOT":
                return f"NOT ({operand})"
            return f"{op}{operand}"

        if node_type == "binop":
            left = self._ast_to_bigquery(node["left"], parameters)
            right = self._ast_to_bigquery(node["right"], parameters)
            op = node["op"]
            return f"{left} {op} {right}"

        if node_type == "concat":
            parts = [self._ast_to_bigquery(p, parameters) for p in node["parts"]]
            return f"CONCAT({', '.join(parts)})"

        if node_type == "lkp_ref":
            lkp_name = node["name"]
            args = [self._ast_to_bigquery(a, parameters) for a in node.get("args", [])]
            if args:
                return f"/* :LKP.{lkp_name} */ {args[0]}"
            return f"/* :LKP.{lkp_name} */ NULL"

        if node_type == "call":
            name_upper = node["name"].upper()
            args = node.get("args", [])

            # IIF(condition, true_val, false_val) → IF(condition, true_val, false_val)
            if name_upper == "IIF" and len(args) >= 3:
                cond = self._ast_to_bigquery(args[0], parameters)
                true_val = self._ast_to_bigquery(args[1], parameters)
                false_val = self._ast_to_bigquery(args[2], parameters)
                return f"IF({cond}, {true_val}, {false_val})"

            # ISNULL(x) → (x IS NULL)
            if name_upper == "ISNULL" and len(args) == 1:
                inner = self._ast_to_bigquery(args[0], parameters)
                return f"({inner} IS NULL)"

            # IS_NUMBER(x) → (SAFE_CAST(x AS FLOAT64) IS NOT NULL)
            if name_upper == "IS_NUMBER" and len(args) == 1:
                inner = self._ast_to_bigquery(args[0], parameters)
                return f"(SAFE_CAST({inner} AS FLOAT64) IS NOT NULL)"

            # NVL(x, default) → COALESCE(x, default)
            if name_upper == "NVL" and len(args) >= 2:
                conv_args = [self._ast_to_bigquery(a, parameters) for a in args]
                return f"COALESCE({', '.join(conv_args)})"

            # DECODE handling
            if name_upper == "DECODE" and len(args) >= 3:
                first_arg = self._ast_to_bigquery(args[0], parameters)
                remaining = args[1:]

                # DECODE(TRUE, cond1, val1, ..., default) → CASE WHEN
                if first_arg.upper() == "TRUE":
                    case_parts = ["CASE"]
                    for i in range(0, len(remaining) - 1, 2):
                        cond = self._ast_to_bigquery(remaining[i], parameters)
                        val = self._ast_to_bigquery(remaining[i + 1], parameters) if i + 1 < len(remaining) else "NULL"
                        case_parts.append(f"WHEN {cond} THEN {val}")
                    if len(remaining) % 2 == 1:
                        default = self._ast_to_bigquery(remaining[-1], parameters)
                        case_parts.append(f"ELSE {default}")
                    case_parts.append("END")
                    return " ".join(case_parts)

                # DECODE(val, match1, result1, ..., default) → CASE val WHEN match1 THEN result1 ...
                case_parts = [f"CASE {first_arg}"]
                for i in range(0, len(remaining) - 1, 2):
                    match_val = self._ast_to_bigquery(remaining[i], parameters)
                    result_val = self._ast_to_bigquery(remaining[i + 1], parameters) if i + 1 < len(remaining) else "NULL"
                    case_parts.append(f"WHEN {match_val} THEN {result_val}")
                if len(remaining) % 2 == 1:
                    default = self._ast_to_bigquery(remaining[-1], parameters)
                    case_parts.append(f"ELSE {default}")
                case_parts.append("END")
                return " ".join(case_parts)

            # ADD_TO_DATE(date, 'unit', amount) → DATE_ADD(date, INTERVAL amount UNIT)
            if name_upper == "ADD_TO_DATE" and len(args) >= 3:
                date_val = self._ast_to_bigquery(args[0], parameters)
                unit_str = self._ast_to_bigquery(args[1], parameters).strip("'\"").upper()
                amount = self._ast_to_bigquery(args[2], parameters)
                unit_map = {'DD': 'DAY', 'MM': 'MONTH', 'YY': 'YEAR',
                            'HH': 'HOUR', 'MI': 'MINUTE', 'SS': 'SECOND'}
                bq_unit = unit_map.get(unit_str, 'DAY')
                return f"DATE_ADD({date_val}, INTERVAL {amount} {bq_unit})"

            # TO_DATE(str, fmt) → PARSE_DATE(fmt, str) or DATE(str)
            if name_upper == "TO_DATE" and len(args) >= 2:
                val = self._ast_to_bigquery(args[0], parameters)
                fmt = self._ast_to_bigquery(args[1], parameters)
                return f"PARSE_DATE({fmt}, {val})"
            if name_upper == "TO_DATE" and len(args) == 1:
                val = self._ast_to_bigquery(args[0], parameters)
                return f"DATE({val})"

            # TO_CHAR → CAST or FORMAT_DATE
            if name_upper == "TO_CHAR":
                conv_args = [self._ast_to_bigquery(a, parameters) for a in args]
                if len(conv_args) >= 2:
                    return f"FORMAT_DATE({conv_args[1]}, {conv_args[0]})"
                return f"CAST({conv_args[0]} AS STRING)" if conv_args else "CAST(NULL AS STRING)"

            # TO_INTEGER → CAST AS INT64
            if name_upper == "TO_INTEGER" and len(args) >= 1:
                val = self._ast_to_bigquery(args[0], parameters)
                return f"CAST({val} AS INT64)"

            # TO_DECIMAL → CAST AS NUMERIC
            if name_upper == "TO_DECIMAL" and len(args) >= 1:
                val = self._ast_to_bigquery(args[0], parameters)
                return f"CAST({val} AS NUMERIC)"

            # LTRIM/RTRIM with character arg → LTRIM(str, chars) (BigQuery compatible)
            if name_upper in ("LTRIM", "RTRIM", "TRIM"):
                conv_args = [self._ast_to_bigquery(a, parameters) for a in args]
                return f"{name_upper}({', '.join(conv_args)})"

            # SUBSTR → SUBSTR (BigQuery compatible)
            if name_upper == "SUBSTR":
                conv_args = [self._ast_to_bigquery(a, parameters) for a in args]
                return f"SUBSTR({', '.join(conv_args)})"

            # INSTR → STRPOS
            if name_upper == "INSTR":
                conv_args = [self._ast_to_bigquery(a, parameters) for a in args]
                return f"STRPOS({', '.join(conv_args)})"

            # SYSDATE → CURRENT_TIMESTAMP()
            if name_upper == "SYSDATE":
                return "CURRENT_TIMESTAMP()"

            # TRUNC(date) → DATE_TRUNC
            if name_upper == "TRUNC":
                conv_args = [self._ast_to_bigquery(a, parameters) for a in args]
                if len(conv_args) >= 2:
                    return f"DATE_TRUNC({conv_args[0]}, {conv_args[1].strip(chr(39))})"
                return f"DATE_TRUNC({conv_args[0]}, DAY)" if conv_args else "DATE_TRUNC(CURRENT_DATE(), DAY)"

            # LPAD/RPAD → LPAD/RPAD (BigQuery compatible)
            if name_upper in ("LPAD", "RPAD"):
                conv_args = [self._ast_to_bigquery(a, parameters) for a in args]
                return f"{name_upper}({', '.join(conv_args)})"

            # REG_REPLACE → REGEXP_REPLACE
            if name_upper == "REG_REPLACE":
                conv_args = [self._ast_to_bigquery(a, parameters) for a in args]
                return f"REGEXP_REPLACE({', '.join(conv_args)})"

            # REG_MATCH → REGEXP_CONTAINS
            if name_upper == "REG_MATCH":
                conv_args = [self._ast_to_bigquery(a, parameters) for a in args]
                return f"REGEXP_CONTAINS({', '.join(conv_args)})"

            # REPLACECHR / REPLACESTR → REPLACE
            if name_upper in ("REPLACECHR", "REPLACESTR") and len(args) >= 3:
                conv_args = [self._ast_to_bigquery(a, parameters) for a in args]
                # REPLACECHR(option, str, old, new) → REPLACE(str, old, new)
                if len(conv_args) >= 4:
                    return f"REPLACE({conv_args[1]}, {conv_args[2]}, {conv_args[3]})"
                return f"REPLACE({', '.join(conv_args)})"

            # IN(value, list) → value IN (list)
            if name_upper == "IN" and len(args) >= 2:
                field = self._ast_to_bigquery(args[0], parameters)
                values = [self._ast_to_bigquery(a, parameters) for a in args[1:]]
                return f"{field} IN ({', '.join(values)})"

            # ABORT → ERROR (BigQuery)
            if name_upper == "ABORT":
                conv_args = [self._ast_to_bigquery(a, parameters) for a in args]
                return f"ERROR({', '.join(conv_args)})" if conv_args else "ERROR('Abort triggered')"

            # ZEROIFNULL(x) → COALESCE(x, 0)
            if name_upper == "ZEROIFNULL" and len(args) >= 1:
                val = self._ast_to_bigquery(args[0], parameters)
                return f"COALESCE({val}, 0)"

            # Default: pass through as function call with converted arguments
            conv_args = [self._ast_to_bigquery(a, parameters) for a in args]
            func_name = node["name"]  # preserve original casing
            # Apply common function renames
            func_renames = {
                "LENGTH": "LENGTH", "UPPER": "UPPER", "LOWER": "LOWER",
                "ABS": "ABS", "ROUND": "ROUND", "POWER": "POWER",
                "MOD": "MOD", "CEIL": "CEIL", "FLOOR": "FLOOR",
                "CONCAT": "CONCAT", "REVERSE": "REVERSE",
            }
            bq_name = func_renames.get(name_upper, func_name)
            return f"{bq_name}({', '.join(conv_args)})"

        # Fallback
        return str(node.get("value", ""))

    # ── Expression Conversion ────────────────────────────────────

    def _convert_expression(self, expr: str, parameters: list | None = None) -> str:
        """Convert Informatica expression syntax to BigQuery SQL.

        Strategy: Try AST-based recursive descent parser first (handles nested
        IIF, DECODE, ISNULL etc. correctly). Falls back to regex-based conversion
        if the AST parser encounters any error.
        """
        if expr in _expression_cache:
            return _expression_cache[expr]

        # Try AST-based conversion first (handles nesting correctly)
        try:
            tokens = self._tokenize_expression(expr)
            if tokens:
                ast_node, _ = self._parse_expression_ast(tokens)
                converted = self._ast_to_bigquery(ast_node, parameters)
                if converted and converted.strip():
                    _expression_cache[expr] = converted
                    return converted
        except Exception:
            pass  # Fall through to regex-based conversion

        converted = expr

        # Apply all pre-compiled expression conversions (avoids re.compile per call)
        for compiled_re, replacement in _COMPILED_CONVERSIONS:
            converted = compiled_re.sub(replacement, converted)

        # Replace $$parameters with @param_name
        converted = _PARAM_RE.sub(r'@\1', converted)

        # Post-process: ISNULL(x) → (x IS NULL)
        # _ISNULL_BQ(x) was placed by the regex; now fix it
        isnull_re = re.compile(r'_ISNULL_BQ\(([^)]+)\)')
        converted = isnull_re.sub(r'(\1 IS NULL)', converted)

        # Post-process: IS_NUMBER(x) → (SAFE_CAST(x AS FLOAT64) IS NOT NULL)
        is_number_re = re.compile(r'_IS_NUMBER_BQ\(([^)]+)\)')
        converted = is_number_re.sub(r'(SAFE_CAST(\1 AS FLOAT64) IS NOT NULL)', converted)

        # Post-process: Informatica || (string concat) → CONCAT()
        # Only if it looks like string concatenation (not SQL OR)
        if '||' in converted and 'OR' not in converted.upper():
            # Simple case: a || b → CONCAT(a, b)
            parts = [p.strip() for p in converted.split('||')]
            if len(parts) > 1 and not any(kw in converted.upper() for kw in ['SELECT', 'WHERE', 'AND']):
                converted = f"CONCAT({', '.join(parts)})"

        # Post-process: Informatica IN(value, list) → value IN (list)
        in_re = re.compile(r'\bIN\s*\(([^,]+),\s*(.+?)\)', re.IGNORECASE)
        match = in_re.search(converted)
        if match:
            # Only transform if it looks like Informatica IN(field, val1, val2...)
            field = match.group(1).strip()
            values = match.group(2).strip()
            if "'" in values or "," in values:
                converted = in_re.sub(f'{field} IN ({values})', converted)

        # Post-process: ADD_TO_DATE handling
        # DATE_ADD(date, 'DD', n) → DATE_ADD(date, INTERVAL n DAY)
        add_date_re = re.compile(
            r"DATE_ADD\(([^,]+),\s*'(DD|MM|YY|HH|MI|SS)'\s*,\s*([^)]+)\)",
            re.IGNORECASE
        )
        def _fix_date_add(m):
            date_val = m.group(1)
            unit_map = {'DD': 'DAY', 'MM': 'MONTH', 'YY': 'YEAR', 'HH': 'HOUR', 'MI': 'MINUTE', 'SS': 'SECOND'}
            unit = unit_map.get(m.group(2).upper(), 'DAY')
            amount = m.group(3)
            return f"DATE_ADD({date_val}, INTERVAL {amount} {unit})"
        converted = add_date_re.sub(_fix_date_add, converted)

        # Post-process: DECODE(TRUE, cond1, val1, cond2, val2, default) → CASE WHEN
        if converted.strip().startswith("CASE ") and "TRUE" in converted:
            # Try to convert CASE TRUE, cond, val pattern to CASE WHEN
            decode_re = re.compile(
                r'CASE\s+TRUE\s*,\s*(.+)',
                re.IGNORECASE | re.DOTALL
            )
            dm = decode_re.match(converted.strip())
            if dm:
                body = dm.group(1)
                # Split by commas (respecting parentheses)
                parts = self._split_respecting_parens(body)
                if len(parts) >= 2:
                    case_parts = ["CASE"]
                    for i in range(0, len(parts) - 1, 2):
                        cond = parts[i].strip()
                        val = parts[i + 1].strip() if i + 1 < len(parts) else "NULL"
                        case_parts.append(f"  WHEN {cond} THEN {val}")
                    if len(parts) % 2 == 1:
                        case_parts.append(f"  ELSE {parts[-1].strip()}")
                    case_parts.append("END")
                    converted = "\n".join(case_parts)

        _expression_cache[expr] = converted
        return converted

    def _split_respecting_parens(self, s: str) -> list:
        """Split a string by commas, respecting parentheses nesting."""
        parts = []
        depth = 0
        current = []
        for ch in s:
            if ch == '(':
                depth += 1
                current.append(ch)
            elif ch == ')':
                depth -= 1
                if depth < 0:
                    break  # End of outer expression
                current.append(ch)
            elif ch == ',' and depth == 0:
                parts.append(''.join(current))
                current = []
            else:
                current.append(ch)
        if current:
            parts.append(''.join(current))
        return parts

    def _validate_sql(self, sql: str, mapping_name: str,
                       target_cols: list | None = None) -> list:
        """Validate generated SQL for common issues.

        Returns list of validation warnings.
        """
        warnings = []

        if not sql or len(sql.strip()) < 20:
            warnings.append(f"[{mapping_name}] Empty or near-empty SQL generated")
            return warnings

        sql_upper = sql.upper()

        # Check for DML presence
        has_dml = any(kw in sql_upper for kw in ['INSERT INTO', 'MERGE', 'DELETE FROM', 'UPDATE'])
        if not has_dml:
            warnings.append(f"[{mapping_name}] Missing DML operation (INSERT/MERGE/DELETE)")

        # Check for balanced parentheses
        open_count = sql.count('(')
        close_count = sql.count(')')
        if open_count != close_count:
            warnings.append(f"[{mapping_name}] Unbalanced parentheses: {open_count} open, {close_count} close")

        # Check for placeholder patterns that indicate incomplete conversion
        if 'a.key = b.key' in sql:
            warnings.append(f"[{mapping_name}] Contains placeholder join condition 'a.key = b.key'")
        if 'lookup_table' in sql.lower() and 'project.dataset.lookup_table' in sql.lower():
            warnings.append(f"[{mapping_name}] Contains unresolved 'lookup_table' reference")

        # Check for TODO markers
        todo_count = sql.upper().count('TODO')
        if todo_count > 0:
            warnings.append(f"[{mapping_name}] Contains {todo_count} TODO marker(s) requiring manual attention")

        # Check target column coverage if provided
        if target_cols:
            for col in target_cols:
                if col.lower() not in sql.lower():
                    warnings.append(f"[{mapping_name}] Target column '{col}' not found in SQL")
                    break  # Only report first missing to avoid spam

        return warnings

    # ── Per-Mapping Confidence Score ──────────────────────────────

    def _calculate_mapping_confidence(
        self, mapping_name: str, sql: str,
        group: dict, connector_graph: dict,
    ) -> dict:
        """Calculate a per-mapping confidence score on 6 dimensions.

        Returns:
            {
                "mapping_name": str,
                "score": 0-100,
                "tier": "HIGH" | "MEDIUM" | "LOW",
                "dimensions": {
                    "expression_coverage": 0-100,
                    "column_coverage": 0-100,
                    "dml_completeness": 0-100,
                    "join_accuracy": 0-100,
                    "transformation_coverage": 0-100,
                },
                "issues": [str, ...]
            }
        """
        issues = []
        sql_upper = sql.upper() if sql else ""
        sql_lower = sql.lower() if sql else ""

        # 1. Expression coverage (25%): % of expressions converted without TODO/placeholder
        total_exprs = 0
        clean_exprs = 0
        for tf in group.get("transformations", []):
            for field in tf.get("fields", []):
                expr = field.get("expression", "").strip()
                if expr:
                    total_exprs += 1
                    if "TODO" not in expr.upper() and "PLACEHOLDER" not in expr.upper():
                        clean_exprs += 1
        expression_coverage = round((clean_exprs / total_exprs) * 100) if total_exprs > 0 else 100

        # Also check output SQL for TODOs
        todo_count = sql_upper.count("TODO")
        if todo_count > 0:
            expression_coverage = max(0, expression_coverage - (todo_count * 5))
            issues.append(f"{todo_count} TODO marker(s) in generated SQL")

        # 2. Column coverage (25%): % of target columns present in final INSERT/MERGE
        total_target_cols = 0
        found_target_cols = 0
        for tgt in group.get("targets", []):
            for col in tgt.get("columns", []):
                total_target_cols += 1
                if col["name"].lower() in sql_lower:
                    found_target_cols += 1
        column_coverage = round((found_target_cols / total_target_cols) * 100) if total_target_cols > 0 else 100
        if total_target_cols > 0 and found_target_cols < total_target_cols:
            issues.append(f"{total_target_cols - found_target_cols} target column(s) not found in SQL")

        # 3. DML completeness (20%): Has INSERT/MERGE + has CREATE TABLE steps
        has_dml = any(kw in sql_upper for kw in ['INSERT INTO', 'MERGE'])
        has_create = 'CREATE OR REPLACE TABLE' in sql_upper or 'CREATE TABLE' in sql_upper
        dml_score = 0
        if has_dml:
            dml_score += 60
        else:
            issues.append("Missing DML operation (INSERT INTO / MERGE)")
        if has_create:
            dml_score += 40
        else:
            issues.append("Missing CREATE TABLE statements for transformation steps")
        dml_completeness = min(dml_score, 100)

        # 4. Join accuracy (15%): No placeholder joins, all lookups resolved
        join_accuracy = 100
        if 'a.key = b.key' in sql_lower:
            join_accuracy -= 40
            issues.append("Contains placeholder join condition 'a.key = b.key'")
        if 'lookup_table' in sql_lower:
            join_accuracy -= 30
            issues.append("Contains unresolved 'lookup_table' reference")
        # Count lookups that produced proper ON clauses
        lookup_count = sum(1 for tf in group.get("transformations", [])
                          if tf["type"] in ("Lookup", "Lookup Procedure"))
        on_clause_count = sql_upper.count(" ON ")
        if lookup_count > 0 and on_clause_count < lookup_count:
            missing = lookup_count - on_clause_count
            join_accuracy -= missing * 10
            issues.append(f"{missing} lookup(s) may have unresolved join conditions")
        join_accuracy = max(0, join_accuracy)

        # 5. Transformation coverage (15%): % of transformations that produced SQL output
        total_tfs = len(group.get("transformations", []))
        # Count transformations that appear as step comments in the SQL
        covered_tfs = 0
        for tf in group.get("transformations", []):
            tf_safe = re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())
            if tf_safe in sql_lower or tf["name"].lower() in sql_lower:
                covered_tfs += 1
        transformation_coverage = round((covered_tfs / total_tfs) * 100) if total_tfs > 0 else 100
        if total_tfs > 0 and covered_tfs < total_tfs:
            issues.append(f"{total_tfs - covered_tfs} transformation(s) may not have generated SQL")

        # Weighted overall score
        score = round(
            expression_coverage * 0.25 +
            column_coverage * 0.25 +
            dml_completeness * 0.20 +
            join_accuracy * 0.15 +
            transformation_coverage * 0.15
        )
        score = min(max(score, 0), 100)

        # Tier classification
        if score >= 80:
            tier = "HIGH"
        elif score >= 50:
            tier = "MEDIUM"
        else:
            tier = "LOW"

        return {
            "mapping_name": mapping_name,
            "score": score,
            "tier": tier,
            "dimensions": {
                "expression_coverage": expression_coverage,
                "column_coverage": column_coverage,
                "dml_completeness": dml_completeness,
                "join_accuracy": join_accuracy,
                "transformation_coverage": transformation_coverage,
            },
            "issues": issues,
        }

    def _build_confidence_summary(self) -> dict:
        """Build a summary of all per-mapping confidence scores.

        Returns:
            {
                "total_mappings": int,
                "average_score": float,
                "tier_distribution": {"HIGH": int, "MEDIUM": int, "LOW": int},
                "top_issues": [str, ...],
                "lowest_scoring": [{"name": str, "score": int, "tier": str}, ...]
            }
        """
        scores = self._mapping_confidences if hasattr(self, '_mapping_confidences') else []
        if not scores:
            return {
                "total_mappings": 0,
                "average_score": 0,
                "tier_distribution": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
                "top_issues": [],
                "lowest_scoring": [],
            }

        avg = round(sum(s["score"] for s in scores) / len(scores), 1)
        tiers = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for s in scores:
            tiers[s["tier"]] = tiers.get(s["tier"], 0) + 1

        # Collect most common issues
        issue_counts = defaultdict(int)
        for s in scores:
            for issue in s.get("issues", []):
                # Normalize issue text for counting
                normalized = re.sub(r'\d+', 'N', issue)
                issue_counts[normalized] += 1
        top_issues = sorted(issue_counts.items(), key=lambda x: -x[1])[:10]

        # Find lowest scoring mappings
        sorted_scores = sorted(scores, key=lambda x: x["score"])
        lowest = [
            {"name": s["mapping_name"], "score": s["score"], "tier": s["tier"]}
            for s in sorted_scores[:10]
        ]

        return {
            "total_mappings": len(scores),
            "average_score": avg,
            "tier_distribution": tiers,
            "top_issues": [f"{issue} (x{count})" for issue, count in top_issues],
            "lowest_scoring": lowest,
        }

    # ── Airflow DAG Generation ───────────────────────────────────

    def _build_workflow_dependency_graph(self, parsed: dict) -> dict:
        """Build task dependency graph from WORKFLOWLINK and WORKLET structures.

        Returns: {
            "edges": {from_task: [to_task, ...]},
            "task_types": {task_name: task_type},
            "worklet_tasks": {worklet_name: {task_name: type}},
            "parallel_groups": [[task1, task2], ...],  # tasks that can run in parallel
        }
        """
        edges = defaultdict(list)
        task_types = {}
        worklet_tasks = defaultdict(dict)

        # Parse top-level workflow links
        for link in parsed.get("workflow_links", []):
            from_t = link["from_task"]
            to_t = link["to_task"]
            edges[from_t].append(to_t)

        # Parse task instance types
        for ti in parsed.get("task_instances", []):
            task_types[ti["name"]] = ti["type"]

        # Parse worklet internal structures
        for wklt in parsed.get("worklets", []):
            wklt_name = wklt["name"]
            for task in wklt.get("tasks", []):
                worklet_tasks[wklt_name][task["name"]] = task["type"]
            for link in wklt.get("links", []):
                edges[f"{wklt_name}.{link['from_task']}"].append(f"{wklt_name}.{link['to_task']}")

        # Detect parallel groups: tasks that share the same predecessor
        parallel_groups = []
        for from_task, to_tasks in edges.items():
            if len(to_tasks) > 1:
                parallel_groups.append(to_tasks)

        # Parse command tasks
        for cmd in parsed.get("command_tasks", []):
            task_types[cmd["name"]] = "COMMAND"

        return {
            "edges": dict(edges),
            "task_types": dict(task_types),
            "worklet_tasks": dict(worklet_tasks),
            "parallel_groups": parallel_groups,
        }

    # ── Reconciliation Task Generation ──────────────────────────

    def _generate_reconciliation_task(
        self, mapping_name: str, source_tables: list[str],
        target_tables: list[str], task_id: str,
        threshold_pct: float = 5.0,
    ) -> list[str]:
        """Generate PythonOperator code for source→target row count reconciliation.

        Runs COUNT(*) on source vs target and fails if delta exceeds threshold%.
        """
        recon_id = f"recon_{task_id}"
        src_tables_str = ", ".join(f'"`{{{{ var.value.gcp_project_id }}}}.{{{{ var.value.bq_dataset }}}}.{s.lower()}`"' for s in source_tables[:3])
        tgt_tables_str = ", ".join(f'"`{{{{ var.value.gcp_project_id }}}}.{{{{ var.value.bq_dataset }}}}.{t.lower()}`"' for t in target_tables[:3])

        lines = [
            f"    # Reconciliation: {mapping_name}",
            f"    def _reconcile_{task_id}(**kwargs):",
            f'        """Row-count reconciliation for {mapping_name}."""',
            "        from google.cloud import bigquery",
            "        client = bigquery.Client()",
            f"        source_tables = [{src_tables_str}]",
            f"        target_tables = [{tgt_tables_str}]",
            "        for src, tgt in zip(source_tables, target_tables):",
            '            src_count = list(client.query(f"SELECT COUNT(*) c FROM {src}").result())[0].c',
            '            tgt_count = list(client.query(f"SELECT COUNT(*) c FROM {tgt}").result())[0].c',
            "            if src_count == 0:",
            "                continue",
            f"            delta_pct = abs(src_count - tgt_count) / src_count * 100",
            f'            if delta_pct > {threshold_pct}:',
            '                raise ValueError(',
            "                    f\"Row count mismatch: {src}={src_count} vs {tgt}={tgt_count} \"",
            f'                    f"(delta={{delta_pct:.1f}}% > {threshold_pct}%)"',
            "                )",
            '            kwargs["ti"].log.info(f"Reconciliation OK: {src}={src_count}, {tgt}={tgt_count}")',
            "",
            f"    {recon_id} = PythonOperator(",
            f'        task_id="{recon_id}",',
            f"        python_callable=_reconcile_{task_id},",
            "    )",
            "",
        ]
        return lines

    # ── Event Wait Sensor Generation ─────────────────────────────

    def _generate_sensor_task(
        self, ew_task: dict, naming: TableNamingConfig | None = None,
    ) -> list[str]:
        """Generate GCSObjectExistenceSensor or ExternalTaskSensor for Event Wait tasks."""
        name = ew_task.get("name", "event_wait")
        task_id = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())
        filewatch = ew_task.get("filewatch_name", "")
        is_workflow_event = "wkfl_" in name.lower() or ew_task.get("user_defined_event", False)

        lines = [f"    # Event Wait: {name}"]

        if is_workflow_event:
            # Map to ExternalTaskSensor for cross-workflow dependencies
            ext_dag = re.sub(r'[^a-zA-Z0-9_]', '_', filewatch.lower()) if filewatch else task_id
            lines.extend([
                f"    {task_id} = ExternalTaskSensor(",
                f'        task_id="{task_id}",',
                f'        external_dag_id="{ext_dag}",',
                '        external_task_id="end",',
                "        mode=\"reschedule\",",
                "        timeout=7200,",
                "        poke_interval=60,",
                "    )",
            ])
        else:
            # File-based: GCSObjectExistenceSensor
            # Convert $PMRootDir/... or $INFA_HOME/... → GCS path
            gcs_path = filewatch
            for var_prefix in ("$PMRootDir", "$INFA_HOME", "$PMSourceFileDir", "$PMTargetFileDir"):
                gcs_path = gcs_path.replace(var_prefix, '{{ var.value.gcs_root }}')
            # Remove Windows-style backslashes
            gcs_path = gcs_path.replace("\\", "/")
            # Split bucket and object
            bucket_var = "{{ var.value.gcs_bucket }}"
            lines.extend([
                f"    {task_id} = GCSObjectExistenceSensor(",
                f'        task_id="{task_id}",',
                f'        bucket_name="{bucket_var}",',
                f'        object="{gcs_path}",',
                "        mode=\"reschedule\",",
                "        timeout=7200,",
                "        poke_interval=120,",
                "    )",
            ])

        lines.append("")
        return lines

    # ── Decision Branch Operator Generation ──────────────────────

    def _generate_branch_operator(
        self, dec_task: dict, downstream_tasks: dict[str, str],
        parameters: list,
    ) -> list[str]:
        """Generate BranchPythonOperator for Decision tasks.

        ``downstream_tasks`` maps condition label → downstream task_id.
        """
        name = dec_task.get("name", "decision")
        task_id = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())
        conditions = dec_task.get("conditions", [])

        lines = [
            f"    # Decision: {name}",
            f"    def _decide_{task_id}(**kwargs):",
            f'        """Branching decision for {name}."""',
        ]

        # Convert conditions to Python branching logic
        for i, cond in enumerate(conditions):
            cond_expr = cond.get("condition", "")
            cond_label = cond.get("name", f"condition_{i}")
            # Convert Informatica condition syntax to Python
            py_cond = self._convert_expression(cond_expr, parameters)
            # Convert SQL-ish operators to Python
            py_cond = re.sub(r'\bAND\b', 'and', py_cond, flags=re.IGNORECASE)
            py_cond = re.sub(r'\bOR\b', 'or', py_cond, flags=re.IGNORECASE)
            py_cond = re.sub(r'\bNOT\b', 'not', py_cond, flags=re.IGNORECASE)

            # Find matching downstream task
            downstream_id = downstream_tasks.get(cond_label, "end")
            if i == 0:
                lines.append(f"        if {py_cond}:")
            else:
                lines.append(f"        elif {py_cond}:")
            lines.append(f'            return "{downstream_id}"')

        # Default fallback
        default_target = list(downstream_tasks.values())[-1] if downstream_tasks else "end"
        if not conditions:
            lines.append(f'        return "{default_target}"')
        else:
            lines.append(f'        return "{default_target}"  # default branch')

        lines.extend([
            "",
            f"    {task_id} = BranchPythonOperator(",
            f'        task_id="{task_id}",',
            f"        python_callable=_decide_{task_id},",
            "    )",
            "",
        ])
        return lines

    def _generate_airflow_dag(self, parsed: dict, analysis: dict, mapping_results: list) -> str:
        """Generate Airflow DAG with parallelism, task groups, and multiple operator types.

        Reflects the original Informatica workflow's parallel branches and worklet nesting.
        """
        wf_name = parsed["workflows"][0]["name"] if parsed["workflows"] else "informatica_migration"
        dag_id = re.sub(r'[^a-zA-Z0-9_]', '_', wf_name.lower())

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

        # Build workflow dependency graph
        wf_graph = self._build_workflow_dependency_graph(parsed)

        # Map session names to mapping names
        session_to_mapping = {}
        for sess in parsed.get("sessions", []):
            session_to_mapping[sess["name"]] = sess.get("mapping_name", "")

        sources = [s["name"] for s in parsed["sources"]]
        targets = [t["name"] for t in parsed["targets"]]

        lines = [
            '"""',
            f"Airflow DAG: {wf_name}",
            f"Auto-generated from Informatica workflow (Advanced Agent)",
            f"Sources: {', '.join(sources[:10])}{'...' if len(sources) > 10 else ''}",
            f"Targets: {', '.join(targets[:10])}{'...' if len(targets) > 10 else ''}",
            f"Mappings: {len(mapping_results)}",
            f"Worklets: {len(parsed.get('worklets', []))}",
            f"Command Tasks: {len(parsed.get('command_tasks', []))}",
            f"Event Wait Tasks: {len(parsed.get('event_wait_tasks', []))}",
            f"Decision Tasks: {len(parsed.get('decision_tasks', []))}",
            "",
            "SQL files are stored in the sql/ directory alongside this DAG.",
            "Deploy both this DAG and the sql/ folder to your Composer dags/ bucket:",
            "  gsutil -m cp -r sql/ gs://<composer-bucket>/dags/sql/",
            "  gsutil cp this_dag.py gs://<composer-bucket>/dags/",
            '"""',
            "",
            "from datetime import datetime, timedelta",
            "from pathlib import Path",
            "",
            "from airflow import DAG",
            "from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator",
            "from airflow.operators.bash import BashOperator",
            "from airflow.operators.python import PythonOperator, BranchPythonOperator",
            "from airflow.operators.dummy import DummyOperator",
            "from airflow.utils.task_group import TaskGroup",
            "from airflow.providers.google.cloud.sensors.gcs import GCSObjectExistenceSensor",
            "from airflow.sensors.external_task import ExternalTaskSensor",
            "",
            "# ── Configuration ─────────────────────────────────────────────",
            'PROJECT_ID = "{{ var.value.gcp_project_id }}"',
            'DATASET = "{{ var.value.bq_dataset }}"',
            'SQL_DIR = Path(__file__).parent / "sql"',
            "",
            "",
            "def _read_sql(filename: str) -> str:",
            '    """Read a SQL file from the sql/ directory."""',
            "    sql_path = SQL_DIR / filename",
            "    if sql_path.exists():",
            "        return sql_path.read_text(encoding='utf-8')",
            '    return f"-- ERROR: SQL file not found: {filename}"',
            "",
            "",
            "default_args = {",
            '    "owner": "data-engineering",',
            '    "depends_on_past": False,',
            '    "email_on_failure": True,',
            '    "email_on_retry": False,',
            '    "retries": 2,',
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
            f'    tags=["informatica-migration", "bigquery", "advanced"],',
            ") as dag:",
            "",
            '    start = DummyOperator(task_id="start")',
            '    end = DummyOperator(task_id="end")',
            "",
        ]

        # Create task per mapping (BigQuery tasks)
        mapping_task_ids = {}  # mapping_name -> task_id
        for mr in mapping_results:
            task_id = re.sub(r'[^a-zA-Z0-9_]', '_', mr["mapping_name"].lower())
            mapping_task_ids[mr["mapping_name"]] = task_id
            sql_filename = f"{task_id}.sql"

            lines.append(f'    # Mapping: {mr["mapping_name"]} ({mr["status"]})')
            lines.append(f'    {task_id} = BigQueryInsertJobOperator(')
            lines.append(f'        task_id="{task_id}",')
            lines.append("        configuration={")
            lines.append('            "query": {')
            lines.append(f'                "query": _read_sql("{sql_filename}"),')
            lines.append('                "useLegacySql": False,')
            lines.append("            }")
            lines.append("        },")
            lines.append("    )")
            lines.append("")

        # Create command tasks (BashOperator)
        cmd_task_ids = {}
        for cmd in parsed.get("command_tasks", []):
            task_id = re.sub(r'[^a-zA-Z0-9_]', '_', cmd["name"].lower())
            cmd_task_ids[cmd["name"]] = task_id
            cmd_str = " && ".join(cmd.get("commands", [])) or "echo 'TODO: implement command'"
            lines.append(f'    # Command Task: {cmd["name"]}')
            lines.append(f'    {task_id} = BashOperator(')
            lines.append(f'        task_id="{task_id}",')
            lines.append(f'        bash_command="""{cmd_str}""",')
            lines.append("    )")
            lines.append("")

        # Create TaskGroups for worklets
        worklet_task_ids = {}
        for wklt in parsed.get("worklets", []):
            wklt_id = re.sub(r'[^a-zA-Z0-9_]', '_', wklt["name"].lower())
            worklet_task_ids[wklt["name"]] = wklt_id
            lines.append(f'    # Worklet: {wklt["name"]}')
            lines.append(f'    with TaskGroup(group_id="{wklt_id}") as {wklt_id}:')
            lines.append(f'        {wklt_id}_start = DummyOperator(task_id="{wklt_id}_start")')
            lines.append(f'        {wklt_id}_end = DummyOperator(task_id="{wklt_id}_end")')

            # Add tasks within the worklet
            wklt_task_list = []
            for task in wklt.get("tasks", []):
                t_id = re.sub(r'[^a-zA-Z0-9_]', '_', task["name"].lower())
                t_type = task.get("type", "").upper()
                if t_type == "SESSION":
                    mapping_name = task.get("task_name", "")
                    if mapping_name in mapping_task_ids:
                        wklt_task_list.append(t_id)
                        # Reference to the mapping task (already created above)
                        lines.append(f'        # Session: {task["name"]} -> Mapping: {mapping_name}')
                elif t_type == "COMMAND":
                    wklt_task_list.append(t_id)
                    lines.append(f'        {t_id} = BashOperator(task_id="{t_id}", bash_command="echo TODO")')
                elif "START" in task["name"].upper():
                    pass  # Start event handled by worklet_start
                elif "EMAIL" in t_type.upper() or "EMAIL" in task["name"].upper():
                    wklt_task_list.append(t_id)
                    lines.append(f'        {t_id} = DummyOperator(task_id="{t_id}")  # Email placeholder')

            # Add internal worklet dependencies
            for link in wklt.get("links", []):
                from_id = re.sub(r'[^a-zA-Z0-9_]', '_', link["from_task"].lower())
                to_id = re.sub(r'[^a-zA-Z0-9_]', '_', link["to_task"].lower())
                if from_id == "start":
                    from_id = f"{wklt_id}_start"
                lines.append(f'        # {link["from_task"]} >> {link["to_task"]}')

            lines.append("")

        # Create reconciliation tasks (row-count verification after each mapping)
        recon_task_ids = {}  # mapping_task_id -> recon_task_id
        enable_recon = getattr(self, '_enable_reconciliation', True)
        recon_threshold = getattr(self, '_reconciliation_threshold_pct', 5.0)
        if enable_recon:
            for mr in mapping_results:
                m_task_id = mapping_task_ids.get(mr["mapping_name"])
                if not m_task_id:
                    continue
                # Gather source/target tables referenced in this mapping's SQL
                sql_lower = mr.get("sql", "").lower()
                m_sources = [s["name"] for s in parsed["sources"]
                             if s["name"].lower() in sql_lower]
                m_targets = [t["name"] for t in parsed["targets"]
                             if t["name"].lower() in sql_lower]
                if not m_sources:
                    m_sources = [parsed["sources"][0]["name"]] if parsed["sources"] else ["source"]
                if not m_targets:
                    m_targets = [parsed["targets"][0]["name"]] if parsed["targets"] else ["target"]
                recon_lines = self._generate_reconciliation_task(
                    mr["mapping_name"], m_sources[:3], m_targets[:3],
                    m_task_id, recon_threshold,
                )
                lines.extend(recon_lines)
                recon_task_ids[m_task_id] = f"recon_{m_task_id}"

        # Create Event Wait sensor tasks
        ew_task_ids = {}
        naming = getattr(self, '_naming_config', None)
        for ew_task in parsed.get("event_wait_tasks", []):
            ew_name = ew_task.get("name", "")
            ew_id = re.sub(r'[^a-zA-Z0-9_]', '_', ew_name.lower())
            ew_task_ids[ew_name] = ew_id
            sensor_lines = self._generate_sensor_task(ew_task, naming)
            lines.extend(sensor_lines)

        # Create Decision branch operators
        dec_task_ids = {}
        for dec_task in parsed.get("decision_tasks", []):
            dec_name = dec_task.get("name", "")
            dec_id = re.sub(r'[^a-zA-Z0-9_]', '_', dec_name.lower())
            dec_task_ids[dec_name] = dec_id
            # Map conditions to downstream tasks (via workflow links)
            downstream = {}
            for link in parsed.get("workflow_links", []):
                if link.get("from_task") == dec_name:
                    to_name = link.get("to_task", "")
                    to_id = re.sub(r'[^a-zA-Z0-9_]', '_', to_name.lower())
                    downstream[link.get("condition", to_name)] = to_id
            branch_lines = self._generate_branch_operator(
                dec_task, downstream, [],
            )
            lines.extend(branch_lines)

        # Build workflow-level dependencies from WORKFLOWLINK
        lines.append("    # ── Workflow Dependencies (from original Informatica workflow) ──")
        all_task_lookup = {}
        all_task_lookup.update(mapping_task_ids)
        all_task_lookup.update(cmd_task_ids)
        all_task_lookup.update(worklet_task_ids)
        all_task_lookup.update(ew_task_ids)
        all_task_lookup.update(dec_task_ids)
        # Also map session names to their mapping task IDs
        for sess_name, mapping_name in session_to_mapping.items():
            if mapping_name in mapping_task_ids:
                all_task_lookup[sess_name] = mapping_task_ids[mapping_name]

        edges = wf_graph.get("edges", {})
        dep_lines_added = set()
        for from_task, to_tasks in edges.items():
            from_id = all_task_lookup.get(from_task)
            if not from_id:
                from_id = re.sub(r'[^a-zA-Z0-9_]', '_', from_task.lower())
            for to_task in to_tasks:
                to_id = all_task_lookup.get(to_task)
                if not to_id:
                    to_id = re.sub(r'[^a-zA-Z0-9_]', '_', to_task.lower())
                dep_key = f"{from_id}>>{to_id}"
                if dep_key not in dep_lines_added:
                    lines.append(f"    # {from_task} >> {to_task}")
                    dep_lines_added.add(dep_key)

        # Show parallel groups
        if wf_graph.get("parallel_groups"):
            lines.append("")
            lines.append("    # ── Parallel Execution Groups ──")
            for i, pg in enumerate(wf_graph["parallel_groups"]):
                pg_ids = [all_task_lookup.get(t, re.sub(r'[^a-zA-Z0-9_]', '_', t.lower())) for t in pg]
                lines.append(f"    # Parallel group {i+1}: {', '.join(pg)}")

        # Wire reconciliation tasks: mapping >> recon
        if recon_task_ids:
            lines.append("")
            lines.append("    # ── Reconciliation Dependencies ──")
            for m_task_id, r_task_id in recon_task_ids.items():
                lines.append(f"    {m_task_id} >> {r_task_id}")

        # Fallback: if no workflow links found, create sequential chain
        if not edges:
            lines.append("    # No workflow links parsed — fallback sequential chain")
            task_names = list(mapping_task_ids.values())
            if task_names:
                lines.append(f"    start >> {task_names[0]}")
                for i in range(len(task_names) - 1):
                    lines.append(f"    {task_names[i]} >> {task_names[i + 1]}")
                lines.append(f"    {task_names[-1]} >> end")
            else:
                lines.append("    start >> end")

        return "\n".join(lines)

    # ── SCD MERGE (Two-Step) ─────────────────────────────────────

    def _generate_scd_merge(self, parsed: dict) -> str:
        """Generate a two-step SCD Type 2 MERGE statement."""
        tgt = parsed["targets"][0] if parsed["targets"] else {"name": "target_table", "columns": []}
        src = parsed["sources"][0] if parsed["sources"] else {"name": "source_table", "columns": []}

        tgt_name = tgt["name"].lower()
        src_name = src["name"].lower()
        key_cols = [c["name"] for c in tgt.get("columns", [])
                    if c.get("key_type") in ("PRIMARY KEY", "PRIMARY")]
        if not key_cols:
            key_cols = [tgt["columns"][0]["name"]] if tgt.get("columns") else ["id"]

        all_cols = [c["name"] for c in tgt.get("columns", [])]
        # Exclude SCD metadata columns from data columns
        scd_meta_cols = {"effective_start_date", "effective_end_date", "is_current",
                         "effective_date", "expiry_date", "current_flag",
                         "dw_insert_date", "dw_update_date"}
        data_cols = [c for c in all_cols if c not in key_cols and c.lower() not in scd_meta_cols]
        non_key_cols = [c for c in all_cols if c not in key_cols]

        merge_key = " AND ".join(f"target.{k} = source.{k}" for k in key_cols)
        change_detect = " OR ".join(f"target.{c} != source.{c}" for c in data_cols[:5]) or "1=1"
        update_cols = ",\n  ".join(f"target.{c} = source.{c}" for c in data_cols[:10])
        insert_cols = ", ".join(all_cols[:15])
        insert_vals = ", ".join(f"source.{c}" if c.lower() not in scd_meta_cols
                                else "CURRENT_TIMESTAMP()" if "start" in c.lower()
                                else "TIMESTAMP('9999-12-31')" if "end" in c.lower() or "expiry" in c.lower()
                                else "TRUE" if "current" in c.lower() or "flag" in c.lower()
                                else f"source.{c}"
                                for c in all_cols[:15])

        return f"""-- ============================================================
-- SCD Type 2: Two-Step Pattern for {tgt_name}
-- Generated by Advanced Informatica Migration Agent
-- ============================================================

-- Step 1: Close existing records that have changed
-- (Set is_current = FALSE, update effective_end_date)
UPDATE `project.dataset.{tgt_name}` AS target
SET
  target.is_current = FALSE,
  target.effective_end_date = CURRENT_TIMESTAMP()
WHERE target.is_current = TRUE
AND EXISTS (
  SELECT 1 FROM `project.dataset.{src_name}_staging` AS source
  WHERE {merge_key}
  AND ({change_detect})
);

-- Step 2: Insert new versions of changed records + brand new records
INSERT INTO `project.dataset.{tgt_name}` (
  {insert_cols}
)
SELECT
  {insert_vals}
FROM `project.dataset.{src_name}_staging` AS source
WHERE NOT EXISTS (
  SELECT 1 FROM `project.dataset.{tgt_name}` AS target
  WHERE {merge_key}
  AND target.is_current = TRUE
  AND NOT ({change_detect})
);"""

    # ── Scorecard Calculation ────────────────────────────────────

    def _calculate_scorecard(
        self, parsed: dict, analysis: dict,
        mapping_results: list, parameters: list,
        expression_comparisons: list,
    ) -> dict:
        """Calculate multi-dimensional migration scorecard."""
        # SQL coverage: % of mappings with generated SQL
        total_mappings = len(mapping_results) if mapping_results else 1
        mappings_with_sql = sum(1 for mr in mapping_results if mr.get("sql") and len(mr["sql"]) > 50)
        sql_coverage = round((mappings_with_sql / total_mappings) * 100) if total_mappings > 0 else 0

        # Target coverage: % of targets addressed in SQL
        total_targets = len(parsed.get("targets", []))
        # Pre-lowercase all SQL once (instead of per-target per-mapping)
        all_sql_lower = " ".join(mr.get("sql", "").lower() for mr in mapping_results)
        target_names_in_sql = set()
        for tgt in parsed.get("targets", []):
            if tgt["name"].lower() in all_sql_lower:
                target_names_in_sql.add(tgt["name"])
        target_coverage = round((len(target_names_in_sql) / total_targets) * 100) if total_targets > 0 else 0

        # Expression fidelity: % of expressions successfully converted
        total_exprs = len(expression_comparisons) if expression_comparisons else 1
        converted_exprs = sum(1 for ec in expression_comparisons if ec["status"] == "converted")
        expression_fidelity = round((converted_exprs / total_exprs) * 100) if total_exprs > 0 else 0

        # DAG completeness: % of mappings with proper DAG tasks
        dag_completeness = sql_coverage  # Mirrors SQL coverage since each mapping gets a DAG task

        # Parameter resolution: % of $$params that are resolved
        total_params = len(parameters) if parameters else 0
        # All extracted params are "resolved" by replacement with @param
        param_resolution = 100 if total_params > 0 else 100

        # SCD coverage: 100 if SCD detected and handled, 0 if detected but not handled
        if analysis.get("has_scd_pattern"):
            scd_coverage = 100  # We always generate SCD MERGE when detected
        else:
            scd_coverage = 100  # No SCD needed = 100%

        # Weighted overall score
        overall = round(
            sql_coverage * 0.30 +
            target_coverage * 0.20 +
            expression_fidelity * 0.20 +
            dag_completeness * 0.15 +
            param_resolution * 0.10 +
            scd_coverage * 0.05
        )

        return {
            "overall_score": min(overall, 100),
            "sql_coverage": sql_coverage,
            "target_coverage": target_coverage,
            "expression_fidelity": expression_fidelity,
            "dag_completeness": dag_completeness,
            "parameter_resolution": param_resolution,
            "scd_coverage": scd_coverage,
        }

    # ── Recommendations ──────────────────────────────────────────

    def _build_recommendations(self, analysis: dict, parsed: dict, scorecard: dict) -> list:
        """Build migration recommendations based on analysis and scorecard."""
        recs = []

        if scorecard["overall_score"] < 60:
            recs.append("Overall conversion score is below 60%. Consider breaking complex mappings into simpler sub-workflows for better conversion.")

        if analysis["complexity"] == "high":
            recs.append("This is a complex workflow. Consider breaking it into smaller, independently schedulable DAGs.")

        if analysis["needs_dataflow"] > 0:
            recs.append(f"{analysis['needs_dataflow']} transformation(s) require Dataflow (Apache Beam) or Dataproc PySpark due to complexity.")

        if analysis["has_scd_pattern"]:
            recs.append("SCD pattern detected. The two-step MERGE pattern (UPDATE existing + INSERT new) is generated for reliable history tracking.")

        if len(parsed["sources"]) > 3:
            recs.append("Multiple data sources detected. Consider using BigQuery federated queries for external sources.")

        if analysis["unsupported"]:
            recs.append(f"{len(analysis['unsupported'])} unsupported pattern(s) require manual review and custom implementation.")

        if scorecard["expression_fidelity"] < 80:
            recs.append(f"Expression conversion fidelity is {scorecard['expression_fidelity']}%. Review the Expression Compare tab for expressions that need manual adjustment.")

        if scorecard["target_coverage"] < 100:
            recs.append(f"Target coverage is {scorecard['target_coverage']}%. Some target tables may not have corresponding SQL generated.")

        recs.append("Set up Airflow Variables for project_id, dataset, and connection details before deploying the DAG.")
        recs.append("Test the BigQuery SQL statements individually before enabling the full DAG.")

        return recs

    # ── Migration Summary ────────────────────────────────────────

    def _build_migration_summary(self, parsed: dict, analysis: dict, scorecard: dict) -> str:
        """Build a human-readable migration summary."""
        parts = []
        parts.append(f"Advanced migration from Informatica to GCP BigQuery + Airflow.")
        parts.append(f"Found {len(parsed['sources'])} source(s), {len(parsed['targets'])} target(s), "
                      f"{analysis['total_transformations']} transformation(s), "
                      f"and {analysis.get('total_connectors', 0)} connector(s).")
        parts.append(f"Processed {analysis.get('total_mappings', 0)} mapping(s) individually.")
        parts.append(f"Overall Score: {scorecard['overall_score']}%. Complexity: {analysis['complexity'].upper()}.")
        parts.append(f"{analysis['sql_convertible']} transformation(s) converted to BigQuery SQL.")
        if analysis['needs_dataflow'] > 0:
            parts.append(f"{analysis['needs_dataflow']} transformation(s) need Dataflow/Dataproc.")
        if analysis['has_scd_pattern']:
            parts.append("SCD pattern detected — two-step MERGE statement generated.")
        if analysis['unsupported']:
            parts.append(f"{len(analysis['unsupported'])} unsupported pattern(s) flagged for manual review.")
        return " ".join(parts)
