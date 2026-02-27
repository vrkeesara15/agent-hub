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

        # Try LLM for intelligent conversion
        if self.llm.client is not None:
            result = await self.call_llm(
                user_message=(
                    f"Convert the following code.\n"
                    f"Mode: {mode}\n"
                    f"Source format: {source_format or 'auto-detect'}\n\n"
                    f"```\n{input_code}\n```"
                    f"{kb_context}"
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

    def get_sample_response(self) -> dict:
        """Legacy fallback."""
        return self._build_empty_response("teradata_to_bigquery")
