from __future__ import annotations

import logging
import re
from typing import Optional

from agents.base import BaseAgent
from knowledge.store import get_knowledge_store

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Code Accelerator agent for enterprise data migration.
Your job is to convert legacy SQL, stored procedures, and ETL scripts into modern
BigQuery-compatible code.

Supported migration modes:
- teradata_to_bigquery
- oracle_to_bigquery
- netezza_to_bigquery
- stored_proc_to_dataform
- etl_to_dataflow
- sas_to_python

When converting code:
1. Identify all legacy-specific syntax
2. Convert to the target platform equivalent
3. Replace legacy table references with their GCP BigQuery equivalents using the knowledge base
4. List all changes made
5. Note any warnings (e.g., features with no direct equivalent)
6. Estimate a completion percentage

Use the knowledge base context provided to map legacy table references to their
correct GCP BigQuery fully-qualified names.
Always respond with valid JSON matching the requested schema."""


class CodeAcceleratorAgent(BaseAgent):
    name = "Code Accelerator"
    slug = "code-accelerator"
    system_prompt = SYSTEM_PROMPT

    def _find_table_mappings(self, input_code: str) -> list[dict]:
        """Find legacy table references in code and look up their GCP mappings."""
        store = get_knowledge_store()
        mappings = []

        # Extract potential table references
        patterns = [
            r'(?:FROM|JOIN|INTO)\s+[`"]?(\w+(?:\.\w+){0,2})[`"]?',
            r'(?:FROM|JOIN|INTO)\s+`([^`]+)`',
        ]

        table_refs = set()
        for pattern in patterns:
            matches = re.findall(pattern, input_code, re.IGNORECASE)
            table_refs.update(matches)

        for ref in table_refs:
            ref_clean = ref.replace("`", "").strip()
            parts = ref_clean.split(".")
            # Try each part and combination
            search_names = [ref_clean]
            if len(parts) > 1:
                search_names.append(parts[-1])
            if len(parts) > 2:
                search_names.append(f"{parts[0]}.{parts[1]}")

            for name in search_names:
                info = store.get_table_info(name)
                if info:
                    gcp_path = info.get("gcp_full_path", "")
                    if gcp_path:
                        mappings.append({
                            "original": ref,
                            "gcp_path": gcp_path,
                            "gcp_table": info.get("gcp_table", ""),
                            "modernized": info.get("modernization_status", "") == "Completed",
                            "info": info,
                        })
                    break

        return mappings

    async def convert(
        self,
        mode: str,
        input_code: str,
        source_format: Optional[str] = None,
    ) -> dict:
        """Convert legacy code to modern equivalent.

        Uses knowledge base to resolve table references and LLM for code conversion.
        """
        if not input_code or not input_code.strip():
            return self._build_empty_response(mode)

        # Find table mappings from knowledge base
        table_mappings = self._find_table_mappings(input_code)

        # Build knowledge base context for LLM
        kb_context = ""
        if table_mappings:
            kb_context = "\n\nKnowledge Base Table Mappings:\n"
            for m in table_mappings:
                kb_context += (
                    f"  {m['original']} -> `{m['gcp_path']}` "
                    f"(modernized: {m['modernized']})\n"
                )

        # Build mode-specific LLM instructions
        mode_instructions = ""
        if "tableau" in mode.lower() or "looker" in mode.lower():
            mode_instructions = (
                "\n\nIMPORTANT: This is a Tableau to Looker conversion. "
                "The output_code MUST be in LookML format. Convert the SQL into a LookML view "
                "with dimensions, measures, and derived tables as appropriate. Example LookML:\n"
                "view: view_name {\n"
                "  sql_table_name: `project.dataset.table` ;;\n"
                "  dimension: col_name {\n"
                "    type: string\n"
                "    sql: ${TABLE}.col_name ;;\n"
                "  }\n"
                "  measure: count {\n"
                "    type: count\n"
                "  }\n"
                "}\n"
            )
        elif "teradata" in mode.lower():
            mode_instructions = (
                "\n\nIMPORTANT: Convert ALL Teradata-specific syntax to BigQuery equivalents AND "
                "replace ALL legacy table references with their GCP BigQuery fully-qualified names. "
                "Both syntax AND table names must be converted."
            )

        # Try LLM for intelligent conversion
        if self.llm.client is not None:
            result = await self.call_llm(
                user_message=(
                    f"Convert the following code.\n"
                    f"Mode: {mode}\n"
                    f"Source format: {source_format or 'auto-detect'}\n\n"
                    f"```\n{input_code}\n```"
                    f"{kb_context}"
                    f"{mode_instructions}"
                ),
                response_schema={
                    "output_code": "string",
                    "changes": [
                        {
                            "original": "string",
                            "converted": "string",
                            "explanation": "string",
                        }
                    ],
                    "warnings": [
                        {
                            "type": "string",
                            "message": "string",
                        }
                    ],
                    "completion_pct": "integer",
                },
            )
            if result is not None:
                return result

        # No LLM — do rule-based conversion using knowledge base
        if "tableau" in mode.lower() or "looker" in mode.lower():
            return self._rule_based_lookml_convert(input_code, table_mappings)
        return self._rule_based_convert(mode, input_code, table_mappings)

    def _rule_based_convert(
        self,
        mode: str,
        input_code: str,
        table_mappings: list[dict],
    ) -> dict:
        """Perform rule-based code conversion without LLM."""
        output_code = input_code
        changes = []
        warnings = []

        # Apply table mappings
        for mapping in table_mappings:
            original = mapping["original"]
            gcp_path = mapping["gcp_path"]

            if original in output_code:
                output_code = output_code.replace(original, f"`{gcp_path}`")
                changes.append({
                    "original": original,
                    "converted": f"`{gcp_path}`",
                    "explanation": "Updated to fully-qualified BigQuery table reference from knowledge base",
                })

        # Apply Teradata-to-BigQuery syntax conversions
        if "teradata" in mode.lower():
            conversions = [
                (r'ZEROIFNULL\(([^)]+)\)', r'IFNULL(\1, 0)', "BigQuery equivalent for null-to-zero"),
                (r"CAST\((\w+)\s+AS\s+DATE\s+FORMAT\s+'[^']+'\)", r'CAST(\1 AS DATE)', "BigQuery uses ISO 8601 date format by default"),
                (r'SEL\b', 'SELECT', "Teradata SEL abbreviation replaced with SELECT"),
                (r'\.DATE\b', 'CURRENT_DATE()', "Replaced Teradata .DATE with BigQuery CURRENT_DATE()"),
                (r'SAMPLE\s+(\d+)', r'ORDER BY RAND() LIMIT \1', "Replaced Teradata SAMPLE with BigQuery random sampling"),
                (r'QUALIFY\s+', 'QUALIFY ', "QUALIFY is supported natively in BigQuery"),
                (r'CHARACTERS\(([^)]+)\)', r'CHAR_LENGTH(\1)', "Replaced CHARACTERS() with CHAR_LENGTH()"),
                (r'INDEX\(([^,]+),\s*([^)]+)\)', r'STRPOS(\1, \2)', "Replaced INDEX() with STRPOS()"),
            ]

            for pattern, replacement, explanation in conversions:
                if re.search(pattern, output_code, re.IGNORECASE):
                    output_code = re.sub(pattern, replacement, output_code, flags=re.IGNORECASE)
                    changes.append({
                        "original": pattern,
                        "converted": replacement,
                        "explanation": explanation,
                    })

            warnings.append({
                "type": "collation",
                "message": "BigQuery defaults to case-sensitive comparisons. Verify string comparisons and joins.",
            })

        elif "oracle" in mode.lower():
            conversions = [
                (r'NVL\(([^,]+),\s*([^)]+)\)', r'IFNULL(\1, \2)', "Replaced Oracle NVL with BigQuery IFNULL"),
                (r'SYSDATE', 'CURRENT_TIMESTAMP()', "Replaced Oracle SYSDATE with BigQuery CURRENT_TIMESTAMP()"),
                (r'ROWNUM\s*<=?\s*(\d+)', r'LIMIT \1', "Replaced Oracle ROWNUM with BigQuery LIMIT"),
                (r'TO_DATE\(([^,]+),\s*([^)]+)\)', r'PARSE_DATE(\2, \1)', "Replaced TO_DATE with PARSE_DATE"),
                (r'DECODE\(([^)]+)\)', r'CASE \1 END', "Replaced Oracle DECODE with CASE statement"),
            ]

            for pattern, replacement, explanation in conversions:
                if re.search(pattern, output_code, re.IGNORECASE):
                    output_code = re.sub(pattern, replacement, output_code, flags=re.IGNORECASE)
                    changes.append({
                        "original": pattern,
                        "converted": replacement,
                        "explanation": explanation,
                    })

        # If no changes were made, add a note
        if not changes:
            warnings.append({
                "type": "no_changes",
                "message": "No automatic conversions were applied. The code may already be BigQuery-compatible or require manual review.",
            })

        # Estimate completion
        completion = 50
        if table_mappings:
            completion += min(25, len(table_mappings) * 5)
        if changes:
            completion += min(25, len(changes) * 5)
        completion = min(95, completion)

        return {
            "output_code": output_code,
            "changes": changes,
            "warnings": warnings,
            "completion_pct": completion,
        }

    def _rule_based_lookml_convert(self, input_code: str, table_mappings: list[dict]) -> dict:
        """Convert SQL to basic LookML format without LLM."""
        # Extract column names from SELECT
        columns = []
        select_match = re.search(r'SELECT\s+([\s\S]*?)\s+FROM', input_code, re.IGNORECASE)
        if select_match:
            cols_str = select_match.group(1)
            for col in cols_str.split(","):
                col = col.strip()
                # Handle aliases
                alias_match = re.search(r'(?:AS\s+)?(\w+)\s*$', col, re.IGNORECASE)
                if alias_match:
                    columns.append(alias_match.group(1))

        # Determine table name
        table_name = "my_table"
        table_path = "project.dataset.table"
        from_match = re.search(r'FROM\s+[`"]?(\w+(?:\.\w+)*)[`"]?', input_code, re.IGNORECASE)
        if from_match:
            table_name = from_match.group(1).split(".")[-1].lower()
        if table_mappings:
            table_path = table_mappings[0].get("gcp_path", table_path)
            table_name = table_mappings[0].get("gcp_table", table_name)

        # Build LookML
        lookml_lines = [f"view: {table_name} {{"]
        lookml_lines.append(f"  sql_table_name: `{table_path}` ;;")
        lookml_lines.append("")

        changes = []
        for col in columns:
            col_clean = col.lower().strip()
            if col_clean == "*":
                continue
            dim_type = "string"
            if any(kw in col_clean for kw in ("id", "count", "num", "amount", "qty", "revenue", "price")):
                dim_type = "number"
            if any(kw in col_clean for kw in ("date", "time", "created", "updated")):
                dim_type = "date" if "time" not in col_clean else "date_time"

            lookml_lines.append(f"  dimension: {col_clean} {{")
            lookml_lines.append(f"    type: {dim_type}")
            lookml_lines.append(f"    sql: ${{TABLE}}.{col_clean} ;;")
            lookml_lines.append("  }")
            lookml_lines.append("")
            changes.append({
                "original": f"Column: {col}",
                "converted": f"dimension: {col_clean} (type: {dim_type})",
                "explanation": f"SQL column mapped to LookML dimension",
            })

        lookml_lines.append("  measure: count {")
        lookml_lines.append("    type: count")
        lookml_lines.append("  }")
        lookml_lines.append("}")

        lookml_output = "\n".join(lookml_lines)

        return {
            "output_code": lookml_output,
            "changes": changes,
            "warnings": [
                {
                    "type": "lookml_basic",
                    "message": "This is a basic LookML conversion. Review dimension types, add measures, and adjust for your Looker model.",
                }
            ],
            "completion_pct": 60,
        }

    def _build_empty_response(self, mode: str) -> dict:
        """Response when no input code is provided."""
        return {
            "output_code": "",
            "changes": [],
            "warnings": [
                {
                    "type": "no_input",
                    "message": "No input code was provided. Paste your legacy SQL or code to convert.",
                }
            ],
            "completion_pct": 0,
        }

    async def optimize(self, input_code: str) -> dict:
        """Analyze SQL for performance and return health assessment."""
        if not input_code or not input_code.strip():
            return {
                "health_score": 0,
                "critical_issues": [],
                "warnings": [{"title": "No Input", "description": "No SQL was provided.", "suggestion": "Paste your SQL to analyze."}],
                "recommendations": [],
                "optimized_code": "",
            }

        # Try LLM for intelligent analysis
        if self.llm.client is not None:
            optimize_prompt = """You are a BigQuery SQL performance expert. Analyze the given SQL query and return:
