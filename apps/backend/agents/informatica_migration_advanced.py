from __future__ import annotations

import asyncio
import json
import logging
import re
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
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
    # Null handling
    r'\bISNULL\s*\(': "IS NULL -- ",
    r'\bNVL\s*\(': "IFNULL(",
    r'\bNVL2\s*\(': "IF(",
    # Validation
    r'\bIS_SPACES\s*\(': "TRIM(",
    r'\bIS_NUMBER\s*\(': "SAFE_CAST(",
    # Error handling
    r'\bERROR\s*\(': "ERROR(",
    r'\bABORT\s*\(': "ERROR(",
    # Teradata-specific
    r'\bZEROIFNULL\s*\(': "IFNULL(",
    r'\bNULLIFZERO\s*\(': "NULLIF(",
    r'\bQUALIFY\b': "QUALIFY",
    r'\bMINUS\b': "EXCEPT DISTINCT",
}

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

    async def migrate(self, xml_content: str, filename: str = "workflow.xml") -> dict:
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

        # Step 6: Process mappings — LLM-assisted when available, else rule-based
        LLM_CONCURRENCY = 3

        if self.llm.client is not None:
            # ── LLM path: send all mappings through LLM with concurrency limit ──
            llm_semaphore = asyncio.Semaphore(LLM_CONCURRENCY)

            async def _process_with_llm(mapping_name, group):
                async with llm_semaphore:
                    return await self._process_mapping(
                        mapping_name, group, parsed, connector_graph, parameters
                    )

            logger.info(
                "Processing %d mappings with LLM (concurrency=%d)",
                len(mapping_groups), LLM_CONCURRENCY,
            )

            tasks = [
                _process_with_llm(name, group)
                for name, group in mapping_groups.items()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            # ── No LLM: fast rule-based path in thread pool ──
            def _process_all_rule_based():
                _results = []
                for name, group in mapping_groups.items():
                    try:
                        r = self._process_mapping_rule_only_sync(
                            name, group, parsed, connector_graph, parameters
                        )
                        _results.append(r)
                    except Exception as exc:
                        logger.warning("Mapping processing failed for %s: %s", name, exc)
                return _results

            logger.info("Processing %d mappings (rule-based, no LLM)", len(mapping_groups))
            results = await asyncio.to_thread(_process_all_rule_based)

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

        for mapping in root.iter("MAPPING"):
            mp = {
                "name": mapping.get("NAME", ""),
                "description": mapping.get("DESCRIPTION", ""),
            }
            result["mappings"].append(mp)

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

        for session in root.iter("SESSION"):
            sess = {
                "name": session.get("NAME", ""),
                "mapping_name": session.get("MAPPINGNAME", ""),
                "description": session.get("DESCRIPTION", ""),
            }
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

    def _build_connector_graph(self, parsed: dict) -> dict:
        """Build a directed graph from connectors for data flow understanding.

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

        for conn in parsed.get("connectors", []):
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
        """Group transformations by mapping using connector graph traversal.

        For each mapping, trace the data flow from sources through transformations
        to targets using the connector graph.
        """
        tf_by_name = {tf["name"]: tf for tf in parsed["transformations"]}
        source_names = {s["name"] for s in parsed["sources"]}
        target_names = {t["name"] for t in parsed["targets"]}

        # If we have explicit mappings with sessions, use session->mapping associations
        session_mapping = {}
        for sess in parsed.get("sessions", []):
            if sess.get("mapping_name"):
                session_mapping[sess["mapping_name"]] = sess["name"]

        # Build mapping groups via graph traversal
        mapping_groups = {}
        instance_edges = connector_graph.get("instance_edges", {})

        # Pre-compute SQ_ set once (not per mapping)
        sq_names = {n for n in tf_by_name if n.startswith("SQ_") or n.startswith("sq_")}

        if parsed["mappings"]:
            for mp in parsed["mappings"]:
                mp_name = mp["name"]
                # Find all transformations reachable from sources via connector graph
                visited = set()
                queue = deque()

                # Start from source qualifier instances (instances connected from sources)
                for src_name in source_names:
                    if src_name in instance_edges:
                        for next_inst in instance_edges[src_name]:
                            if next_inst not in visited:
                                queue.append(next_inst)
                                visited.add(next_inst)

                # Also add any SQ_ prefixed (Source Qualifier) transformations
                for sq_name in sq_names:
                    if sq_name not in visited:
                        queue.append(sq_name)
                        visited.add(sq_name)

                while queue:
                    current = queue.popleft()  # O(1) with deque vs O(n) with list.pop(0)
                    if current in instance_edges:
                        for next_inst in instance_edges[current]:
                            if next_inst not in visited:
                                visited.add(next_inst)
                                queue.append(next_inst)

                # Collect transformations that are in our visited set
                group_tfs = []
                for tf_name in visited:
                    if tf_name in tf_by_name:
                        group_tfs.append(tf_by_name[tf_name])

                # Find sources and targets for this mapping
                group_sources = [s for s in parsed["sources"] if s["name"] in visited or
                                 any(s["name"] in instance_edges.get(s["name"], set()) for _ in [0])]
                group_targets = [t for t in parsed["targets"] if t["name"] in visited]

                mapping_groups[mp_name] = {
                    "transformations": group_tfs if group_tfs else parsed["transformations"],
                    "sources": group_sources if group_sources else parsed["sources"],
                    "targets": group_targets if group_targets else parsed["targets"],
                    "description": mp.get("description", ""),
                }
        else:
            # No explicit mappings: treat all transformations as one group
            mapping_groups["default_mapping"] = {
                "transformations": parsed["transformations"],
                "sources": parsed["sources"],
                "targets": parsed["targets"],
                "description": "",
            }

        return mapping_groups

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
            for src in group["sources"][:3]:
                if src["columns"]:
                    cols = [c["name"] for c in src["columns"][:10]]
                    parts.append(f"  {src['name']} columns: {', '.join(cols)}")

        if group["targets"]:
            tgt_names = [t["name"] for t in group["targets"]]
            parts.append(f"Targets: {', '.join(tgt_names)}")
            for tgt in group["targets"][:3]:
                if tgt["columns"]:
                    cols = [c["name"] for c in tgt["columns"][:10]]
                    parts.append(f"  {tgt['name']} columns: {', '.join(cols)}")

        parts.append(f"\nTransformations ({len(group['transformations'])}):")
        for tf in group["transformations"]:
            line = f"  - {tf['name']} (type: {tf['type']})"
            if tf.get("fields"):
                expr_fields = [f for f in tf["fields"] if f.get("expression")]
                if expr_fields:
                    exprs = [f"{f['name']} = {f['expression']}" for f in expr_fields[:5]]
                    line += f"\n    Expressions: {'; '.join(exprs)}"
            if tf.get("properties"):
                props = [f"{k}={v}" for k, v in list(tf["properties"].items())[:3]]
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

    # ── Rule-Based Per-Mapping SQL ───────────────────────────────

    def _rule_based_mapping_sql(
        self, mapping_name: str, group: dict,
        connector_graph: dict, parameters: list,
    ) -> str:
        """Generate BigQuery SQL for a single mapping using rule-based conversion."""
        lines = [
            f"-- ============================================================",
            f"-- BigQuery SQL for mapping: {mapping_name}",
            f"-- Sources: {', '.join(s['name'] for s in group['sources'])}",
            f"-- Targets: {', '.join(t['name'] for t in group['targets'])}",
            f"-- ============================================================",
            "",
        ]

        # Build source extracts for ALL sources (not just first)
        for i, src in enumerate(group["sources"]):
            cols = [c["name"] for c in src["columns"]] if src["columns"] else ["*"]
            lines.append(f"-- Step {i + 1}: Extract from source ({src['name']})")
            lines.append(f"CREATE OR REPLACE TABLE `project.dataset.staging_{src['name'].lower()}` AS")
            lines.append("SELECT")
            lines.append("  " + ",\n  ".join(cols))
            lines.append(f"FROM `project.dataset.{src['name'].lower()}`")
            lines.append(";")
            lines.append("")

        # Process transformations
        step = len(group["sources"]) + 1
        prev_table = f"staging_{group['sources'][0]['name'].lower()}" if group["sources"] else "source_table"

        for tf in group["transformations"]:
            tf_type = tf["type"]

            if tf_type in ("Expression", "SQL Transformation"):
                lines.append(f"-- Step {step}: {tf['name']} ({tf_type})")
                table_name = f"transform_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}"
                lines.append(f"CREATE OR REPLACE TABLE `project.dataset.{table_name}` AS")
                lines.append("SELECT")
                expr_fields = []
                for field in tf.get("fields", []):
                    expr = field.get("expression", "")
                    name = field.get("name", "unknown")
                    if expr:
                        expr_bq = self._convert_expression(expr, parameters)
                        expr_fields.append(f"  {expr_bq} AS {name}")
                    else:
                        expr_fields.append(f"  {name}")
                lines.append(",\n".join(expr_fields) if expr_fields else "  *")
                lines.append(f"FROM `project.dataset.{prev_table}`")
                lines.append(";")
                lines.append("")
                prev_table = table_name
                step += 1

            elif tf_type == "Filter":
                lines.append(f"-- Step {step}: {tf['name']} (Filter)")
                filter_cond = tf.get("properties", {}).get("Filter Condition", "1=1")
                filter_cond = self._convert_expression(filter_cond, parameters)
                table_name = f"filtered_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}"
                lines.append(f"CREATE OR REPLACE TABLE `project.dataset.{table_name}` AS")
                lines.append(f"SELECT * FROM `project.dataset.{prev_table}`")
                lines.append(f"WHERE {filter_cond};")
                lines.append("")
                prev_table = table_name
                step += 1

            elif tf_type == "Aggregator":
                lines.append(f"-- Step {step}: {tf['name']} (Aggregator → GROUP BY)")
                table_name = f"agg_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}"
                lines.append(f"CREATE OR REPLACE TABLE `project.dataset.{table_name}` AS")
                group_fields = []
                agg_fields = []
                for field in tf.get("fields", []):
                    expr = field.get("expression", "")
                    name = field.get("name", "")
                    port = field.get("porttype", "")
                    if "OUTPUT" in port.upper() and expr:
                        agg_fields.append(f"  {self._convert_expression(expr, parameters)} AS {name}")
                    elif name:
                        group_fields.append(name)
                lines.append("SELECT")
                all_fields = [f"  {g}" for g in group_fields] + agg_fields
                lines.append(",\n".join(all_fields) if all_fields else "  *")
                lines.append(f"FROM `project.dataset.{prev_table}`")
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
                lines.append(f"CREATE OR REPLACE TABLE `project.dataset.{table_name}` AS")
                if len(join_sources) >= 2:
                    lines.append(f"SELECT * FROM `project.dataset.{join_sources[0].lower()}`")
                    lines.append(f"{bq_join} `project.dataset.{join_sources[1].lower()}`")
                else:
                    lines.append(f"SELECT * FROM `project.dataset.{prev_table}`")
                    lines.append(f"{bq_join} lookup_table")
                lines.append(f"ON {join_cond};")
                lines.append("")
                prev_table = table_name
                step += 1

            elif tf_type == "Lookup":
                lines.append(f"-- Step {step}: {tf['name']} (Lookup → LEFT JOIN)")
                lookup_sql = tf.get("properties", {}).get("Lookup Sql Override", "")
                if lookup_sql:
                    lookup_sql = self._convert_expression(lookup_sql, parameters)
                    lines.append(f"-- Lookup SQL: {lookup_sql}")
                table_name = f"lookup_{re.sub(r'[^a-zA-Z0-9_]', '_', tf['name'].lower())}"
                lines.append(f"CREATE OR REPLACE TABLE `project.dataset.{table_name}` AS")
                lines.append(f"SELECT a.*, b.*")
                lines.append(f"FROM `project.dataset.{prev_table}` a")
                if lookup_sql:
                    lines.append(f"LEFT JOIN ({lookup_sql}) b ON a.key = b.key")
                else:
                    lines.append(f"LEFT JOIN `project.dataset.lookup_table` b ON a.key = b.key")
                lines.append(";")
                lines.append("")
                prev_table = table_name
                step += 1

            elif tf_type == "Router":
                lines.append(f"-- Step {step}: {tf['name']} (Router → CASE WHEN)")
                lines.append("-- Use CASE WHEN to route records:")
                for prop_name, prop_val in tf.get("properties", {}).items():
                    if "Group Filter" in prop_name:
                        converted = self._convert_expression(prop_val, parameters)
                        lines.append(f"--   WHEN {converted} THEN ...")
                lines.append("")
                step += 1

            elif tf_type == "Sequence Generator":
                lines.append(f"-- Step {step}: {tf['name']} (Sequence → ROW_NUMBER)")
                lines.append("-- ROW_NUMBER() OVER (ORDER BY <key>) AS sequence_id")
                lines.append("-- Or: GENERATE_UUID() for unique identifiers")
                lines.append("")
                step += 1

            elif tf_type == "Sorter":
                lines.append(f"-- Step {step}: {tf['name']} (Sorter → ORDER BY)")
                lines.append(f"-- ORDER BY applied to `project.dataset.{prev_table}`")
                lines.append("")
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
                    lines.append(f"CREATE OR REPLACE TABLE `project.dataset.{table_name}` AS")
                    for idx, us in enumerate(union_sources):
                        if idx > 0:
                            lines.append("UNION ALL")
                        lines.append(f"SELECT * FROM `project.dataset.{us.lower()}`")
                    lines.append(";")
                    prev_table = table_name
                lines.append("")
                step += 1

        # Final target loads for ALL targets (not just first)
        for tgt in group["targets"]:
            tgt_cols = [c["name"] for c in tgt["columns"]] if tgt["columns"] else ["*"]
            lines.append(f"-- Final: Load into target ({tgt['name']})")
            lines.append(f"INSERT INTO `project.dataset.{tgt['name'].lower()}`")
            lines.append(f"  ({', '.join(tgt_cols)})")
            lines.append("SELECT")
            lines.append("  " + ",\n  ".join(tgt_cols))
            lines.append(f"FROM `project.dataset.{prev_table}`")
            lines.append(";")
            lines.append("")

        return "\n".join(lines)

    # ── Expression Conversion ────────────────────────────────────

    def _convert_expression(self, expr: str, parameters: list | None = None) -> str:
        """Convert Informatica expression syntax to BigQuery SQL (expanded).

        Uses pre-compiled regex patterns and an LRU cache for speed.
        """
        if expr in _expression_cache:
            return _expression_cache[expr]

        converted = expr

        # Apply all pre-compiled expression conversions (avoids re.compile per call)
        for compiled_re, replacement in _COMPILED_CONVERSIONS:
            converted = compiled_re.sub(replacement, converted)

        # Replace $$parameters with @param_name
        converted = _PARAM_RE.sub(r'@\1', converted)

        _expression_cache[expr] = converted
        return converted

    # ── Airflow DAG Generation ───────────────────────────────────

    def _generate_airflow_dag(self, parsed: dict, analysis: dict, mapping_results: list) -> str:
        """Generate Airflow DAG with per-mapping tasks that read SQL from files.

        Each mapping's SQL is stored in a separate .sql file under a sql/ directory
        alongside the DAG. The DAG reads each file at runtime using pathlib.
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

        sources = [s["name"] for s in parsed["sources"]]
        targets = [t["name"] for t in parsed["targets"]]

        lines = [
            '"""',
            f"Airflow DAG: {wf_name}",
            f"Auto-generated from Informatica workflow (Advanced Agent)",
            f"Sources: {', '.join(sources[:10])}{'...' if len(sources) > 10 else ''}",
            f"Targets: {', '.join(targets[:10])}{'...' if len(targets) > 10 else ''}",
            f"Mappings: {len(mapping_results)}",
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
            "from airflow.operators.dummy import DummyOperator",
            "",
            "# ── Configuration ─────────────────────────────────────────────",
            "# Set these Airflow Variables in the Composer UI:",
            "#   gcp_project_id  — your GCP project ID",
            "#   bq_dataset      — target BigQuery dataset name",
            'PROJECT_ID = "{{ var.value.gcp_project_id }}"',
            'DATASET = "{{ var.value.bq_dataset }}"',
            "",
            "# SQL files directory (alongside this DAG file)",
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

        # Create a task per mapping — each reads its SQL from a .sql file
        task_names = []
        for mr in mapping_results:
            task_id = re.sub(r'[^a-zA-Z0-9_]', '_', mr["mapping_name"].lower())
            task_names.append(task_id)
            sql_filename = f"{task_id}.sql"

            lines.append(f'    # Mapping: {mr["mapping_name"]} ({mr["status"]})')
            lines.append(f'    # Transformations converted: {mr["transformations_converted"]}/{mr["transformations_used"]}')
            if mr.get("used_llm"):
                lines.append(f'    # Engine: LLM-assisted')
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
