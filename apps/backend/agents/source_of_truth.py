from __future__ import annotations

import logging
from typing import Optional

from agents.base import BaseAgent
from knowledge.store import get_knowledge_store
from knowledge.metadata import format_row_count, format_time_ago

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Source of Truth agent for a large enterprise data migration platform.
You help users discover table mappings and migration status for the Teradata-to-Google Cloud migration.

Your knowledge base contains 3 key data sources:
1. **UG1 Objects** (304 objects) — Primary migration mapping from Teradata to GCP.
   Each object has: Workstream, TD DB Name, TD Object Name, GCP Workspace, GCP Dataset(s),
   GCP Object Name, Status (Available/Deprecated/Restricted/In Development), Notes, Owner.
2. **Actuals** (1977 rows) — Replication tracking with GCP project/dataset/table,
   BQ View references, UG0/UG1 classification, flip dates, modernized tables, DAG schedules.
3. **Frank Sheet** (5259 rows) — Master inventory with ownership (POC name, org),
   replication decisions (Y/N), priority (P1/P2/P3), frequency, load type,
   usage stats (read/write counts, row counts), object type (View/Table).

When answering questions:
- For migration status questions, check UG1 Objects first (Status field: Available, Deprecated, Restricted, In Development, In DVCF queue)
- For "where is my table in GCP" questions, provide the GCP Workspace + Dataset + Object Name from UG1, and BQ View path from Actuals
- For ownership questions, check Frank Sheet for POC_Name, TableOrgOwner (AID/Non-AID), ProductArea
- For replication/DAG questions, check Actuals for Replication_Dag_Name and schedule
- If a table is Deprecated or Restricted, ALWAYS include the Notes field which explains the reason and alternatives
- For modernization questions, check if Modernized_Table exists in Actuals
- Workstreams include: Home/Prospect/Mobile Infra, VZ Engage, Pricing Enablement, Upgrade Enablement, Performance Management, Acquisition