1. A health_score (0-100, where 100 is perfectly optimized)
2. critical_issues: serious performance problems (each with title, description, suggestion)
3. warnings: minor issues or best practice violations (each with title, description, suggestion)
4. recommendations: general optimization tips as strings
5. optimized_code: the optimized version of the SQL

Focus on: partition pruning, clustering usage, SELECT *, unnecessary JOINs,
subquery optimization, window function efficiency, data skew, and BigQuery best practices.

Respond with valid JSON matching this schema:
{
  "health_score": integer,
  "critical_issues": [{"title": "string", "description": "string", "suggestion": "string"}],
  "warnings": [{"title": "string", "description": "string", "suggestion": "string"}],
  "recommendations": ["string"],
  "optimized_code": "string"
}"""
            try:
                import json
                api_response = self.llm.client.messages.create(
                    model=self.llm.model,
                    max_tokens=4096,
                    system=optimize_prompt,
                    messages=[{"role": "user", "content": f"Analyze this SQL:\n```sql\n{input_code}\n```"}],
                )
                text = api_response.content[0].text.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    text = "\n".join(lines)
                return json.loads(text)
            except Exception as exc:
                logger.warning("Optimize LLM call failed: %s", exc)

        # Rule-based fallback
        return self._rule_based_optimize(input_code)

    def _rule_based_optimize(self, input_code: str) -> dict:
        """Basic rule-based SQL optimization analysis."""
        critical = []
        warnings = []
        recommendations = []
        score = 80

        code_upper = input_code.upper()

        if "SELECT *" in code_upper:
            critical.append({
                "title": "SELECT * Usage",
                "description": "Using SELECT * fetches all columns, increasing data scanned and cost.",
                "suggestion": "Specify only the columns you need: SELECT col1, col2, col3 FROM ...",
            })
            score -= 15

        if "ORDER BY" in code_upper and "LIMIT" not in code_upper:
            warnings.append({
                "title": "ORDER BY Without LIMIT",
                "description": "Sorting entire result sets is expensive on large tables.",
                "suggestion": "Add a LIMIT clause or remove ORDER BY if not needed.",
            })
            score -= 5

        if code_upper.count("JOIN") > 3:
            warnings.append({
                "title": "Multiple JOINs",
                "description": f"Query has {code_upper.count('JOIN')} JOINs which may cause performance issues.",
                "suggestion": "Consider materializing intermediate results or using CTEs.",
            })
            score -= 10

        if "WHERE" not in code_upper and "FROM" in code_upper:
            critical.append({
                "title": "No WHERE Clause",
                "description": "Full table scan without filtering — expensive on large tables.",
                "suggestion": "Add WHERE filters, especially on partition columns.",
            })
            score -= 20

        if "CROSS JOIN" in code_upper:
            critical.append({
                "title": "CROSS JOIN Detected",
                "description": "CROSS JOINs produce cartesian products and are very expensive.",
                "suggestion": "Replace with an appropriate INNER/LEFT JOIN with a ON condition.",
            })
            score -= 20

        if "NOT IN" in code_upper:
            warnings.append({
                "title": "NOT IN Subquery",
                "description": "NOT IN with subqueries can be slow and has NULL handling issues.",
                "suggestion": "Use NOT EXISTS or LEFT JOIN ... WHERE key IS NULL instead.",
            })
            score -= 5

        if "DISTINCT" in code_upper:
            warnings.append({
                "title": "DISTINCT Usage",
                "description": "DISTINCT forces deduplication which can be expensive.",
                "suggestion": "Check if DISTINCT is truly needed or if the data model can be improved.",
            })
            score -= 3

        recommendations.append("Use partitioned tables and filter on partition columns in WHERE clauses.")
        recommendations.append("Leverage clustered tables to improve filter and join performance.")
        recommendations.append("Avoid SELECT * — specify only needed columns to reduce data scanned.")

        score = max(10, min(100, score))

        return {
            "health_score": score,
            "critical_issues": critical,
            "warnings": warnings,
            "recommendations": recommendations,
            "optimized_code": input_code,  # Rule-based can't rewrite, return original
        }

    def get_sample_response(self) -> dict:
        """Legacy fallback."""
        return self._build_empty_response("teradata_to_bigquery")
