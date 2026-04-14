from __future__ import annotations

import json
import logging
import re
from typing import Optional

from agents.base import BaseAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sample message code templates (placeholder — replace with real SQL files)
# ---------------------------------------------------------------------------
SAMPLE_TEMPLATES: list[dict] = [
    {
        "id": "mc_welcome_email",
        "name": "Welcome Email",
        "category": "email",
        "channel": "email",
        "description": "Sends a welcome email to newly registered users within 24 hours of signup.",
        "sql": """-- Message Code: MC_WELCOME_EMAIL
-- Description: Welcome email for new user registrations
-- Owner: marketing-team
-- Schedule: Daily 08:00 UTC

WITH new_users AS (
    SELECT
        u.user_id,
        u.email,
        u.first_name,
        u.last_name,
        u.registration_date,
        u.preferred_language,
        u.country_code
    FROM `project.dataset.dim_users` u
    WHERE u.registration_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
      AND u.registration_date < CURRENT_DATE()
      AND u.email_opt_in = TRUE
      AND u.is_active = TRUE
),

exclusions AS (
    SELECT DISTINCT user_id
    FROM `project.dataset.message_log`
    WHERE message_code = 'MC_WELCOME_EMAIL'
      AND send_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
)

SELECT
    nu.user_id,
    nu.email,
    nu.first_name,
    nu.last_name,
    nu.preferred_language,
    nu.country_code,
    'MC_WELCOME_EMAIL' AS message_code,
    CURRENT_TIMESTAMP() AS created_at
FROM new_users nu
LEFT JOIN exclusions ex ON nu.user_id = ex.user_id
WHERE ex.user_id IS NULL;
""",
        "tags": ["onboarding", "new-user", "email", "welcome"],
        "logic_summary": "Selects new users from last 24h who have email opt-in, excludes anyone already sent this message in 30 days.",
    },
    {
        "id": "mc_cart_abandon",
        "name": "Cart Abandonment Reminder",
        "category": "remarketing",
        "channel": "email",
        "description": "Sends a cart abandonment reminder after 2 hours of inactivity.",
        "sql": """-- Message Code: MC_CART_ABANDON
-- Description: Cart abandonment reminder email
-- Owner: growth-team
-- Schedule: Every 2 hours

WITH abandoned_carts AS (
    SELECT
        c.user_id,
        c.cart_id,
        c.created_at AS cart_created,
        c.total_amount,
        c.item_count,
        u.email,
        u.first_name,
        u.preferred_language
    FROM `project.dataset.fact_carts` c
    JOIN `project.dataset.dim_users` u ON c.user_id = u.user_id
    WHERE c.status = 'abandoned'
      AND c.updated_at <= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)
      AND c.updated_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
      AND c.total_amount > 0
      AND u.email_opt_in = TRUE
),

recent_purchases AS (
    SELECT DISTINCT user_id
    FROM `project.dataset.fact_orders`
    WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
),

exclusions AS (
    SELECT DISTINCT user_id
    FROM `project.dataset.message_log`
    WHERE message_code = 'MC_CART_ABANDON'
      AND send_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
)

SELECT
    ac.user_id,
    ac.email,
    ac.first_name,
    ac.cart_id,
    ac.total_amount,
    ac.item_count,
    ac.preferred_language,
    'MC_CART_ABANDON' AS message_code,
    CURRENT_TIMESTAMP() AS created_at
FROM abandoned_carts ac
LEFT JOIN recent_purchases rp ON ac.user_id = rp.user_id
LEFT JOIN exclusions ex ON ac.user_id = ex.user_id
WHERE rp.user_id IS NULL
  AND ex.user_id IS NULL;
""",
        "tags": ["cart", "abandonment", "remarketing", "email"],
        "logic_summary": "Finds carts abandoned 2-24h ago with amount > 0, excludes recent purchasers and users messaged in last 3 days.",
    },
    {
        "id": "mc_push_promo",
        "name": "Promotional Push Notification",
        "category": "promotion",
        "channel": "push",
        "description": "Sends a promotional push notification to eligible users for a campaign.",
        "sql": """-- Message Code: MC_PUSH_PROMO
-- Description: Promotional push notification for active campaigns
-- Owner: campaigns-team
-- Schedule: Campaign-based trigger

WITH eligible_users AS (
    SELECT
        u.user_id,
        u.device_token,
        u.first_name,
        u.preferred_language,
        u.country_code,
        u.user_segment,
        s.last_active_date
    FROM `project.dataset.dim_users` u
    JOIN `project.dataset.user_sessions` s ON u.user_id = s.user_id
    WHERE u.push_opt_in = TRUE
      AND u.is_active = TRUE
      AND u.device_token IS NOT NULL
      AND s.last_active_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
),

campaign_targets AS (
    SELECT
        campaign_id,
        target_segment,
        target_countries,
        start_date,
        end_date
    FROM `project.dataset.dim_campaigns`
    WHERE status = 'active'
      AND CURRENT_DATE() BETWEEN start_date AND end_date
),

exclusions AS (
    SELECT DISTINCT user_id
    FROM `project.dataset.message_log`
    WHERE channel = 'push'
      AND send_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
)

SELECT
    eu.user_id,
    eu.device_token,
    eu.first_name,
    eu.preferred_language,
    ct.campaign_id,
    'MC_PUSH_PROMO' AS message_code,
    CURRENT_TIMESTAMP() AS created_at
FROM eligible_users eu
CROSS JOIN campaign_targets ct
LEFT JOIN exclusions ex ON eu.user_id = ex.user_id
WHERE ex.user_id IS NULL
  AND eu.user_segment IN UNNEST(SPLIT(ct.target_segment, ','))
  AND eu.country_code IN UNNEST(SPLIT(ct.target_countries, ','));
""",
        "tags": ["push", "promotion", "campaign", "notification"],
        "logic_summary": "Targets push-opted-in users active in 30 days matching campaign segment/country, limits to 1 push per day.",
    },
    {
        "id": "mc_sms_otp",
        "name": "SMS OTP Verification",
        "category": "transactional",
        "channel": "sms",
        "description": "Sends OTP verification SMS for high-value transactions.",
        "sql": """-- Message Code: MC_SMS_OTP
-- Description: OTP verification for high-value transactions
-- Owner: security-team
-- Schedule: Real-time trigger

WITH pending_verifications AS (
    SELECT
        v.verification_id,
        v.user_id,
        v.transaction_id,
        v.transaction_amount,
        v.requested_at,
        u.phone_number,
        u.country_code
    FROM `project.dataset.fact_verifications` v
    JOIN `project.dataset.dim_users` u ON v.user_id = u.user_id
    WHERE v.status = 'pending'
      AND v.requested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 MINUTE)
      AND v.transaction_amount >= 500
      AND u.phone_number IS NOT NULL
      AND u.sms_opt_in = TRUE
),

rate_limit AS (
    SELECT user_id, COUNT(*) AS sms_count
    FROM `project.dataset.message_log`
    WHERE message_code = 'MC_SMS_OTP'
      AND send_date = CURRENT_DATE()
    GROUP BY user_id
    HAVING sms_count >= 5
)

SELECT
    pv.user_id,
    pv.phone_number,
    pv.verification_id,
    pv.transaction_id,
    pv.transaction_amount,
    pv.country_code,
    'MC_SMS_OTP' AS message_code,
    CURRENT_TIMESTAMP() AS created_at
FROM pending_verifications pv
LEFT JOIN rate_limit rl ON pv.user_id = rl.user_id
WHERE rl.user_id IS NULL;
""",
        "tags": ["sms", "otp", "verification", "transactional", "security"],
        "logic_summary": "Sends OTP for transactions >= 500, rate limited to 5 SMS/day per user, only pending verifications from last 5 minutes.",
    },
    {
        "id": "mc_reactivation",
        "name": "User Reactivation Campaign",
        "category": "lifecycle",
        "channel": "email",
        "description": "Re-engages dormant users who haven't been active in 30-90 days.",
        "sql": """-- Message Code: MC_REACTIVATION
-- Description: Re-engagement email for dormant users
-- Owner: lifecycle-team
-- Schedule: Weekly Monday 10:00 UTC

WITH dormant_users AS (
    SELECT
        u.user_id,
        u.email,
        u.first_name,
        u.last_name,
        u.preferred_language,
        u.country_code,
        s.last_active_date,
        DATE_DIFF(CURRENT_DATE(), s.last_active_date, DAY) AS days_inactive,
        u.lifetime_value
    FROM `project.dataset.dim_users` u
    JOIN `project.dataset.user_sessions` s ON u.user_id = s.user_id
    WHERE u.email_opt_in = TRUE
      AND u.is_active = TRUE
      AND s.last_active_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
                                  AND DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
),

exclusions AS (
    SELECT DISTINCT user_id
    FROM `project.dataset.message_log`
    WHERE message_code = 'MC_REACTIVATION'
      AND send_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)
)

SELECT
    du.user_id,
    du.email,
    du.first_name,
    du.last_name,
    du.preferred_language,
    du.country_code,
    du.days_inactive,
    du.lifetime_value,
    CASE
        WHEN du.lifetime_value >= 1000 THEN 'high_value'
        WHEN du.lifetime_value >= 200 THEN 'medium_value'
        ELSE 'low_value'
    END AS user_tier,
    'MC_REACTIVATION' AS message_code,
    CURRENT_TIMESTAMP() AS created_at
FROM dormant_users du
LEFT JOIN exclusions ex ON du.user_id = ex.user_id
WHERE ex.user_id IS NULL
ORDER BY du.lifetime_value DESC;
""",
        "tags": ["reactivation", "lifecycle", "dormant", "email", "re-engagement"],
        "logic_summary": "Targets users inactive 30-90 days with email opt-in, segments by lifetime value tier, excludes if messaged in 14 days.",
    },
]

