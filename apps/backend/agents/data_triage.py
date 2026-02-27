from __future__ import annotations

import logging
import re
from typing import Optional

from agents.base import BaseAgent
from knowledge.store import get_knowledge_store
from knowledge.metadata import format_time_ago

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Data Triage agent for enterprise data quality management.
Your job is to scan SQL files, pipelines, and data references to identify:
1. Deprecated tables that should be migrated
2. Broken references (tables not found)
3. Stale data sources
4. Health status of all referenced tables

For each issue found, provide:
- The table name
- Severity (healthy, warning, alert, critical)
- A descriptive message
- Suggested actions to fix the issue

Use the knowledge base context provided to give real, accurate status information.
Always respond with valid JSON matching the requested schema."""


class DataTriageAgent(BaseAgent):
    name = "Data Triage"
    slug = "data-triage"
    system_prompt = SYSTEM_PROMPT

    def _extract_table_refs(self, sql_content: str) -> list[str]:
        """Extract table references from SQL content."""
        tables: list[str] = []
        patterns = [
            r'(?:FROM|JOIN)\s+[`"]?(\w+(?:\.\w+){0,2})[`"]?',
            r'(?:FROM|JOIN)\s+`([^`]+)`',
            r'(?:INTO)\s+[`"]?(\w+(?:\.\w+){0,2})[`"]?',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, sql_content, re.IGNORECASE)
            tables.extend(matches)

        seen = set()
        unique = []
        for t in tables:
            t_lower = t.lower().strip()
            if t_lower and t_lower not in seen:
                if t_lower not in ("select", "where", "group", "order", "having", "limit", "set", "values"):
                    seen.add(t_lower)
                    unique.append(t)
        return unique

    def _lookup_table_status(self, table_ref: str, store) -> dict:
        """Look up a table in the knowledge base and determine its health status."""
        parts = table_ref.replace("`", "").split(".")
        search_names = [table_ref.replace("`", "")]
        if len(parts) > 1:
            search_names.append(parts[-1])
        if len(parts) > 2:
            search_names.append(f"{parts[-2]}.{parts[-1]}")

        info = None
        for name in search_names:
            info = store.get_table_info(name)
            if info:
                break

        if not info:
            return {
                "name": table_ref,
                "status": "alert",
                "issue": "Not found in knowledge base",
                "info": None,
            }

        status = info.get("status", "").lower()
        health = info.get("health_status", "").lower()
        mod_status = info.get("modernization_status", "").lower()

        if status == "deprecated" or health == "deprecated":
            return {
                "name": table_ref,
                "status": "alert",
                "issue": f"Deprecated{' on ' + info.get('deprecation_date', '') if info.get('deprecation_date') else ''}",
                "info": info,
            }
        elif status in ("not_found", ""):
            if not info.get("gcp_full_path"):
                return {
                    "name": table_ref,
                    "status": "alert",
                    "issue": "Table not found or deleted",
                    "info": info,
                }
        elif status == "staging" or "staging" in table_ref.lower():
            return {
                "name": table_ref,
                "status": "warning",
                "issue": "Staging table — not recommended for production",
                "info": info,
            }
        elif mod_status == "in progress":
            return {
                "name": table_ref,
                "status": "warning",
                "issue": "Modernization in progress — may have incomplete data",
                "info": info,
            }
        elif mod_status == "not started":
            return {
                "name": table_ref,
                "status": "warning",
                "issue": "Not yet modernized — still on legacy platform",
                "info": info,
            }
        elif health == "warning":
            return {
                "name": table_ref,
                "status": "warning",
                "issue": info.get("issue", "Minor issue detected"),
                "info": info,
            }

        return {
            "name": table_ref,
            "status": "healthy",
            "issue": None,
            "info": info,
        }

    async def scan(
        self,
        file_content: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> dict:
        """Scan a file or SQL content for table health issues."""
        store = get_knowledge_store()

        if file_content and file_content.strip():
            table_refs = self._extract_table_refs(file_content)

            if not table_refs:
                return {
                    "filename": filename or "unknown.sql",
                    "tables_found": 0,
                    "tables": [],
                    "issues": [],
                }

            tables = []
            issues = []

            for ref in table_refs:
                result = self._lookup_table_status(ref, store)
                tables.append({
                    "name": result["name"],
                    "status": result["status"],
                    "issue": result["issue"],
                })

                if result["status"] in ("alert", "critical"):
                    info = result.get("info")
                    actions = ["search_similar"]

                    if info and info.get("replacement_table"):
                        message = (
                            f"Table '{ref}' is deprecated. "
                            f"Recommended replacement: {info['replacement_table']}"
                        )
                        actions = ["show_fix", "search_similar"]
                    elif result["issue"] and "not found" in result["issue"].lower():
                        message = f"Table '{ref}' was not found in the knowledge base. It may have been deleted or renamed."
                        actions = ["request_access", "search_similar"]
                    else:
                        message = f"Table '{ref}': {result['issue']}"
                        actions = ["show_fix", "search_similar"]

                    issues.append({
                        "table": ref,
                        "severity": "critical" if "deprecated" in str(result["issue"]).lower() else "warning",
                        "message": message,
                        "actions": actions,
                    })
                elif result["status"] == "warning":
                    issues.append({
                        "table": ref,
                        "severity": "warning",
                        "message": f"Table '{ref}': {result['issue']}",
                        "actions": ["search_similar"],
                    })

            # Try LLM for enhanced analysis if available
            if self.llm.client is not None:
                context_lines = []
                for t in tables:
                    context_lines.append(f"  {t['name']}: status={t['status']}, issue={t['issue']}")
                context = "\n".join(context_lines)

                llm_result = await self.call_llm(
                    user_message=(
                        f"Scan the following file for table health issues.\n"
                        f"Filename: {filename or 'unknown.sql'}\n\n"
                        f"```\n{file_content}\n```\n\n"
                        f"Knowledge Base Table Status:\n{context}"
                    ),
                    response_schema={
                        "filename": "string",
                        "tables_found": "integer",
                        "tables": [{"name": "string", "status": "string", "issue": "string|null"}],
                        "issues": [
                            {
                                "table": "string",
                                "severity": "string",
                                "message": "string",
                                "actions": ["string"],
                            }
                        ],
                    },
                )
                if llm_result is not None:
                    return llm_result

            return {
                "filename": filename or "unknown.sql",
                "tables_found": len(tables),
                "tables": tables,
                "issues": issues,
            }

        # No file content provided — return health overview from KB
        return self._build_health_overview(filename, store)

    def _build_health_overview(self, filename: Optional[str], store) -> dict:
        """Build a health overview from the knowledge base."""
        health_data = store.get_table_health()
        tables = []
        issues = []

        for row in health_data:
            name = row.get("table_name", row.get("gcp_table", ""))
            status = row.get("health_status", row.get("status", "healthy")).lower()
            issue = row.get("issue", None)

            if status in ("deprecated", "not_found"):
                display_status = "alert"
            elif status in ("warning", "staging", "stale"):
                display_status = "warning"
            else:
                display_status = "healthy"

            tables.append({
                "name": name,
                "status": display_status,
                "issue": issue if issue else None,
            })

            if display_status == "alert":
                issues.append({
                    "table": name,
                    "severity": "critical",
                    "message": f"{name}: {issue or 'Issue detected'}",
                    "actions": ["show_fix", "search_similar"],
                })

        return {
            "filename": filename or "knowledge_base_health_check",
            "tables_found": len(tables),
            "tables": tables,
            "issues": issues,
        }

    async def fix(self, table: str, original_code: str) -> dict:
        """Generate a fix suggestion for a specific table issue."""
        store = get_knowledge_store()

        info = store.get_table_info(table)
        replacement_info = None

        if info:
            replacement_name = info.get("replacement_table", "")
            if replacement_name:
                replacement_info = store.get_table_info(replacement_name)

        # Try LLM for intelligent fix
        if self.llm.client is not None and original_code.strip():
            context = ""
            if info:
                context += f"\nProblematic table info: {info}"
            if replacement_info:
                context += f"\nReplacement table info: {replacement_info}"

            llm_result = await self.call_llm(
                user_message=(
                    f"Suggest a fix for the deprecated table reference.\n"
                    f"Table: {table}\n\n"
                    f"Original code:\n```\n{original_code}\n```"
                    f"{context}"
                ),
                response_schema={
                    "explanation": "string",
                    "original_line": "string",
                    "fixed_line": "string",
                    "additional_changes": ["string"],
                },
            )
            if llm_result is not None:
                return llm_result

        return self._build_fix_from_kb(table, original_code, info, replacement_info)

    def _build_fix_from_kb(
        self,
        table: str,
        original_code: str,
        info: Optional[dict],
        replacement_info: Optional[dict],
    ) -> dict:
        """Build a fix suggestion from knowledge base data."""
        if replacement_info:
            rep_path = replacement_info.get("gcp_full_path", "")
            rep_table = replacement_info.get("gcp_table", replacement_info.get("table_name", ""))

            explanation = (
                f"The table {table} is deprecated. "
                f"It has been replaced by {rep_table} in the modernized data warehouse."
            )
            if replacement_info.get("description"):
                explanation += f" {replacement_info['description']}."
            if replacement_info.get("owner_team"):
                explanation += f" Maintained by {replacement_info['owner_team']}."

            table_parts = table.replace("`", "").split(".")
            original_line = f"FROM {table}"
            for line in original_code.split("\n"):
                if any(part.lower() in line.lower() for part in table_parts if len(part) > 3):
                    original_line = line.strip()
                    break

            fixed_line = original_line
            for part in table_parts:
                if part.lower() in fixed_line.lower():
                    fixed_line = re.sub(
                        re.escape(part),
                        f"`{rep_path}`" if rep_path else rep_table,
                        fixed_line,
                        flags=re.IGNORECASE,
                        count=1,
                    )
                    break

            additional = [
                "Verify column names match the new schema",
                "Update any dependent views or downstream queries",
            ]
            if replacement_info.get("partitioned") == "Yes":
                additional.append(
                    f"Note: New table is partitioned by {replacement_info.get('partition_field', 'unknown field')}"
                )

            return {
                "explanation": explanation,
                "original_line": original_line,
                "fixed_line": fixed_line,
                "additional_changes": additional,
            }

        if info:
            return {
                "explanation": (
                    f"The table {table} has issues: {info.get('issue', 'unknown')}. "
                    f"No direct replacement was found in the knowledge base. "
                    f"Contact the {info.get('owner_team', 'data engineering')} team for guidance."
                ),
                "original_line": f"FROM {table}",
                "fixed_line": f"-- TODO: Replace {table} with modernized equivalent",
                "additional_changes": [
                    "Search for alternative tables using the Source of Truth agent",
                    "Contact the data engineering team for the correct replacement",
                ],
            }

        return {
            "explanation": (
                f"The table {table} was not found in the knowledge base. "
                f"It may have been deleted, renamed, or not yet cataloged."
            ),
            "original_line": f"FROM {table}",
            "fixed_line": f"-- TODO: Replace {table} with correct table reference",
            "additional_changes": [
                "Search for the table using the Source of Truth agent",
                "Verify the table name and check for typos",
                "Contact the data engineering team if the table should exist",
            ],
        }

    async def chat(self, message: str, history: list[dict] = None) -> dict:
        """Conversational chat for data health checks."""
        store = get_knowledge_store()
        history = history or []

        # Detect if message looks like SQL
        sql_keywords = ["SELECT", "FROM", "JOIN", "INSERT", "CREATE", "DROP", "ALTER", "WITH"]
        is_sql = any(kw in message.upper() for kw in sql_keywords) and len(message) > 40

        scan_result = None
        if is_sql:
            scan_result = await self.scan(file_content=message, filename="chat_input.sql")
        else:
            table_names = self._extract_table_names_from_text(message)
            if table_names:
                tables = []
                issues = []
                for ref in table_names:
                    result = self._lookup_table_status(ref, store)
                    tables.append({
                        "name": result["name"],
                        "status": result["status"],
                        "issue": result["issue"],
                    })
                    if result["status"] in ("alert", "critical", "warning"):
                        issues.append({
                            "table": ref,
                            "severity": "critical" if result["status"] == "alert" else "warning",
                            "message": f"Table '{ref}': {result['issue']}",
                            "actions": ["show_fix", "search_similar"],
                        })
                scan_result = {
                    "filename": "health_check",
                    "tables_found": len(tables),
                    "tables": tables,
                    "issues": issues,
                }

        # Build KB context
        kb_context = ""
        if scan_result:
            kb_context = f"Scan results: {scan_result.get('tables_found', 0)} tables found.\n"
            for t in scan_result.get("tables", []):
                kb_context += f"  {t['name']}: status={t['status']}, issue={t.get('issue', 'none')}\n"
            if scan_result.get("issues"):
                kb_context += f"\nIssues ({len(scan_result['issues'])}):\n"
                for iss in scan_result["issues"]:
                    kb_context += f"  [{iss['severity']}] {iss['message']}\n"

        # Try LLM
        if self.llm.client is not None:
            chat_system = (
                self.system_prompt
                + "\n\nYou are in CHAT mode. Respond conversationally about data health. "
                "Include scan results in structured_data when available. "
                "Use conversation history for follow-up context.\n\n"
                f"Knowledge Base Context:\n{kb_context}"
            )

            messages = []
            for h in history:
                messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
            messages.append({"role": "user", "content": message})

            try:
                import json
                schema_hint = (
                    "\n\nRespond with valid JSON:\n"
                    '{"response_text": "your conversational response", '
                    '"structured_data": { ...scan response data or null }, '
                    '"data_type": "health_check" or null}'
                )
                api_response = self.llm.client.messages.create(
                    model=self.llm.model,
                    max_tokens=4096,
                    system=chat_system + schema_hint,
                    messages=messages,
                )
                text = api_response.content[0].text.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    text = "\n".join(lines)
                parsed = json.loads(text)
                return parsed
            except Exception as exc:
                logger.warning("Chat LLM call failed: %s", exc)

        # Fallback without LLM
        if scan_result:
            tables_found = scan_result.get("tables_found", 0)
            issues_count = len(scan_result.get("issues", []))
            healthy_count = sum(1 for t in scan_result.get("tables", []) if t["status"] == "healthy")

            text = f"I analyzed {tables_found} table(s). "
            if issues_count > 0:
                text += f"Found {issues_count} issue(s) that need attention. "
            if healthy_count > 0:
                text += f"{healthy_count} table(s) are healthy."

            return {
                "response_text": text,
                "structured_data": scan_result,
                "data_type": "health_check",
            }

        return {
            "response_text": (
                "I couldn't find any tables in your message. "
                "Try mentioning a table name like 'dim_customer' or paste SQL code directly."
            ),
            "structured_data": None,
            "data_type": None,
        }

    def _extract_table_names_from_text(self, message: str) -> list[str]:
        """Extract potential table names from natural language text."""
        terms = []
        patterns = [
            r'`([^`]+)`',
            r'(?:table|check|health|status|of|for)\s+["\']?(\w+(?:\.\w+){0,2})["\']?',
            r'(\w+\.\w+(?:\.\w+)?)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            terms.extend(matches)

        seen = set()
        unique = []
        for t in terms:
            t_lower = t.lower().strip()
            if t_lower not in seen and len(t_lower) > 2:
                if t_lower not in ("the", "for", "and", "this", "that", "with", "from", "check"):
                    seen.add(t_lower)
                    unique.append(t)
        return unique

    def get_sample_scan_response(self, filename: Optional[str] = None) -> dict:
        store = get_knowledge_store()
        return self._build_health_overview(filename, store)

    def get_sample_fix_response(self, table: str) -> dict:
        store = get_knowledge_store()
        info = store.get_table_info(table)
        replacement_info = None
        if info and info.get("replacement_table"):
            replacement_info = store.get_table_info(info["replacement_table"])
        return self._build_fix_from_kb(table, f"FROM {table}", info, replacement_info)