Use the knowledge base data provided to give accurate, real answers.
Always respond with valid JSON matching the requested schema."""


class SourceOfTruthAgent(BaseAgent):
    name = "Source of Truth"
    slug = "source-of-truth"
    system_prompt = SYSTEM_PROMPT

    async def search(self, query: str) -> dict:
        """Search for the best table matching the user query.

        Uses real knowledge base data. If an LLM API key is configured,
        uses the LLM to intelligently rank and explain results.
        Otherwise, builds the response directly from knowledge base data.
        """
        store = get_knowledge_store()

        # Search knowledge base for matching tables
        kb_results = store.search_tables(query)

        # Also try direct table lookup
        table_info = store.get_table_info(query)

        # If we have an LLM, use it with knowledge base context
        if self.llm.client is not None and (kb_results or table_info):
            context = self._build_context(query, kb_results, table_info, store)
            result = await self.call_llm(
                user_message=(
                    f"Find the best table for: {query}\n\n"
                    f"Knowledge Base Context:\n{context}"
                ),
                response_schema={
                    "recommended": {
                        "table_name": "string",
                        "project": "string",
                        "dataset": "string",
                        "why": ["string"],
                        "stats": {
                            "row_count": "string",
                            "last_updated": "string",
                            "quality_score": "integer",
                        },
                        "modernized": "boolean",
                    },
                    "alternatives": [
                        {
                            "table_name": "string",
                            "status": "warning|deprecated|stale",
                            "reason": "string",
                        }
                    ],
                    "confidence": "high|medium|low",
                },
            )
            if result is not None:
                return result

        # No LLM available or LLM failed — build response from KB data
        if table_info:
            return self._build_response_from_info(table_info, store)

        if kb_results:
            return self._build_response_from_search(query, kb_results, store)

        # Nothing found in knowledge base
        return self._build_not_found_response(query)

    def _build_context(
        self,
        query: str,
        kb_results: list[dict],
        table_info: Optional[dict],
        store,
    ) -> str:
        """Build a context string from knowledge base data for the LLM."""
        parts = []

        if table_info:
            parts.append("Direct table match found:")
            for k, v in table_info.items():
                if v and k != "sources_used":
                    parts.append(f"  {k}: {v}")
            parts.append(f"  Data sources: {', '.join(table_info.get('sources_used', []))}")
            parts.append("")

        if kb_results:
            parts.append(f"Search results ({len(kb_results)} tables found):")
            for i, row in enumerate(kb_results[:10]):
                table_name = (
                    row.get("TD_Object_Name", "")
                    or row.get("GCP_Object_Name", "")
                    or row.get("GCP_Replicated_Table", "")
                    or row.get("tablename", "")
                    or row.get("gcp_table", "")
                    or row.get("table_name", "")
                )
                source = row.get("_source", "unknown")
                parts.append(f"  {i + 1}. {table_name} (from {source})")
                for k, v in row.items():
                    if k.startswith("_") or not v:
                        continue
                    parts.append(f"     {k}: {v}")
                parts.append("")

        # Add DAG info if available
        if table_info:
            dag = store.get_dag_for_table(
                table_info.get("gcp_table", "") or table_info.get("table_name", query)
            )
            if dag:
                parts.append("Pipeline info:")
                for k, v in dag.items():
                    if v:
                        parts.append(f"  {k}: {v}")

        return "\n".join(parts)

    def _build_response_from_info(self, info: dict, store) -> dict:
        """Build a structured response from a direct table info lookup."""
        table_name = info.get("gcp_table", info.get("table_name", ""))
        project = info.get("gcp_project", "")
        dataset = info.get("gcp_dataset", "")

        # Build reasons
        why = []
        status = info.get("status", "")
        if status == "Available":
            why.append("This object is Available and migrated to GCP.")
        elif status == "Deprecated":
            why.append(f"⚠️ This object is DEPRECATED.")
            notes = info.get("notes", "")
            if notes:
                why.append(f"Note: {notes}")
        elif status == "Restricted":
            why.append(f"🔒 This object is RESTRICTED.")
            notes = info.get("notes", "")
            if notes:
                why.append(f"Note: {notes}")
        elif status == "In development":
            why.append("🔧 This object is currently In Development and not yet available.")
            notes = info.get("notes", "")
            if notes:
                why.append(f"Note: {notes}")
        elif status == "In DVCF queue":
            why.append("📋 This object is in the DVCF queue for processing.")

        # Modernization info
        modernized = info.get("modernized_table", "")
        if modernized:
            why.append(f"Modernized table available: {modernized}")

        flipped = info.get("flipped_date", "")
        if flipped:
            why.append(f"Data flipped to production on {flipped}.")

        # Replication info
        dag = info.get("replication_dag", "")
        if dag:
            schedule = info.get("replication_schedule", "")
            why.append(f"Replication DAG: {dag}" + (f" (Schedule: {schedule})" if schedule else ""))

        # Workstream
        workstream = info.get("workstream", "")
        if workstream:
            why.append(f"Workstream: {workstream}")

        # Ownership
        owner = info.get("owner", "")
        poc = info.get("poc_name", "")
        if owner:
            why.append(f"Org owner: {owner}" + (f", POC: {poc}" if poc else ""))
        elif poc:
            why.append(f"POC: {poc}")

        # Notes (if not already added)
        notes = info.get("notes", "")
        if notes and not any(notes in w for w in why):
            why.append(notes)

        if not why:
            why.append("This table was found in the knowledge base.")

        # Build stats
        row_count = info.get("row_count", "")
        if row_count:
            row_count = format_row_count(row_count)
        else:
            row_count = "N/A"

        last_access = info.get("last_access", "")
        if last_access:
            last_updated = last_access
        else:
            last_updated = format_time_ago(info.get("table_create_date", ""))

        read_count = info.get("read_count", "")
        space_gb = info.get("space_gb", "")

        # Check for deprecated tables
        alternatives = []
        if status.lower() == "deprecated":
            # Already handled in why
            pass
        elif status.lower() == "restricted":
            pass

        # Find alternatives
        self._add_alternatives(table_name, info, alternatives, store)

        # Determine confidence
        sources_count = len(info.get("sources_used", []))
        if sources_count >= 3:
            confidence = "high"
        elif sources_count >= 2:
            confidence = "high"
        else:
            confidence = "medium"

        return {
            "recommended": {
                "table_name": f"{dataset}.{table_name}" if dataset else table_name,
                "project": project,
                "dataset": dataset,
                "why": why,
                "stats": {
                    "row_count": row_count,
                    "last_updated": last_updated,
                    "space_gb": space_gb or "N/A",
                    "read_count": read_count or "N/A",
                },
                "modernized": bool(modernized),
            },
            "alternatives": alternatives,
            "confidence": confidence,
        }

    def _build_deprecated_redirect(self, deprecated_info: dict, replacement_info: dict, store) -> dict:
        """Build a response when the user searched for a deprecated table."""
        dep_table = deprecated_info.get("gcp_table", deprecated_info.get("table_name", ""))
        rep_table = replacement_info.get("gcp_table", replacement_info.get("table_name", ""))
        rep_project = replacement_info.get("gcp_project", "")
        rep_dataset = replacement_info.get("gcp_dataset", "")

        why = [
            f"'{dep_table}' is deprecated. Recommending its replacement: '{rep_table}'.",
        ]
        dep_date = deprecated_info.get("deprecation_date", "")
        if dep_date:
            why.append(f"The old table was deprecated on {dep_date}.")

        mod_status = replacement_info.get("modernization_status", "")
        if mod_status == "Completed":
            why.append("The replacement table is fully modernized on GCP BigQuery.")

        owner = replacement_info.get("owner_team", "")
        if owner:
            why.append(f"Owned by {owner}.")

        desc = replacement_info.get("description", "")
        if desc:
            why.append(desc)

        row_count = format_row_count(replacement_info.get("row_count", "0"))
        last_updated = format_time_ago(replacement_info.get("last_modified_date", ""))
        quality_score = 0
        try:
            quality_score = int(replacement_info.get("quality_score", 0))
        except (ValueError, TypeError):
            pass

        return {
            "recommended": {
                "table_name": f"{rep_dataset}.{rep_table}" if rep_dataset else rep_table,
                "project": rep_project,
                "dataset": rep_dataset,
                "why": why,
                "stats": {
                    "row_count": row_count,
                    "last_updated": last_updated,
                    "quality_score": quality_score,
                },
                "modernized": mod_status == "Completed",
            },
            "alternatives": [
                {
                    "table_name": dep_table,
                    "status": "deprecated",
                    "reason": f"Deprecated{' on ' + dep_date if dep_date else ''}. Use {rep_table} instead.",
                }
            ],
            "confidence": "high",
        }

    def _add_alternatives(self, table_name: str, info: dict, alternatives: list, store) -> None:
        """Find and add alternative/deprecated tables related to the recommended one."""
        # Look for deprecated tables that map to this one
        deprecated_tables = store.get_tables_by_status("deprecated")
        for dep in deprecated_tables:
            replacement = dep.get("replacement_table", "").lower()
            dep_name = dep.get("table_name", dep.get("gcp_table", ""))
            if replacement and table_name.lower() in replacement:
                dep_date = dep.get("deprecation_date", "")
                alternatives.append({
                    "table_name": dep_name,
                    "status": "deprecated",
                    "reason": f"Deprecated{' on ' + dep_date if dep_date else ''}. Use the recommended table instead.",
                })

        # Look for staging/raw versions
        staging_tables = store.get_tables_by_status("staging")
        for stg in staging_tables:
            stg_name = stg.get("table_name", stg.get("gcp_table", ""))
            if stg_name:
                alternatives.append({
                    "table_name": stg_name,
                    "status": "warning",
                    "reason": stg.get("issue", "Staging table — not for production use."),
                })

        # Limit to 5 alternatives
        alternatives[:] = alternatives[:5]

    def _build_response_from_search(self, query: str, results: list[dict], store) -> dict:
        """Build response from search results when no exact match was found."""
        # Pick the best result (from highest priority source)
        best = results[0]
        table_name = (
            best.get("gcp_table", "")
            or best.get("table_name", "")
            or best.get("legacy_table", "")
        )

        # Try to get full info for the best match
        full_info = store.get_table_info(table_name)
        if full_info:
            return self._build_response_from_info(full_info, store)

        # Fallback: use what we have from search results
        project = best.get("gcp_project", best.get("project", ""))
        dataset = best.get("gcp_dataset", best.get("dataset", ""))

        why = [f"Best match for '{query}' in the knowledge base."]
        desc = best.get("description", best.get("notes", ""))
        if desc:
            why.append(desc)

        row_count = format_row_count(best.get("row_count", "0"))
        last_updated = format_time_ago(
            best.get("last_modified_date", best.get("last_updated", ""))
        )
        quality_score = 0
        try:
            quality_score = int(best.get("quality_score", 0))
        except (ValueError, TypeError):
            pass

        # Build alternatives from remaining results
        alternatives = []
        for alt in results[1:4]:
            alt_name = (
                alt.get("gcp_table", "")
                or alt.get("table_name", "")
                or alt.get("legacy_table", "")
            )
            alt_status = alt.get("status", alt.get("health_status", "warning"))
            if alt_status not in ("deprecated", "warning", "stale"):
                alt_status = "warning"
            alternatives.append({
                "table_name": alt_name,
                "status": alt_status,
                "reason": alt.get("issue", alt.get("notes", "Consider this alternative table.")),
            })

        return {
            "recommended": {
                "table_name": f"{dataset}.{table_name}" if dataset else table_name,
                "project": project,
                "dataset": dataset,
                "why": why,
                "stats": {
                    "row_count": row_count,
                    "last_updated": last_updated,
                    "quality_score": quality_score,
                },
                "modernized": best.get("modernized", best.get("modernization_status", "")) in ("Yes", "Completed"),
            },
            "alternatives": alternatives,
            "confidence": "medium" if len(results) > 1 else "low",
        }

    def _build_not_found_response(self, query: str) -> dict:
        """Build a response when no table was found in the knowledge base."""
        return {
            "recommended": {
                "table_name": "Not Found",
                "project": "",
                "dataset": "",
                "why": [
                    f"No table matching '{query}' was found in the knowledge base.",
                    "The table may not exist, may not be cataloged yet, or the name may be different.",
                    "Try searching with a different name, or check with the data engineering team.",
                ],
                "stats": {
                    "row_count": "N/A",
                    "last_updated": "N/A",
                    "quality_score": 0,
                },
                "modernized": False,
            },
            "alternatives": [],
            "confidence": "low",
        }

    async def chat(self, message: str, history: list[dict] = None) -> dict:
        """Conversational chat interface for table discovery.

        Accepts natural language, searches the KB, and returns a
        conversational response with optional structured data.
        """
        store = get_knowledge_store()
        history = history or []

        # Extract potential table names / search terms from the message
        search_terms = self._extract_search_terms(message)

        # Search knowledge base for all extracted terms
        kb_results = []
        table_info = None
        for term in search_terms:
            results = store.search_tables(term)
            kb_results.extend(results)
            info = store.get_table_info(term)
            if info and not table_info:
                table_info = info

        # Also try the full message as a search query
        if not kb_results and not table_info:
            kb_results = store.search_tables(message)

        # Build context for LLM
        kb_context = ""
        if table_info:
            kb_context += "Direct table match found:\n"
            for k, v in table_info.items():
                if v and k != "sources_used":
                    kb_context += f"  {k}: {v}\n"

        if kb_results:
            kb_context += f"\nSearch results ({len(kb_results)} tables):\n"
            for i, row in enumerate(kb_results[:8]):
                table_name = (
                    row.get("gcp_table", "")
                    or row.get("table_name", "")
                    or row.get("legacy_table", "")
                )
                kb_context += f"  {i+1}. {table_name}"
                for k, v in row.items():
                    if not k.startswith("_") and v:
                        kb_context += f"  |  {k}: {v}"
                kb_context += "\n"

        # Try LLM for conversational response
        if self.llm.client is not None:
            chat_system = (
                self.system_prompt
                + "\n\nYou are in CHAT mode. Respond conversationally to the user. "
                "When you find matching tables, include their migration status, GCP location, "
                "workstream, owner, and any important notes. "
                "If a table is Deprecated or Restricted, ALWAYS highlight the Notes which contain "
                "important instructions about alternatives. "
                "If the user asks a follow-up, use the conversation history for context.\n\n"
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
                    '"structured_data": { ...search response data or null }, '
                    '"data_type": "table_recommendation" or null}'
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

        # Fallback: build response from KB data without LLM
        if table_info:
            search_result = self._build_response_from_info(table_info, store)
            return {
                "response_text": self._build_text_response(table_info, search_terms),
                "structured_data": search_result,
                "data_type": "table_recommendation",
            }

        if kb_results:
            search_result = self._build_response_from_search(
                search_terms[0] if search_terms else message, kb_results, store
            )
            return {
                "response_text": f"I found {len(kb_results)} matching table(s) in the knowledge base for your query.",
                "structured_data": search_result,
                "data_type": "table_recommendation",
            }

        return {
            "response_text": (
                f"I couldn't find any tables matching your query. "
                f"Try a different table name or check with the data engineering team."
            ),
            "structured_data": None,
            "data_type": None,
        }

    def _extract_search_terms(self, message: str) -> list[str]:
        """Extract potential table/object names from a natural language message.
        Handles patterns like:
          - billing_dim_6131 (underscore-separated with numeric suffix)
          - FIN_CORE_164 (database names)
          - FIN_CORE_164.billing_dim_6131 (fully qualified)
          - vz-it-pr-gk1v-bizdo-0.ntl_prd_qmtbls.table_name (BQ paths)
        """
        import re
        terms = []
        # Match backtick-quoted names
        terms.extend(re.findall(r'`([^`]+)`', message))
        # Match fully qualified BQ paths (project.dataset.table)
        terms.extend(re.findall(r'([\w-]+\.[\w-]+\.[\w-]+)', message))
        # Match database.table patterns (e.g., FIN_CORE_164.billing_dim_6131)
        terms.extend(re.findall(r'(\w+\.\w+)', message))
        # Match object name patterns (word_word_digits)
        terms.extend(re.findall(r'\b([a-zA-Z]+_[a-zA-Z]+_\d{3,})\b', message))
        # Match database name patterns (WORD_WORD_digits)
        terms.extend(re.findall(r'\b([A-Z]+_[A-Z]+_\d+)\b', message))
        # Match after keywords like "table", "object", "for", etc.
        terms.extend(re.findall(
            r'(?:table|object|for|of|called|named|status of|find|where is|look up)\s+["\']?(\w+(?:[._]\w+)*)["\']?',
            message, re.IGNORECASE
        ))

        # Deduplicate while preserving order
        seen = set()
        unique = []
        stop_words = {"the", "for", "and", "this", "that", "with", "from",
                       "check", "what", "where", "status", "table", "object",
                       "find", "look", "tell", "about", "show"}
        for t in terms:
            t_lower = t.lower().strip()
            if t_lower not in seen and len(t_lower) > 3 and t_lower not in stop_words:
                seen.add(t_lower)
                unique.append(t)
        return unique

    def _build_text_response(self, info: dict, search_terms: list[str]) -> str:
        """Build a conversational text response from table info."""
        table_name = info.get("gcp_table", info.get("table_name", ""))
        legacy_table = info.get("legacy_table", "")
        gcp_path = info.get("gcp_full_path", "")
        project = info.get("gcp_project", "")
        dataset = info.get("gcp_dataset", "")
        status = info.get("status", "")

        parts = [f"I found **{table_name}**"]
        if legacy_table and legacy_table != table_name:
            parts.append(f"(Teradata source: {legacy_table})")
        if gcp_path:
            parts.append(f"in GCP at `{gcp_path}`")
        elif project:
            parts.append(f"(project: {project}, dataset: {dataset})")
        parts.append(".")

        if status == "Available":
            parts.append("Status: ✅ Available in GCP.")
        elif status == "Deprecated":
            parts.append("Status: ⚠️ Deprecated.")
            notes = info.get("notes", "")
            if notes:
                parts.append(f"Note: {notes}")
        elif status == "Restricted":
            parts.append("Status: 🔒 Restricted.")
            notes = info.get("notes", "")
            if notes:
                parts.append(f"Note: {notes}")
        elif status == "In development":
            parts.append("Status: 🔧 In Development.")

        modernized = info.get("modernized_table", "")
        if modernized:
            parts.append(f"Modernized table: {modernized}.")

        owner = info.get("owner", "")
        if owner:
            parts.append(f"Org: {owner}.")

        workstream = info.get("workstream", "")
        if workstream:
            parts.append(f"Workstream: {workstream}.")

        return " ".join(parts)

    def get_sample_response(self) -> dict:
        """Legacy fallback — should not be reached with new KB system."""
        return self._build_not_found_response("unknown")