# ---------------------------------------------------------------------------
# In-memory knowledge base for created message codes
# ---------------------------------------------------------------------------
_knowledge_store: list[dict] = []


def get_message_knowledge() -> list[dict]:
    return _knowledge_store


def add_message_knowledge(entry: dict) -> None:
    _knowledge_store.append(entry)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are the Message Code Builder agent. You help developers rapidly create
new message code SQL files by analyzing requirements and finding the best template from the
existing codebase.

Your workflow:
1. Analyze the user's requirements (message type, channel, audience, business rules)
2. Match to the most similar existing template
3. Generate the new SQL with all required modifications
4. Provide an Airflow DAG for scheduling
5. Explain all changes and logic decisions

When generating SQL, follow these conventions:
- Use BigQuery-compatible SQL
- Always include a WITH clause for CTEs (audience, exclusions, rate limiting)
- Always include message_code and created_at in the final SELECT
- Use descriptive CTE names
- Include header comments with message code, description, owner, and schedule
- Follow the exclusion pattern: check message_log for recent sends
- Support opt-in checks appropriate to the channel (email_opt_in, push_opt_in, sms_opt_in)

Always respond with valid JSON matching the requested schema."""


class MessageCodeBuilderAgent(BaseAgent):
    name = "Message Code Builder"
    slug = "message-code-builder"
    system_prompt = SYSTEM_PROMPT

    def _get_all_templates(self) -> list[dict]:
        """Return built-in templates plus any saved knowledge entries."""
        return SAMPLE_TEMPLATES + _knowledge_store

    def _match_template(self, requirements: dict) -> dict:
        """Score each template against requirements and return the best match."""
        templates = self._get_all_templates()
        if not templates:
            return SAMPLE_TEMPLATES[0]

        channel = (requirements.get("channel") or "").lower()
        category = (requirements.get("category") or "").lower()
        description = (requirements.get("description") or "").lower()

        scored: list[tuple[int, dict]] = []
        for t in templates:
            score = 0
            t_channel = (t.get("channel") or "").lower()
            t_category = (t.get("category") or "").lower()
            t_tags = [tag.lower() for tag in (t.get("tags") or [])]
            t_desc = (t.get("description") or "").lower()

            # Channel match is most important
            if channel and channel == t_channel:
                score += 40

            # Category match
            if category and category == t_category:
                score += 30

            # Keyword overlap from description
            desc_words = set(re.findall(r'\w+', description))
            tag_overlap = desc_words & set(t_tags)
            desc_overlap = desc_words & set(re.findall(r'\w+', t_desc))
            score += len(tag_overlap) * 10
            score += len(desc_overlap) * 3

            scored.append((score, t))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    async def analyze_requirements(self, requirements: dict) -> dict:
        """Analyze requirements and recommend the best template."""
        best = self._match_template(requirements)
        all_templates = self._get_all_templates()

        # Score all templates for alternatives
        channel = (requirements.get("channel") or "").lower()
        description = (requirements.get("description") or "").lower()

        alternatives = []
        for t in all_templates:
            if t["id"] == best["id"]:
                continue
            t_channel = (t.get("channel") or "").lower()
            relevance = "low"
            if t_channel == channel:
                relevance = "medium"
            alternatives.append({
                "id": t["id"],
                "name": t["name"],
                "category": t.get("category", ""),
                "channel": t.get("channel", ""),
                "description": t.get("description", ""),
                "relevance": relevance,
            })

        return {
            "recommended_template": {
                "id": best["id"],
                "name": best["name"],
                "category": best.get("category", ""),
                "channel": best.get("channel", ""),
                "description": best.get("description", ""),
                "logic_summary": best.get("logic_summary", ""),
                "sql": best.get("sql", ""),
                "tags": best.get("tags", []),
            },
            "alternatives": alternatives,
            "match_reasoning": self._explain_match(requirements, best),
        }

    def _explain_match(self, requirements: dict, template: dict) -> str:
        reasons = []
        if (requirements.get("channel") or "").lower() == (template.get("channel") or "").lower():
            reasons.append(f"Same channel: {template.get('channel')}")
        if (requirements.get("category") or "").lower() == (template.get("category") or "").lower():
            reasons.append(f"Same category: {template.get('category')}")
        desc_words = set(re.findall(r'\w+', (requirements.get("description") or "").lower()))
        tag_overlap = desc_words & set(t.lower() for t in (template.get("tags") or []))
        if tag_overlap:
            reasons.append(f"Matching tags: {', '.join(tag_overlap)}")
        if not reasons:
            reasons.append("Closest general match based on available templates")
        return "; ".join(reasons)

    async def generate_message_code(self, requirements: dict, template_id: Optional[str] = None) -> dict:
        """Generate the full message code SQL based on requirements and a template."""
        # Find template
        if template_id:
            templates = self._get_all_templates()
            template = next((t for t in templates if t["id"] == template_id), None)
            if not template:
                template = self._match_template(requirements)
        else:
            template = self._match_template(requirements)

        msg_code = requirements.get("message_code", "MC_NEW_MESSAGE")
        msg_name = requirements.get("name", "New Message")
        owner = requirements.get("owner", "team")
        schedule = requirements.get("schedule", "Daily 08:00 UTC")
        channel = requirements.get("channel", "email")
        description = requirements.get("description", "")
        audience_rules = requirements.get("audience_rules", "")
        exclusion_rules = requirements.get("exclusion_rules", "")
        extra_fields = requirements.get("extra_fields", "")

        # Try LLM for intelligent generation
        if self.llm.client is not None:
            llm_prompt = (
                f"Generate a new message code SQL based on this template and requirements.\n\n"
                f"TEMPLATE SQL:\n```sql\n{template['sql']}\n```\n\n"
                f"TEMPLATE LOGIC: {template.get('logic_summary', '')}\n\n"
                f"NEW REQUIREMENTS:\n"
                f"- Message Code: {msg_code}\n"
                f"- Name: {msg_name}\n"
                f"- Description: {description}\n"
                f"- Channel: {channel}\n"
                f"- Owner: {owner}\n"
                f"- Schedule: {schedule}\n"
                f"- Audience Rules: {audience_rules}\n"
                f"- Exclusion Rules: {exclusion_rules}\n"
                f"- Extra Fields Needed: {extra_fields}\n\n"
                f"Generate the new SQL following the same CTE pattern as the template. "
                f"Update all references to match the new message code. "
                f"Adjust the audience CTE based on new audience rules. "
                f"Adjust exclusion window if specified. "
                f"Add any extra fields to the SELECT."
            )
            result = await self.call_llm(
                user_message=llm_prompt,
                response_schema={
                    "sql": "string - the complete new SQL",
                    "changes": [
                        {
                            "section": "string - which CTE or section was changed",
                            "description": "string - what changed and why",
                        }
                    ],
                    "logic_summary": "string - plain English summary of the message code logic",
                    "warnings": ["string - any concerns or review items"],
                },
            )
            if result is not None:
                result["template_used"] = template["id"]
                result["template_name"] = template["name"]
                return result

        # Rule-based fallback: adapt template SQL
        new_sql = template["sql"]
        changes = []

        # Replace message code references
        old_code_match = re.search(r"message_code\s*=\s*'([^']+)'", new_sql)
        old_code = old_code_match.group(1) if old_code_match else "MC_OLD"
        new_sql = new_sql.replace(old_code, msg_code)
        changes.append({"section": "Message Code", "description": f"Replaced '{old_code}' with '{msg_code}'"})

        # Update header comments
        new_sql = re.sub(r'-- Message Code: .*', f'-- Message Code: {msg_code}', new_sql)
        new_sql = re.sub(r'-- Description: .*', f'-- Description: {description or msg_name}', new_sql)
        new_sql = re.sub(r'-- Owner: .*', f'-- Owner: {owner}', new_sql)
        new_sql = re.sub(r'-- Schedule: .*', f'-- Schedule: {schedule}', new_sql)
        changes.append({"section": "Header", "description": "Updated message code, description, owner, and schedule in header comments"})

        # Adjust channel opt-in
        opt_in_map = {
            "email": "email_opt_in",
            "push": "push_opt_in",
            "sms": "sms_opt_in",
        }
        for ch, opt in opt_in_map.items():
            if ch != channel.lower() and opt in new_sql:
                new_opt = opt_in_map.get(channel.lower(), "email_opt_in")
                new_sql = new_sql.replace(opt, new_opt)
                changes.append({"section": "Opt-in", "description": f"Changed {opt} to {new_opt} for {channel} channel"})

        # Update message_code literal in SELECT
        literal_pattern = r"'MC_\w+'\s*AS\s*message_code"
        new_sql = re.sub(literal_pattern, f"'{msg_code}' AS message_code", new_sql)

        logic_summary = (
            f"Adapted from template '{template['name']}'. "
            f"Channel: {channel}. Schedule: {schedule}. "
            f"{description}"
        )

        warnings = []
        if audience_rules:
            warnings.append(f"Custom audience rules requested but not automatically applied: '{audience_rules}'. Please review the audience CTE.")
        if exclusion_rules:
            warnings.append(f"Custom exclusion rules requested: '{exclusion_rules}'. Please verify the exclusions CTE.")

        return {
            "sql": new_sql,
            "changes": changes,
            "logic_summary": logic_summary,
            "warnings": warnings,
            "template_used": template["id"],
            "template_name": template["name"],
        }

    def generate_dag(self, requirements: dict) -> dict:
        """Generate an Airflow DAG for the message code."""
        msg_code = requirements.get("message_code", "MC_NEW_MESSAGE")
        dag_id = msg_code.lower().replace("mc_", "msg_")
        owner = requirements.get("owner", "data-team")
        schedule = requirements.get("schedule", "Daily 08:00 UTC")
        description = requirements.get("description", "")

        # Convert schedule to cron expression
        cron = self._schedule_to_cron(schedule)

        dag_code = f'''"""
DAG: {dag_id}
Message Code: {msg_code}
Description: {description}
Generated by Message Code Builder
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.google.cloud.operators.bigquery import (
    BigQueryInsertJobOperator,
    BigQueryCheckOperator,
)
from airflow.operators.python import PythonOperator

default_args = {{
    "owner": "{owner}",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "start_date": datetime(2024, 1, 1),
}}

with DAG(
    dag_id="{dag_id}",
    default_args=default_args,
    description="{description}",
    schedule_interval="{cron}",
    catchup=False,
    tags=["{msg_code}", "message-code", "{requirements.get('channel', 'email')}"],
) as dag:

    # Step 1: Run the message code query
    run_message_query = BigQueryInsertJobOperator(
        task_id="run_message_query",
        configuration={{
            "query": {{
                "query": open(
                    "/dags/sql/{msg_code.lower()}.sql"
                ).read(),
                "useLegacySql": False,
                "destinationTable": {{
                    "projectId": "your-project",
                    "datasetId": "messaging",
                    "tableId": "{msg_code.lower()}_{{{{ ds_nodash }}}}",
                }},
                "writeDisposition": "WRITE_TRUNCATE",
            }}
        }},
    )

    # Step 2: Validate output has rows
    validate_output = BigQueryCheckOperator(
        task_id="validate_output",
        sql=f"""
            SELECT COUNT(*) > 0
            FROM `your-project.messaging.{msg_code.lower()}_{{{{{{ ds_nodash }}}}}}`
        """,
        use_legacy_sql=False,
    )

    # Step 3: Trigger message dispatch
    def trigger_dispatch(**context):
        """Trigger the messaging platform to send the message code."""
        execution_date = context["ds"]
        print(f"Triggering dispatch for {msg_code} on {{execution_date}}")
        # TODO: Add your messaging platform API call here

    dispatch_messages = PythonOperator(
        task_id="dispatch_messages",
        python_callable=trigger_dispatch,
    )

    run_message_query >> validate_output >> dispatch_messages
'''

        return {
            "dag_code": dag_code,
            "dag_id": dag_id,
            "cron": cron,
            "filename": f"{dag_id}.py",
        }

    def _schedule_to_cron(self, schedule: str) -> str:
        """Convert a human-readable schedule to a cron expression."""
        s = schedule.lower().strip()
        if "real-time" in s or "trigger" in s:
            return "*/5 * * * *"  # every 5 minutes
        if "hourly" in s or "every hour" in s:
            return "0 * * * *"
        if "every 2 hour" in s:
            return "0 */2 * * *"
        if "weekly" in s:
            if "monday" in s:
                return "0 10 * * 1"
            return "0 10 * * 1"
        if "daily" in s:
            # Try to extract time
            time_match = re.search(r'(\d{1,2}):(\d{2})', s)
            if time_match:
                return f"{time_match.group(2)} {time_match.group(1)} * * *"
            return "0 8 * * *"
        return "0 8 * * *"

    def list_templates(self) -> list[dict]:
        """List all available templates."""
        templates = self._get_all_templates()
        return [
            {
                "id": t["id"],
                "name": t["name"],
                "category": t.get("category", ""),
                "channel": t.get("channel", ""),
                "description": t.get("description", ""),
                "tags": t.get("tags", []),
            }
            for t in templates
        ]

    def save_to_knowledge(self, message_code_data: dict) -> dict:
        """Save a generated message code to the knowledge base for future reference."""
        entry = {
            "id": message_code_data.get("message_code", "mc_unknown").lower(),
            "name": message_code_data.get("name", "Unknown"),
            "category": message_code_data.get("category", ""),
            "channel": message_code_data.get("channel", ""),
            "description": message_code_data.get("description", ""),
            "sql": message_code_data.get("sql", ""),
            "tags": message_code_data.get("tags", []),
            "logic_summary": message_code_data.get("logic_summary", ""),
            "owner": message_code_data.get("owner", ""),
            "schedule": message_code_data.get("schedule", ""),
        }
        add_message_knowledge(entry)
        return {"saved": True, "id": entry["id"], "total_templates": len(self._get_all_templates())}

    def get_sample_response(self) -> dict:
        return {"templates": self.list_templates()}
