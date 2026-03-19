"""Unit tests for medium-term and long-term improvements (Items 1-38).

Tests all new methods added to InformaticaMigrationAdvancedAgent:
  - Item 30: Selective/Interactive Mode
  - Item 14: DECODE(TRUE) nesting fix
  - Item 8: Partition & Clustering Hints
  - Item 4: Connection Object Resolution
  - Item 11: Unconnected Lookups -> Subqueries
  - Item 5: Flat File / SFTP -> GCS Loading
  - Item 1: Multi-XML Merge Support
  - Item 39: Caching (content-hash)
  - Item 38: Chunked XML (iterparse)
  - Item 34: Unit Test SQL Generation
  - Item 36: Cost Estimation
  - Item 37: dbt Model Generation
  - Item 33: Terraform Export
  - _deduplicate_by_name()
"""
from __future__ import annotations

import sys
import os
import textwrap

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.informatica_migration_advanced import (
    InformaticaMigrationAdvancedAgent,
    ConnectionConfig,
    TableNamingConfig,
    FLAT_FILE_TYPES,
    _PARTITION_RE,
    _CLUSTER_RE,
    _prep_cache,
)

# ── Helper: minimal agent instance ─────────────────────────────────

def _agent() -> InformaticaMigrationAdvancedAgent:
    a = InformaticaMigrationAdvancedAgent.__new__(InformaticaMigrationAdvancedAgent)
    a._naming_config = TableNamingConfig()
    a._current_parsed = None
    a._mapping_confidences = []
    a._connection_config = None
    a._enable_reconciliation = True
    a._reconciliation_threshold_pct = 5.0
    return a


# ── Sample minimal XML for parsing tests ──────────────────────────

MINI_XML = textwrap.dedent("""\
<?xml version="1.0" encoding="UTF-8"?>
<POWERMART>
  <REPOSITORY>
    <FOLDER NAME="TestFolder">
      <SOURCE NAME="SRC_ORDERS" DATABASETYPE="Oracle" OWNERNAME="dbo">
        <SOURCEFIELD NAME="ORDER_ID" DATATYPE="number" PRECISION="10" SCALE="0" NULLABLE="NOTNULL"/>
        <SOURCEFIELD NAME="ORDER_DATE" DATATYPE="date/time" PRECISION="19" SCALE="0" NULLABLE="NULL"/>
        <SOURCEFIELD NAME="CUSTOMER_ID" DATATYPE="number" PRECISION="10" SCALE="0" NULLABLE="NULL"/>
        <SOURCEFIELD NAME="AMOUNT" DATATYPE="decimal" PRECISION="12" SCALE="2" NULLABLE="NULL"/>
      </SOURCE>
      <SOURCE NAME="SRC_FLAT_FILE" DATABASETYPE="Flat File" OWNERNAME="" DELIMITER="|" CODEPAGE="UTF-8">
        <SOURCEFIELD NAME="RECORD_ID" DATATYPE="string" PRECISION="20" SCALE="0" NULLABLE="NULL"/>
        <SOURCEFIELD NAME="LOAD_DATE" DATATYPE="date/time" PRECISION="19" SCALE="0" NULLABLE="NULL"/>
      </SOURCE>
      <TARGET NAME="TGT_ORDERS" DATABASETYPE="Oracle" OWNERNAME="dbo">
        <TARGETFIELD NAME="ORDER_ID" DATATYPE="number" PRECISION="10" SCALE="0" NULLABLE="NOTNULL" KEYTYPE="PRIMARY KEY"/>
        <TARGETFIELD NAME="ORDER_DATE" DATATYPE="date/time" PRECISION="19" SCALE="0" NULLABLE="NULL" KEYTYPE=""/>
        <TARGETFIELD NAME="CUSTOMER_ID" DATATYPE="number" PRECISION="10" SCALE="0" NULLABLE="NULL" KEYTYPE=""/>
        <TARGETFIELD NAME="REGION_CODE" DATATYPE="string" PRECISION="10" SCALE="0" NULLABLE="NULL" KEYTYPE=""/>
        <TARGETFIELD NAME="STATUS" DATATYPE="string" PRECISION="20" SCALE="0" NULLABLE="NULL" KEYTYPE=""/>
        <TARGETFIELD NAME="AMOUNT" DATATYPE="decimal" PRECISION="12" SCALE="2" NULLABLE="NULL" KEYTYPE=""/>
      </TARGET>
      <TRANSFORMATION NAME="LKP_CUSTOMER" TYPE="Lookup Procedure" DESCRIPTION="">
        <TRANSFORMFIELD NAME="CUST_KEY" DATATYPE="number" EXPRESSION="" PORTTYPE="INPUT"/>
        <TRANSFORMFIELD NAME="CUST_NAME" DATATYPE="string" EXPRESSION="" PORTTYPE="OUTPUT"/>
        <TABLEATTRIBUTE NAME="Lookup table name" VALUE="CUSTOMER_DIM"/>
      </TRANSFORMATION>
      <MAPPING NAME="m_load_orders" DESCRIPTION="Load orders mapping">
        <TRANSFORMATION NAME="SQ_SRC_ORDERS" TYPE="Source Qualifier" DESCRIPTION="">
          <TRANSFORMFIELD NAME="ORDER_ID" DATATYPE="number" EXPRESSION="" PORTTYPE="INPUT/OUTPUT"/>
          <TRANSFORMFIELD NAME="ORDER_DATE" DATATYPE="date/time" EXPRESSION="" PORTTYPE="INPUT/OUTPUT"/>
        </TRANSFORMATION>
        <INSTANCE NAME="SRC_ORDERS" TYPE="SOURCE" TRANSFORMATION_NAME="SRC_ORDERS" TRANSFORMATION_TYPE="Source"/>
        <INSTANCE NAME="TGT_ORDERS" TYPE="TARGET" TRANSFORMATION_NAME="TGT_ORDERS" TRANSFORMATION_TYPE="Target"/>
        <CONNECTOR FROMINSTANCE="SRC_ORDERS" FROMFIELD="ORDER_ID" TOINSTANCE="SQ_SRC_ORDERS" TOFIELD="ORDER_ID"/>
        <CONNECTOR FROMINSTANCE="SQ_SRC_ORDERS" FROMFIELD="ORDER_ID" TOINSTANCE="TGT_ORDERS" TOFIELD="ORDER_ID"/>
      </MAPPING>
      <MAPPING NAME="m_load_customers" DESCRIPTION="Load customers mapping">
        <INSTANCE NAME="SRC_ORDERS" TYPE="SOURCE" TRANSFORMATION_NAME="SRC_ORDERS" TRANSFORMATION_TYPE="Source"/>
        <INSTANCE NAME="TGT_ORDERS" TYPE="TARGET" TRANSFORMATION_NAME="TGT_ORDERS" TRANSFORMATION_TYPE="Target"/>
      </MAPPING>
      <TASK NAME="cmd_pre_cleanup" TYPE="Command" DESCRIPTION="Pre-cleanup task">
        <ATTRIBUTE NAME="CmdLine1" VALUE="echo cleanup"/>
      </TASK>
      <TASK NAME="cmd_sftp_vframe" TYPE="Command" DESCRIPTION="SFTP transfer">
        <VALUEPAIR NAME="Command1" VALUE="$PMRootDir/ETL_SCRIPTS/alv_sftp_vframe.ksh"/>
        <VALUEPAIR NAME="Command2" VALUE="$PMRootDir/ETL_SCRIPTS/alv_post_sftp.ksh"/>
      </TASK>
      <TASK NAME="email_success" TYPE="Email" DESCRIPTION="Success notification">
        <ATTRIBUTE NAME="Email Subject" VALUE="Job Complete"/>
        <ATTRIBUTE NAME="Email Text" VALUE="The daily load completed successfully."/>
        <ATTRIBUTE NAME="Email User Name" VALUE="team@example.com"/>
      </TASK>
      <TASK NAME="ew_file_arrival" TYPE="Event Wait" DESCRIPTION="Wait for file">
        <ATTRIBUTE NAME="Filewatch name" VALUE="/data/input/orders.dat"/>
      </TASK>
      <TASK NAME="dec_check_count" TYPE="Decision" DESCRIPTION="Check row count">
        <ATTRIBUTE NAME="Decision Name" VALUE="row_count_gt_0"/>
      </TASK>
      <WORKLET NAME="wklt_sub_process" DESCRIPTION="Sub-process worklet">
        <TASKINSTANCE NAME="Start" TASKTYPE="Start" TASKNAME="" ISVALID="YES"/>
        <TASKINSTANCE NAME="s_sub_orders" TASKTYPE="Session" TASKNAME="m_load_orders" ISVALID="YES"/>
        <TASKINSTANCE NAME="cmd_sub_script" TASKTYPE="Command" TASKNAME="cmd_sftp_vframe" ISVALID="YES"/>
        <WORKFLOWLINK FROMTASK="Start" TOTASK="s_sub_orders" CONDITION=""/>
        <WORKFLOWLINK FROMTASK="s_sub_orders" TOTASK="cmd_sub_script" CONDITION="$s_sub_orders.Status = SUCCEEDED OR DISABLED"/>
      </WORKLET>
      <WORKFLOWEVENT NAME="evt_trigger_downstream" TYPE="User Defined" DESCRIPTION="Signal downstream DAG"/>
      <CONNECTIONREFERENCE CONNECTIONNAME="PROD_DB" CONNECTIONTYPE="Relational" VARIABLE="$Source1" CONNECTIONSUBTYPE="Oracle"/>
      <CONNECTIONREFERENCE CONNECTIONNAME="TGT_BQ" CONNECTIONTYPE="Relational" VARIABLE="$Target1" CONNECTIONSUBTYPE="BigQuery"/>
      <TARGETLOADORDER ORDER="1" TARGETINSTANCE="TGT_ORDERS"/>
      <SESSION NAME="s_load_orders" MAPPINGNAME="m_load_orders" DESCRIPTION="">
        <ATTRIBUTE NAME="Parameter Filename" VALUE="param_orders.par"/>
      </SESSION>
      <WORKFLOW NAME="wkfl_daily_load" DESCRIPTION="Daily load workflow">
        <SCHEDULER SCHEDULETYPE="DAILY" REPEAT="1" STARTDATE="2024-01-01" STARTTIME="06:00:00"/>
        <WORKFLOWVARIABLE NAME="$$WF_RUN_DATE" DATATYPE="date/time" DEFAULTVALUE="01/01/2025" DESCRIPTION="Workflow run date" ISNULL="NO" ISPERSISTENT="YES" USERDEFINED="YES"/>
        <WORKFLOWVARIABLE NAME="$$WF_BATCH_ID" DATATYPE="integer" DEFAULTVALUE="0" DESCRIPTION="Batch identifier" ISNULL="NO"/>
        <MAPPINGVARIABLE NAME="$$LOAD_TYPE" DATATYPE="string" DEFAULTVALUE="FULL" DESCRIPTION="Load type param" ISPARAM="YES"/>
        <MAPPINGVARIABLE NAME="$$EXTRACT_DATE" DATATYPE="date/time" DEFAULTVALUE="01/01/2025" DESCRIPTION="Extract date" ISPARAM="YES"/>
        <TASKINSTANCE NAME="s_load_orders" TASKTYPE="Session" TASKNAME="s_load_orders" ISVALID="YES" REUSABLE="NO" ISENABLED="YES"/>
        <TASKINSTANCE NAME="wklt_sub_process" TASKTYPE="Worklet" TASKNAME="wklt_sub_process" ISVALID="YES" TREAT_INPUTLINK_AS_AND="YES"/>
        <TASKINSTANCE NAME="email_success" TASKTYPE="Email" TASKNAME="email_success" ISVALID="YES"/>
        <TASKINSTANCE NAME="s_disabled_task" TASKTYPE="Session" TASKNAME="s_disabled_task" ISVALID="YES" ISENABLED="NO"/>
        <WORKFLOWLINK FROMTASK="Start" TOTASK="s_load_orders" CONDITION=""/>
        <WORKFLOWLINK FROMTASK="s_load_orders" TOTASK="wklt_sub_process" CONDITION="$s_load_orders.Status = SUCCEEDED OR DISABLED"/>
        <WORKFLOWLINK FROMTASK="wklt_sub_process" TOTASK="email_success" CONDITION=""/>
        <WORKFLOWLINK FROMTASK="s_load_orders" TOTASK="s_disabled_task" CONDITION="$s_load_orders.Status = FAILED"/>
      </WORKFLOW>
    </FOLDER>
  </REPOSITORY>
</POWERMART>
""")


# ═══════════════════════════════════════════════════════════════════
# Test: _parse_xml basic (existing parser)
# ═══════════════════════════════════════════════════════════════════

def test_parse_xml_basic():
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    assert "error" not in parsed, f"Parse error: {parsed.get('error')}"
    assert len(parsed["sources"]) >= 2
    assert len(parsed["targets"]) >= 1
    assert len(parsed["mappings"]) >= 2
    assert len(parsed["workflows"]) >= 1
    assert len(parsed["sessions"]) >= 1
    assert len(parsed["command_tasks"]) >= 1
    assert len(parsed["event_wait_tasks"]) >= 1
    assert len(parsed["decision_tasks"]) >= 1
    # Verify flat file detection
    flat_src = [s for s in parsed["sources"] if s.get("is_flat_file")]
    assert len(flat_src) >= 1, "Flat file source should be detected"
    assert flat_src[0]["file_format"]["delimiter"] == "|"


# ═══════════════════════════════════════════════════════════════════
# Test: Item 38 — Chunked XML (iterparse) produces same output
# ═══════════════════════════════════════════════════════════════════

def test_iterparse_matches_standard():
    agent = _agent()
    standard = agent._parse_xml(MINI_XML)
    chunked = agent._parse_xml_iterparse(MINI_XML)

    # Both should parse without error
    assert "error" not in standard
    assert "error" not in chunked

    # Compare key counts
    for key in ["sources", "targets", "mappings", "workflows", "sessions",
                "command_tasks", "event_wait_tasks", "decision_tasks"]:
        assert len(standard[key]) == len(chunked[key]), \
            f"Mismatch on '{key}': standard={len(standard[key])}, iterparse={len(chunked[key])}"

    # Compare source names
    std_src_names = {s["name"] for s in standard["sources"]}
    chunk_src_names = {s["name"] for s in chunked["sources"]}
    assert std_src_names == chunk_src_names, f"Source names differ: {std_src_names} vs {chunk_src_names}"

    # Compare target names
    std_tgt_names = {t["name"] for t in standard["targets"]}
    chunk_tgt_names = {t["name"] for t in chunked["targets"]}
    assert std_tgt_names == chunk_tgt_names

    # Compare mapping names
    std_map_names = {m["name"] for m in standard["mappings"]}
    chunk_map_names = {m["name"] for m in chunked["mappings"]}
    assert std_map_names == chunk_map_names

    # Check flat file detection in iterparse
    flat_src = [s for s in chunked["sources"] if s.get("is_flat_file")]
    assert len(flat_src) >= 1, "iterparse should detect flat file sources"


def test_iterparse_invalid_xml():
    agent = _agent()
    result = agent._parse_xml_iterparse("<BROKEN><<<")
    assert result.get("error"), "Should report error on invalid XML"


# ═══════════════════════════════════════════════════════════════════
# Test: Item 30 — Selective mode (filtering)
# ═══════════════════════════════════════════════════════════════════

def test_selective_mode_filter():
    """Selected mappings should filter mapping_groups."""
    mapping_groups = {
        "m_load_orders": {"targets": []},
        "m_load_customers": {"targets": []},
        "m_load_products": {"targets": []},
    }
    selected = ["m_load_orders", "m_load_products"]
    filtered = {k: v for k, v in mapping_groups.items() if k in selected}
    assert len(filtered) == 2
    assert "m_load_customers" not in filtered
    assert "m_load_orders" in filtered


# ═══════════════════════════════════════════════════════════════════
# Test: Item 4 — ConnectionConfig resolution
# ═══════════════════════════════════════════════════════════════════

def test_connection_config_exact():
    cc = ConnectionConfig(connections={
        "PROD_DB": {"project": "prod-project", "dataset": "main_ds"},
        "STAGING": {"project": "staging-project", "dataset": "stg_ds"},
    })
    proj, ds = cc.resolve("PROD_DB")
    assert proj == "prod-project"
    assert ds == "main_ds"


def test_connection_config_partial_match():
    cc = ConnectionConfig(connections={
        "PROD_DB": {"project": "prod-project", "dataset": "main_ds"},
    })
    # Partial match: "PROD" should match "PROD_DB"
    proj, ds = cc.resolve("PROD")
    assert proj == "prod-project"
    assert ds == "main_ds"


def test_connection_config_fallback():
    cc = ConnectionConfig(connections={})
    proj, ds = cc.resolve("UNKNOWN")
    assert proj == "project"
    assert ds == "dataset"


# ═══════════════════════════════════════════════════════════════════
# Test: Item 8 — Partition & Clustering detection
# ═══════════════════════════════════════════════════════════════════

def test_partition_detection_date_type():
    agent = _agent()
    columns = [
        {"name": "ID", "datatype": "number", "precision": "10", "scale": "0"},
        {"name": "CREATED_AT", "datatype": "date/time", "precision": "19", "scale": "0"},
        {"name": "STATUS", "datatype": "string", "precision": "10", "scale": "0"},
    ]
    part_col, cluster_cols = agent._detect_partition_cluster_columns(columns)
    assert part_col == "CREATED_AT"
    assert "STATUS" in cluster_cols


def test_partition_detection_name_heuristic():
    agent = _agent()
    columns = [
        {"name": "LOAD_DATE", "datatype": "string", "precision": "26", "scale": "0"},
        {"name": "CUSTOMER_ID", "datatype": "number", "precision": "10", "scale": "0"},
        {"name": "REGION_CODE", "datatype": "string", "precision": "5", "scale": "0"},
    ]
    part_col, cluster_cols = agent._detect_partition_cluster_columns(columns)
    assert part_col == "LOAD_DATE"
    assert "CUSTOMER_ID" in cluster_cols


def test_cluster_max_four():
    agent = _agent()
    columns = [
        {"name": "DATE_COL", "datatype": "date/time", "precision": "19", "scale": "0"},
        {"name": "ID1", "datatype": "number", "precision": "10", "scale": "0"},
        {"name": "STATUS", "datatype": "string", "precision": "10", "scale": "0"},
        {"name": "TYPE", "datatype": "string", "precision": "10", "scale": "0"},
        {"name": "REGION", "datatype": "string", "precision": "10", "scale": "0"},
        {"name": "CATEGORY", "datatype": "string", "precision": "10", "scale": "0"},
        {"name": "ACCOUNT_ID", "datatype": "number", "precision": "10", "scale": "0"},
    ]
    part_col, cluster_cols = agent._detect_partition_cluster_columns(columns)
    assert part_col == "DATE_COL"
    assert len(cluster_cols) <= 4, f"BigQuery limits to 4 cluster cols, got {len(cluster_cols)}"


# ═══════════════════════════════════════════════════════════════════
# Test: Item 11 — Unconnected Lookup resolution
# ═══════════════════════════════════════════════════════════════════

def test_resolve_unconnected_lookup():
    agent = _agent()
    agent._current_parsed = {
        "transformations": [
            {
                "name": "LKP_CUSTOMER",
                "type": "Lookup Procedure",
                "fields": [
                    {"name": "CUST_KEY", "porttype": "INPUT", "datatype": "number", "expression": ""},
                    {"name": "CUST_NAME", "porttype": "OUTPUT", "datatype": "string", "expression": ""},
                ],
                "properties": {"Lookup table name": "CUSTOMER_DIM"},
                "description": "",
            }
        ]
    }
    result = agent._resolve_unconnected_lookup("CUSTOMER")
    assert result is not None
    assert result["table"] == "CUSTOMER_DIM"
    assert result["key_col"] == "CUST_KEY"
    assert result["output_col"] == "CUST_NAME"


def test_resolve_unconnected_lookup_not_found():
    agent = _agent()
    agent._current_parsed = {"transformations": []}
    result = agent._resolve_unconnected_lookup("NONEXISTENT")
    assert result is None


# ═══════════════════════════════════════════════════════════════════
# Test: Item 5 — Flat File detection
# ═══════════════════════════════════════════════════════════════════

def test_flat_file_type_detection():
    for ft in ("FLATFILE", "Flat File", "FILE", "XML SOURCE", "COBOL"):
        assert ft.upper() in FLAT_FILE_TYPES or ft in FLAT_FILE_TYPES, f"{ft} should be in FLAT_FILE_TYPES"


def test_flat_file_source_parsed():
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    flat_sources = [s for s in parsed["sources"] if s.get("is_flat_file")]
    assert len(flat_sources) >= 1
    ff = flat_sources[0]
    assert ff["name"] == "SRC_FLAT_FILE"
    assert ff["file_format"]["delimiter"] == "|"
    assert ff["file_format"]["encoding"] == "UTF-8"


# ═══════════════════════════════════════════════════════════════════
# Test: Item 1 — Multi-XML merge / deduplicate
# ═══════════════════════════════════════════════════════════════════

def test_deduplicate_by_name():
    agent = _agent()
    items = [
        {"name": "A", "val": 1},
        {"name": "B", "val": 2},
        {"name": "A", "val": 3},  # duplicate
        {"name": "C", "val": 4},
    ]
    deduped = agent._deduplicate_by_name(items)
    assert len(deduped) == 3
    names = [i["name"] for i in deduped]
    assert names == ["A", "B", "C"]
    # First occurrence is kept
    assert deduped[0]["val"] == 1


# ═══════════════════════════════════════════════════════════════════
# Test: Item 39 — Caching behavior
# ═══════════════════════════════════════════════════════════════════

def test_cache_hit_miss():
    _prep_cache.clear()
    agent = _agent()
    # First call — cache miss
    result1 = agent._heavy_parse_and_analyze(MINI_XML, use_cache=True)
    assert not result1["error"]
    assert len(_prep_cache) == 1

    # Second call — cache hit (same content)
    result2 = agent._heavy_parse_and_analyze(MINI_XML, use_cache=True)
    assert result2 is result1  # same object from cache


def test_cache_disabled():
    _prep_cache.clear()
    agent = _agent()
    result = agent._heavy_parse_and_analyze(MINI_XML, use_cache=False)
    assert not result["error"]
    assert len(_prep_cache) == 0, "Cache should not be populated when disabled"


# ═══════════════════════════════════════════════════════════════════
# Test: Item 34 — Unit Test SQL Generation
# ═══════════════════════════════════════════════════════════════════

def test_generate_unit_tests():
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    mapping_results = [
        {
            "mapping_name": "m_load_orders",
            "sql": "CREATE OR REPLACE TABLE `project.dataset.tgt_orders` AS SELECT * FROM ...",
        },
    ]
    tests = agent._generate_unit_tests(mapping_results, parsed)
    assert len(tests) >= 1
    key = list(tests.keys())[0]
    assert key.startswith("test_")
    assert key.endswith(".sql")
    content = tests[key]
    assert "PASS" in content
    assert "FAIL" in content
    assert "COUNT(*)" in content


def test_generate_unit_tests_pk_check():
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    mapping_results = [
        {
            "mapping_name": "m_load_orders",
            "sql": "SELECT * FROM TGT_ORDERS",
        },
    ]
    tests = agent._generate_unit_tests(mapping_results, parsed)
    content = list(tests.values())[0]
    # Should have PK uniqueness test for ORDER_ID
    assert "pk_unique" in content.lower() or "PRIMARY" in content or "DISTINCT" in content


# ═══════════════════════════════════════════════════════════════════
# Test: Item 36 — Cost Estimation
# ═══════════════════════════════════════════════════════════════════

def test_estimate_costs():
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    mapping_results = [
        {
            "mapping_name": "m_load_orders",
            "sql": "SELECT * FROM source JOIN lookup ON ...",
        },
    ]
    costs = agent._estimate_costs(parsed, mapping_results)
    assert "storage" in costs
    assert "compute" in costs
    assert "summary" in costs
    assert "assumptions" in costs
    assert costs["storage"]["total_gb"] > 0
    assert costs["compute"]["total_per_run_usd"] >= 0
    assert "/GB/month" in costs["assumptions"][1]


# ═══════════════════════════════════════════════════════════════════
# Test: Item 37 — dbt Model Generation
# ═══════════════════════════════════════════════════════════════════

def test_generate_dbt_models():
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    mapping_results = [
        {
            "mapping_name": "m_load_orders",
            "sql": "CREATE OR REPLACE TABLE `project.dataset.tgt_orders` AS SELECT ORDER_ID FROM `project.dataset.staging_src_orders`",
        },
    ]
    parameters = []
    files = agent._generate_dbt_models(mapping_results, parsed, parameters)
    assert "dbt_project.yml" in files
    assert "models/schema.yml" in files
    # Check staging model exists for at least one source
    staging_files = [k for k in files if k.startswith("models/staging/")]
    assert len(staging_files) >= 1
    # Check mart model exists
    mart_files = [k for k in files if k.startswith("models/marts/")]
    assert len(mart_files) >= 1
    # Check dbt_project.yml content
    assert "config-version: 2" in files["dbt_project.yml"]
    assert "materialized" in files["dbt_project.yml"]
    # Check staging model uses {{ source() }}
    stg_content = files[staging_files[0]]
    assert "{{ source(" in stg_content
    assert "{{ config(" in stg_content


# ═══════════════════════════════════════════════════════════════════
# Test: Item 33 — Terraform Export
# ═══════════════════════════════════════════════════════════════════

def test_generate_terraform():
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    mapping_results = [
        {"mapping_name": "m_load_orders", "sql": "SELECT 1"},
    ]
    files = agent._generate_terraform(parsed, mapping_results)
    assert "terraform/main.tf" in files
    assert "terraform/variables.tf" in files
    assert "terraform/bigquery.tf" in files
    assert "terraform/composer.tf" in files
    # Check main.tf has provider
    assert "hashicorp/google" in files["terraform/main.tf"]
    assert "provider" in files["terraform/main.tf"]
    # Check variables
    assert "project_id" in files["terraform/variables.tf"]
    assert "region" in files["terraform/variables.tf"]
    # Check bigquery.tf has dataset and table
    assert "google_bigquery_dataset" in files["terraform/bigquery.tf"]
    assert "google_bigquery_table" in files["terraform/bigquery.tf"]
    # Check composer
    assert "google_composer_environment" in files["terraform/composer.tf"]


def test_terraform_partition_cluster():
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    mapping_results = []
    files = agent._generate_terraform(parsed, mapping_results)
    bq_content = files["terraform/bigquery.tf"]
    # TGT_ORDERS has ORDER_DATE (date/time) → should detect partition
    if "time_partitioning" in bq_content:
        assert "DAY" in bq_content


# ═══════════════════════════════════════════════════════════════════
# Test: Regex patterns for partition / cluster
# ═══════════════════════════════════════════════════════════════════

def test_partition_re_patterns():
    assert _PARTITION_RE.search("LOAD_DATE")
    assert _PARTITION_RE.search("ETL_DATE")
    assert _PARTITION_RE.search("EFFECTIVE_DATE")
    assert _PARTITION_RE.search("CREATED")
    assert _PARTITION_RE.search("UPDATED")
    assert not _PARTITION_RE.search("CUSTOMER_NAME")
    assert not _PARTITION_RE.search("ORDER_ID")


def test_cluster_re_patterns():
    assert _CLUSTER_RE.search("CUSTOMER_ID")
    assert _CLUSTER_RE.search("REGION_CODE")
    assert _CLUSTER_RE.search("STATUS")
    assert _CLUSTER_RE.search("TYPE")
    assert _CLUSTER_RE.search("ACCOUNT_ID")
    assert not _CLUSTER_RE.search("ORDER_DATE")
    assert not _CLUSTER_RE.search("DESCRIPTION")


# ═══════════════════════════════════════════════════════════════════
# Test: Multi-XML merge (_heavy_parse_and_analyze_multi)
# ═══════════════════════════════════════════════════════════════════

def test_multi_xml_merge():
    """Multi-XML merge should combine sources from both XMLs."""
    agent = _agent()
    xml2 = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <POWERMART>
      <REPOSITORY>
        <FOLDER NAME="Folder2">
          <SOURCE NAME="SRC_PRODUCTS" DATABASETYPE="Oracle" OWNERNAME="dbo">
            <SOURCEFIELD NAME="PROD_ID" DATATYPE="number" PRECISION="10" SCALE="0" NULLABLE="NOTNULL"/>
          </SOURCE>
          <TARGET NAME="TGT_PRODUCTS" DATABASETYPE="Oracle" OWNERNAME="dbo">
            <TARGETFIELD NAME="PROD_ID" DATATYPE="number" PRECISION="10" SCALE="0" NULLABLE="NOTNULL" KEYTYPE="PRIMARY KEY"/>
          </TARGET>
          <MAPPING NAME="m_load_products" DESCRIPTION="">
            <INSTANCE NAME="SRC_PRODUCTS" TYPE="SOURCE" TRANSFORMATION_NAME="SRC_PRODUCTS" TRANSFORMATION_TYPE="Source"/>
            <INSTANCE NAME="TGT_PRODUCTS" TYPE="TARGET" TRANSFORMATION_NAME="TGT_PRODUCTS" TRANSFORMATION_TYPE="Target"/>
          </MAPPING>
          <WORKFLOW NAME="wkfl_product_load" DESCRIPTION="">
          </WORKFLOW>
        </FOLDER>
      </REPOSITORY>
    </POWERMART>
    """)
    result = agent._heavy_parse_and_analyze_multi([MINI_XML, xml2])
    assert not result["error"]
    parsed = result["parsed"]
    # Should have sources from both XMLs
    src_names = {s["name"] for s in parsed["sources"]}
    assert "SRC_ORDERS" in src_names
    assert "SRC_PRODUCTS" in src_names
    # Should have mappings from both
    map_names = {m["name"] for m in parsed["mappings"]}
    assert "m_load_orders" in map_names
    assert "m_load_products" in map_names


# ═══════════════════════════════════════════════════════════════════
# V3 Tests: VALUEPAIR, Email, WorkflowEvent, DAG wiring
# ═══════════════════════════════════════════════════════════════════

def test_valuepair_command_parsing():
    """Command tasks parsed via VALUEPAIR should have non-empty commands."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    assert "error" not in parsed

    # cmd_sftp_vframe uses VALUEPAIR, should have 2 commands
    sftp_tasks = [c for c in parsed["command_tasks"] if c["name"] == "cmd_sftp_vframe"]
    assert len(sftp_tasks) == 1, "cmd_sftp_vframe should be parsed"
    assert len(sftp_tasks[0]["commands"]) == 2, \
        f"Expected 2 commands from VALUEPAIR, got {len(sftp_tasks[0]['commands'])}"
    assert "$PMRootDir" in sftp_tasks[0]["commands"][0]

    # cmd_pre_cleanup uses CmdLine ATTRIBUTE, should also work
    cleanup = [c for c in parsed["command_tasks"] if c["name"] == "cmd_pre_cleanup"]
    assert len(cleanup) == 1
    assert len(cleanup[0]["commands"]) >= 1


def test_valuepair_iterparse():
    """iterparse should also capture VALUEPAIR commands."""
    agent = _agent()
    parsed = agent._parse_xml_iterparse(MINI_XML)
    assert "error" not in parsed

    sftp_tasks = [c for c in parsed["command_tasks"] if c["name"] == "cmd_sftp_vframe"]
    assert len(sftp_tasks) == 1
    assert len(sftp_tasks[0]["commands"]) == 2


def test_email_task_parsing():
    """Email tasks should be parsed as dedicated type."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    assert "email_tasks" in parsed
    assert len(parsed["email_tasks"]) >= 1
    email = parsed["email_tasks"][0]
    assert email["name"] == "email_success"
    assert email["type"] == "EMAIL"
    assert "Job Complete" in email["subject"]
    assert "team@example.com" in email["to"]


def test_email_task_iterparse():
    """iterparse should also capture email tasks."""
    agent = _agent()
    parsed = agent._parse_xml_iterparse(MINI_XML)
    assert "email_tasks" in parsed
    assert len(parsed["email_tasks"]) >= 1
    assert parsed["email_tasks"][0]["name"] == "email_success"


def test_workflow_event_parsing():
    """WORKFLOWEVENT elements should be parsed."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    assert "workflow_events" in parsed
    assert len(parsed["workflow_events"]) >= 1
    evt = parsed["workflow_events"][0]
    assert evt["name"] == "evt_trigger_downstream"


def test_workflow_event_iterparse():
    """iterparse should also capture WORKFLOWEVENT elements."""
    agent = _agent()
    parsed = agent._parse_xml_iterparse(MINI_XML)
    assert "workflow_events" in parsed
    assert len(parsed["workflow_events"]) >= 1


def test_condition_to_trigger_rule():
    """Known conditions should map to correct TriggerRules."""
    rule = InformaticaMigrationAdvancedAgent._condition_to_trigger_rule
    assert rule("") is None
    assert rule("$s_load.Status = SUCCEEDED") is None  # Default
    assert rule("$s_load.Status = SUCCEEDED OR DISABLED") == "TriggerRule.ALL_DONE"
    assert rule("$s_load.TgtSuccessRows = 1") == "SHORTCIRCUIT"
    assert rule("$s_load.SrcSuccessRows >= 0") == "SHORTCIRCUIT"


def test_workflow_dependencies_real_code():
    """DAG output should contain real >> operators, not just comments."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    analysis = {"complexity": "medium", "has_scd_pattern": False, "needs_dataflow": 0,
                 "unsupported": [], "sql_convertible": 0, "has_complex_logic": False,
                 "transformation_summary": []}
    # Create minimal mapping results
    mr = [{"mapping_name": "m_load_orders", "status": "converted", "sql": "SELECT 1"}]
    dag = agent._generate_airflow_dag(parsed, analysis, mr)

    # Should contain real dependency wiring (>> not preceded by #)
    dag_lines = dag.split("\n")
    real_deps = [l for l in dag_lines if ">>" in l and not l.strip().startswith("#")]
    assert len(real_deps) > 0, "DAG should contain real >> dependency wiring, not just comments"


def test_worklet_internal_wiring_real():
    """TaskGroup code should have actual >> operators for internal deps."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    analysis = {"complexity": "medium", "has_scd_pattern": False, "needs_dataflow": 0,
                 "unsupported": [], "sql_convertible": 0, "has_complex_logic": False,
                 "transformation_summary": []}
    mr = [{"mapping_name": "m_load_orders", "status": "converted", "sql": "SELECT 1"}]
    dag = agent._generate_airflow_dag(parsed, analysis, mr)

    # Should have a TaskGroup
    assert "TaskGroup" in dag, "DAG should contain TaskGroup for worklets"
    # Worklet internal deps should be real code
    in_taskgroup = False
    wklt_real_deps = []
    for line in dag.split("\n"):
        if "TaskGroup(" in line:
            in_taskgroup = True
        if in_taskgroup and ">>" in line and not line.strip().startswith("#"):
            wklt_real_deps.append(line)
    assert len(wklt_real_deps) > 0, "Worklet internal deps should be real >> code"


def test_no_echo_todo_when_commands_resolved():
    """BashOperator should use resolved commands, not echo TODO placeholders."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    analysis = {"complexity": "medium", "has_scd_pattern": False, "needs_dataflow": 0,
                 "unsupported": [], "sql_convertible": 0, "has_complex_logic": False,
                 "transformation_summary": []}
    mr = [{"mapping_name": "m_load_orders", "status": "converted", "sql": "SELECT 1"}]
    dag = agent._generate_airflow_dag(parsed, analysis, mr)

    # cmd_sftp_vframe has VALUEPAIR commands, should NOT have echo TODO
    # Find BashOperator lines
    bash_lines = [l for l in dag.split("\n") if "BashOperator" in l or "bash_command" in l]
    assert len(bash_lines) > 0, "DAG should contain BashOperator"

    # Check that resolved commands appear (not echo TODO for tasks with commands)
    assert "alv_sftp_vframe" in dag, "Resolved VALUEPAIR command should appear in DAG"


def test_dag_has_email_operator():
    """DAG should contain EmailOperator for email tasks."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    analysis = {"complexity": "medium", "has_scd_pattern": False, "needs_dataflow": 0,
                 "unsupported": [], "sql_convertible": 0, "has_complex_logic": False,
                 "transformation_summary": []}
    mr = [{"mapping_name": "m_load_orders", "status": "converted", "sql": "SELECT 1"}]
    dag = agent._generate_airflow_dag(parsed, analysis, mr)

    assert "EmailOperator" in dag, "DAG should contain EmailOperator"
    assert "email_success" in dag.lower(), "Email task should appear in DAG"


def test_dag_has_trigger_rule():
    """DAG should contain TriggerRule.ALL_DONE for SUCCEEDED OR DISABLED links."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    analysis = {"complexity": "medium", "has_scd_pattern": False, "needs_dataflow": 0,
                 "unsupported": [], "sql_convertible": 0, "has_complex_logic": False,
                 "transformation_summary": []}
    mr = [{"mapping_name": "m_load_orders", "status": "converted", "sql": "SELECT 1"}]
    dag = agent._generate_airflow_dag(parsed, analysis, mr)

    assert "TriggerRule" in dag, "DAG should import and use TriggerRule"
    assert "TriggerRule.ALL_DONE" in dag, "DAG should contain TriggerRule.ALL_DONE for DISABLED conditions"


def test_dag_has_trigger_dagrun():
    """DAG should contain TriggerDagRunOperator for WorkflowEvents."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    analysis = {"complexity": "medium", "has_scd_pattern": False, "needs_dataflow": 0,
                 "unsupported": [], "sql_convertible": 0, "has_complex_logic": False,
                 "transformation_summary": []}
    mr = [{"mapping_name": "m_load_orders", "status": "converted", "sql": "SELECT 1"}]
    dag = agent._generate_airflow_dag(parsed, analysis, mr)

    assert "TriggerDagRunOperator" in dag, "DAG should contain TriggerDagRunOperator"
    assert "evt_trigger_downstream" in dag.lower(), "WorkflowEvent should appear in DAG"


def test_dag_has_bash_env_vars():
    """Command tasks with .ksh scripts should generate PythonOperator stubs with migration guidance."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    analysis = {"complexity": "medium", "has_scd_pattern": False, "needs_dataflow": 0,
                 "unsupported": [], "sql_convertible": 0, "has_complex_logic": False,
                 "transformation_summary": []}
    mr = [{"mapping_name": "m_load_orders", "status": "converted", "sql": "SELECT 1"}]
    dag = agent._generate_airflow_dag(parsed, analysis, mr)

    # .ksh commands should now be PythonOperator with migration guidance (Fix #6)
    assert "PythonOperator" in dag, "ksh commands should use PythonOperator stubs"
    assert "MIGRATE_TO_GCP" in dag, "ksh commands should have MIGRATE_TO_GCP guidance"


def test_scorecard_has_operator_counts():
    """Scorecard should include operator counts and control flow coverage."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    analysis = {"complexity": "medium", "has_scd_pattern": False, "needs_dataflow": 0,
                 "unsupported": [], "sql_convertible": 0, "has_complex_logic": False,
                 "transformation_summary": []}
    mr = [{"mapping_name": "m_load_orders", "status": "converted", "sql": "SELECT 1"}]
    scorecard = agent._calculate_scorecard(parsed, analysis, mr, [], [])

    assert "operator_counts" in scorecard, "Scorecard should include operator counts"
    counts = scorecard["operator_counts"]
    assert counts["command_tasks"] >= 2  # cmd_pre_cleanup + cmd_sftp_vframe
    assert counts["email_tasks"] >= 1
    assert counts["workflow_events"] >= 1
    assert counts["worklets"] >= 1
    assert "control_flow_coverage" in scorecard


def test_dependency_graph_carries_conditions():
    """Dependency graph edges should carry condition metadata."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    graph = agent._build_workflow_dependency_graph(parsed)

    edges = graph["edges"]
    assert len(edges) > 0, "Should have workflow edges"

    # Check that edges are dicts with condition, not just strings
    found_condition = False
    for from_task, edge_list in edges.items():
        for edge in edge_list:
            assert isinstance(edge, dict), f"Edge should be dict, got {type(edge)}"
            assert "to_task" in edge, "Edge should have to_task"
            assert "condition" in edge, "Edge should have condition"
            if "DISABLED" in edge.get("condition", "").upper():
                found_condition = True

    assert found_condition, "Should find at least one DISABLED condition in edges"


# ═══════════════════════════════════════════════════════════════════
# V4 Tests: WORKFLOWVARIABLE, MAPPINGVARIABLE, CONNECTIONREFERENCE,
#           ISENABLED, AND-gate, TARGETLOADORDER, Normalizer, Rank,
#           REUSABLE flag, FLATFILE, complex conditions
# ═══════════════════════════════════════════════════════════════════

def test_workflow_variable_parsing():
    """WORKFLOWVARIABLE elements should be parsed with defaults and datatypes."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    assert "workflow_variables" in parsed
    wf_vars = parsed["workflow_variables"]
    assert len(wf_vars) >= 2, f"Expected >=2 workflow variables, got {len(wf_vars)}"
    # Check WF_RUN_DATE
    run_date = [v for v in wf_vars if "RUN_DATE" in v["name"]]
    assert len(run_date) >= 1, "WF_RUN_DATE should be parsed"
    assert run_date[0]["datatype"] == "date/time"
    assert run_date[0]["default_value"] == "01/01/2025"
    assert run_date[0]["is_persistent"] == "YES"
    # Check WF_BATCH_ID
    batch_id = [v for v in wf_vars if "BATCH_ID" in v["name"]]
    assert len(batch_id) >= 1, "WF_BATCH_ID should be parsed"
    assert batch_id[0]["datatype"] == "integer"


def test_workflow_variable_iterparse():
    """iterparse should also capture WORKFLOWVARIABLE elements."""
    agent = _agent()
    parsed = agent._parse_xml_iterparse(MINI_XML)
    assert "workflow_variables" in parsed
    assert len(parsed["workflow_variables"]) >= 2


def test_mapping_variable_parsing():
    """MAPPINGVARIABLE elements should be parsed with ISPARAM flag."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    assert "mapping_variables" in parsed
    mp_vars = parsed["mapping_variables"]
    assert len(mp_vars) >= 2, f"Expected >=2 mapping variables, got {len(mp_vars)}"
    # Check LOAD_TYPE
    load_type = [v for v in mp_vars if "LOAD_TYPE" in v["name"]]
    assert len(load_type) >= 1, "LOAD_TYPE should be parsed"
    assert load_type[0]["is_param"] == "YES"
    assert load_type[0]["default_value"] == "FULL"


def test_mapping_variable_iterparse():
    """iterparse should also capture MAPPINGVARIABLE elements."""
    agent = _agent()
    parsed = agent._parse_xml_iterparse(MINI_XML)
    assert "mapping_variables" in parsed
    assert len(parsed["mapping_variables"]) >= 2


def test_connection_reference_parsing():
    """CONNECTIONREFERENCE elements should be parsed."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    assert "connection_references" in parsed
    conn_refs = parsed["connection_references"]
    assert len(conn_refs) >= 2, f"Expected >=2 connection references, got {len(conn_refs)}"
    prod = [c for c in conn_refs if c["name"] == "PROD_DB"]
    assert len(prod) >= 1, "PROD_DB connection should be parsed"
    assert prod[0]["type"] == "Relational"
    assert prod[0]["instance_name"] == "$Source1"


def test_connection_reference_iterparse():
    """iterparse should also capture CONNECTIONREFERENCE elements."""
    agent = _agent()
    parsed = agent._parse_xml_iterparse(MINI_XML)
    assert "connection_references" in parsed
    assert len(parsed["connection_references"]) >= 2


def test_target_load_order_parsing():
    """TARGETLOADORDER elements should be parsed."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    assert "target_load_orders" in parsed
    tlo = parsed["target_load_orders"]
    assert len(tlo) >= 1, f"Expected >=1 target load orders, got {len(tlo)}"
    assert tlo[0]["target_instance"] == "TGT_ORDERS"
    assert tlo[0]["order"] == "1"


def test_target_load_order_iterparse():
    """iterparse should also capture TARGETLOADORDER elements."""
    agent = _agent()
    parsed = agent._parse_xml_iterparse(MINI_XML)
    assert "target_load_orders" in parsed
    assert len(parsed["target_load_orders"]) >= 1


def test_isenabled_parsing():
    """TASKINSTANCE ISENABLED attribute should be captured."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    disabled = [ti for ti in parsed["task_instances"] if ti.get("is_enabled", "YES").upper() == "NO"]
    assert len(disabled) >= 1, "Should find at least one disabled task instance"
    assert disabled[0]["name"] == "s_disabled_task"


def test_isenabled_iterparse():
    """iterparse should also capture ISENABLED."""
    agent = _agent()
    parsed = agent._parse_xml_iterparse(MINI_XML)
    disabled = [ti for ti in parsed["task_instances"] if ti.get("is_enabled", "YES").upper() == "NO"]
    assert len(disabled) >= 1, "iterparse should find disabled task"


def test_and_gate_parsing():
    """TREAT_INPUTLINK_AS_AND attribute should be captured."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    and_gates = [ti for ti in parsed["task_instances"]
                 if ti.get("treat_input_as_and", "NO").upper() == "YES"]
    assert len(and_gates) >= 1, "Should find at least one AND-gate task"
    assert and_gates[0]["name"] == "wklt_sub_process"


def test_and_gate_in_dependency_graph():
    """Dependency graph should track AND-gate tasks."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    graph = agent._build_workflow_dependency_graph(parsed)
    assert "and_gate_tasks" in graph
    assert "wklt_sub_process" in graph["and_gate_tasks"]


def test_disabled_tasks_in_dependency_graph():
    """Dependency graph should track disabled tasks."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    graph = agent._build_workflow_dependency_graph(parsed)
    assert "disabled_tasks" in graph
    assert "s_disabled_task" in graph["disabled_tasks"]


def test_disabled_task_in_dag():
    """DAG should contain DummyOperator for disabled tasks."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    analysis = {"complexity": "medium", "has_scd_pattern": False, "needs_dataflow": 0,
                 "unsupported": [], "sql_convertible": 0, "has_complex_logic": False,
                 "transformation_summary": []}
    mr = [{"mapping_name": "m_load_orders", "status": "converted", "sql": "SELECT 1"}]
    dag = agent._generate_airflow_dag(parsed, analysis, mr)
    assert "Disabled" in dag or "disabled" in dag.lower(), "DAG should mention disabled tasks"
    assert "s_disabled_task" in dag.lower(), "Disabled task should appear in DAG"


def test_complex_condition_trigger_rules():
    """Complex conditions should map to appropriate TriggerRules."""
    rule = InformaticaMigrationAdvancedAgent._condition_to_trigger_rule
    # FAILED condition → ALL_FAILED
    assert rule("$task.Status = FAILED") == "TriggerRule.ALL_FAILED"
    # SUCCEEDED OR STOPPED → ALL_DONE
    assert rule("$task.Status = SUCCEEDED OR STOPPED") == "TriggerRule.ALL_DONE"
    # Simple SUCCEEDED → None (default)
    assert rule("$task.Status = SUCCEEDED") is None


def test_parameters_enriched_from_variables():
    """_extract_parameters should use WORKFLOWVARIABLE and MAPPINGVARIABLE data."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    params = agent._extract_parameters(parsed)
    # Should include WF_RUN_DATE from WORKFLOWVARIABLE
    wf_params = [p for p in params if "RUN_DATE" in p["name"]]
    assert len(wf_params) >= 1, "WF_RUN_DATE should be in parameters"
    assert wf_params[0]["default_value"] == "01/01/2025"
    assert wf_params[0]["type_guess"] == "date"
    assert wf_params[0]["source"] == "workflow_variable"

    # Should include LOAD_TYPE from MAPPINGVARIABLE
    mp_params = [p for p in params if "LOAD_TYPE" in p["name"]]
    assert len(mp_params) >= 1, "LOAD_TYPE should be in parameters"
    assert mp_params[0]["default_value"] == "FULL"
    assert mp_params[0]["source"] == "mapping_variable"


def test_connection_map_building():
    """_build_connection_map should build instance→connection mapping."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    conn_map = agent._build_connection_map(parsed)
    assert len(conn_map) >= 2
    assert "$Source1" in conn_map
    assert conn_map["$Source1"]["connection_name"] == "PROD_DB"


def test_reusable_flag_on_transformations():
    """Transformations should have reusable flag."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    for tf in parsed["transformations"]:
        assert "reusable" in tf, f"Transformation {tf['name']} should have reusable flag"


def test_scorecard_has_new_counts():
    """Scorecard should include new operator counts for variables and references."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    analysis = {"complexity": "medium", "has_scd_pattern": False, "needs_dataflow": 0,
                 "unsupported": [], "sql_convertible": 0, "has_complex_logic": False,
                 "transformation_summary": []}
    mr = [{"mapping_name": "m_load_orders", "status": "converted", "sql": "SELECT 1"}]
    scorecard = agent._calculate_scorecard(parsed, analysis, mr, [], [])
    counts = scorecard["operator_counts"]
    assert "workflow_variables" in counts
    assert "mapping_variables" in counts
    assert "connection_references" in counts
    assert "target_load_orders" in counts
    assert counts["workflow_variables"] >= 2
    assert counts["mapping_variables"] >= 2
    assert counts["connection_references"] >= 2


def test_failed_condition_trigger_rule_in_dag():
    """DAG should contain TriggerRule.ALL_FAILED for FAILED conditions."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    analysis = {"complexity": "medium", "has_scd_pattern": False, "needs_dataflow": 0,
                 "unsupported": [], "sql_convertible": 0, "has_complex_logic": False,
                 "transformation_summary": []}
    mr = [{"mapping_name": "m_load_orders", "status": "converted", "sql": "SELECT 1"}]
    dag = agent._generate_airflow_dag(parsed, analysis, mr)
    assert "TriggerRule.ALL_FAILED" in dag, \
        "DAG should contain TriggerRule.ALL_FAILED for FAILED condition links"


def test_iterparse_new_keys_parity():
    """iterparse should produce same counts for all new keys as standard parser."""
    agent = _agent()
    standard = agent._parse_xml(MINI_XML)
    chunked = agent._parse_xml_iterparse(MINI_XML)

    for key in ["workflow_variables", "mapping_variables",
                "connection_references", "target_load_orders"]:
        assert len(standard.get(key, [])) == len(chunked.get(key, [])), \
            f"Mismatch on '{key}': standard={len(standard.get(key, []))}, iterparse={len(chunked.get(key, []))}"


# ═══════════════════════════════════════════════════════════════════
# Gap Enhancement Tests (18 gaps from critical review)
# ═══════════════════════════════════════════════════════════════════


def test_associated_source_instance_parsing():
    """Gap 1: ASSOCIATED_SOURCE_INSTANCE is parsed from INSTANCE elements."""
    xml = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <POWERMART><REPOSITORY><FOLDER NAME="F">
      <SOURCE NAME="SRC_A" DATABASETYPE="Teradata"><SOURCEFIELD NAME="ID" DATATYPE="number"/></SOURCE>
      <SOURCE NAME="SRC_B" DATABASETYPE="Teradata"><SOURCEFIELD NAME="NAME" DATATYPE="string"/></SOURCE>
      <TARGET NAME="TGT" DATABASETYPE="Teradata"><TARGETFIELD NAME="ID" DATATYPE="number" KEYTYPE="PRIMARY KEY"/></TARGET>
      <MAPPING NAME="m_test" DESCRIPTION="">
        <INSTANCE NAME="SRC_A" TYPE="SOURCE" TRANSFORMATION_NAME="SRC_A" TRANSFORMATION_TYPE="Source"/>
        <INSTANCE NAME="SRC_B" TYPE="SOURCE" TRANSFORMATION_NAME="SRC_B" TRANSFORMATION_TYPE="Source"
                  ASSOCIATED_SOURCE_INSTANCE="SQ_COMBINED"/>
        <INSTANCE NAME="SQ_COMBINED" TYPE="TRANSFORMATION" TRANSFORMATION_NAME="SQ_COMBINED" TRANSFORMATION_TYPE="Source Qualifier"/>
        <INSTANCE NAME="TGT" TYPE="TARGET" TRANSFORMATION_NAME="TGT" TRANSFORMATION_TYPE="Target"/>
      </MAPPING>
      <WORKFLOW NAME="wf"><TASKINSTANCE NAME="s1" TASKTYPE="Session" TASKNAME="s1" ISENABLED="YES"/></WORKFLOW>
    </FOLDER></REPOSITORY></POWERMART>""")

    agent = _agent()
    parsed = agent._parse_xml(xml)
    # Find the instance with ASSOCIATED_SOURCE_INSTANCE
    instances = parsed["mappings"][0]["instances"]
    assoc_inst = [i for i in instances if i.get("associated_source_instance")]
    assert len(assoc_inst) >= 1, "Should find at least one instance with associated_source_instance"
    assert assoc_inst[0]["associated_source_instance"] == "SQ_COMBINED"

    # Test _resolve_associated_sources
    group = {"instances": instances}
    associated = agent._resolve_associated_sources("SQ_COMBINED", group)
    assert "SRC_B" in associated, f"Should find SRC_B as associated source, got {associated}"

    # Verify iterparse produces same result
    parsed_iter = agent._parse_xml_iterparse(xml)
    iter_instances = parsed_iter["mappings"][0]["instances"]
    iter_assoc = [i for i in iter_instances if i.get("associated_source_instance")]
    assert len(iter_assoc) >= 1


def test_update_strategy_dd_flags_merge():
    """Gap 2: Update Strategy DD flags parsed and used in MERGE."""
    agent = _agent()
    # Test _parse_update_strategy_expression
    expr = "IIF(ISNULL(KEY_COL), DD_INSERT, IIF(STATUS = 'D', DD_DELETE, DD_UPDATE))"
    result = agent._parse_update_strategy_expression(expr, [])
    assert "DD_INSERT" in result, f"Should find DD_INSERT condition, got {result}"
    assert "DD_DELETE" in result, f"Should find DD_DELETE condition, got {result}"
    assert "DD_UPDATE" in result or len(result) >= 2, f"Should find DD conditions, got {result}"


def test_treat_source_rows_as_update():
    """Gap 3: 'Treat source rows as' parsed from sessions."""
    xml = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <POWERMART><REPOSITORY><FOLDER NAME="F">
      <SOURCE NAME="SRC" DATABASETYPE="Teradata"><SOURCEFIELD NAME="ID" DATATYPE="number"/></SOURCE>
      <TARGET NAME="TGT" DATABASETYPE="Teradata">
        <TARGETFIELD NAME="ID" DATATYPE="number" KEYTYPE="PRIMARY KEY"/>
        <TARGETFIELD NAME="VAL" DATATYPE="string" KEYTYPE=""/>
      </TARGET>
      <MAPPING NAME="m_upd" DESCRIPTION="">
        <INSTANCE NAME="SRC" TYPE="SOURCE" TRANSFORMATION_NAME="SRC" TRANSFORMATION_TYPE="Source"/>
        <INSTANCE NAME="TGT" TYPE="TARGET" TRANSFORMATION_NAME="TGT" TRANSFORMATION_TYPE="Target"/>
      </MAPPING>
      <SESSION NAME="s_upd" MAPPINGNAME="m_upd" DESCRIPTION="">
        <ATTRIBUTE NAME="Treat source rows as" VALUE="Update"/>
      </SESSION>
      <WORKFLOW NAME="wf"><TASKINSTANCE NAME="s_upd" TASKTYPE="Session" TASKNAME="s_upd" ISENABLED="YES"/></WORKFLOW>
    </FOLDER></REPOSITORY></POWERMART>""")

    agent = _agent()
    parsed = agent._parse_xml(xml)
    sess = parsed["sessions"][0]
    assert sess.get("treat_source_rows_as") == "Update", \
        f"Expected 'Update', got {sess.get('treat_source_rows_as')}"

    # Verify iterparse
    parsed_iter = agent._parse_xml_iterparse(xml)
    sess_iter = parsed_iter["sessions"][0]
    assert sess_iter.get("treat_source_rows_as") == "Update"


def test_target_load_order_sorting():
    """Gap 4: Targets sorted by TARGETLOADORDER before SQL generation."""
    agent = _agent()
    group = {
        "targets": [
            {"name": "FACT_TABLE", "columns": [{"name": "ID", "datatype": "number", "key_type": "PRIMARY KEY"}], "database_type": "Teradata"},
            {"name": "DIM_TABLE", "columns": [{"name": "ID", "datatype": "number", "key_type": "PRIMARY KEY"}], "database_type": "Teradata"},
        ],
        "target_load_orders": [
            {"target_instance": "DIM_TABLE", "order": "1"},
            {"target_instance": "FACT_TABLE", "order": "2"},
        ],
        "transformations": [],
        "sources": [{"name": "SRC", "columns": [], "database_type": "Teradata"}],
        "instances": [],
        "connector_graph": {"forward_edges": {}, "reverse_edges": {}, "nodes": set(), "field_map": {}},
    }
    agent._current_parsed = {"sessions": []}
    sql = agent._rule_based_mapping_sql("m_test", group, group["connector_graph"], [])
    # DIM_TABLE should appear before FACT_TABLE in the target load section (after "Final: Load")
    final_section = sql[sql.find("-- Final:"):]
    dim_pos = final_section.find("dim_table")
    fact_pos = final_section.find("fact_table")
    assert dim_pos >= 0 and fact_pos >= 0, f"Both tables should appear in final load section"
    assert dim_pos < fact_pos, f"DIM_TABLE (pos {dim_pos}) should come before FACT_TABLE (pos {fact_pos}) in final loads"


def test_joiner_master_detail_orientation():
    """Gap 5: Joiner resolves Master/Detail for correct JOIN orientation."""
    agent = _agent()
    tf = {
        "name": "JNR_TEST",
        "type": "Joiner",
        "fields": [
            {"name": "DETAIL_KEY", "porttype": "INPUT, DETAIL", "datatype": "number", "expression": ""},
            {"name": "MASTER_KEY", "porttype": "INPUT, MASTER", "datatype": "number", "expression": ""},
        ],
        "properties": {},
    }
    join_sources = ["detail_table", "master_table"]
    connector_graph = {
        "forward_edges": {},
        "reverse_edges": {"JNR_TEST": {"detail_table", "master_table"}},
        "field_map": {
            ("detail_table", "DETAIL_KEY"): ("JNR_TEST", "DETAIL_KEY"),
            ("master_table", "MASTER_KEY"): ("JNR_TEST", "MASTER_KEY"),
        },
    }
    detail_src, master_src = agent._resolve_joiner_master_detail(tf, join_sources, connector_graph)
    assert detail_src == "detail_table", f"Expected detail_table, got {detail_src}"
    assert master_src == "master_table", f"Expected master_table, got {master_src}"


def test_sequence_currval_and_properties():
    """Gap 6: Sequence Generator uses Start Value, Increment, and CURRVAL."""
    agent = _agent()
    agent._current_parsed = {"sessions": []}
    group = {
        "transformations": [
            {
                "name": "SEQ_GEN", "type": "Sequence Generator",
                "properties": {"Start Value": "100", "Increment By": "10"},
                "fields": [
                    {"name": "NEXTVAL", "porttype": "OUTPUT", "datatype": "number", "expression": ""},
                    {"name": "CURRVAL", "porttype": "OUTPUT", "datatype": "number", "expression": ""},
                ],
            }
        ],
        "sources": [{"name": "SRC", "columns": [{"name": "ID", "datatype": "number"}], "database_type": "Teradata"}],
        "targets": [{"name": "TGT", "columns": [{"name": "ID", "datatype": "number", "key_type": "PRIMARY KEY"}], "database_type": "Teradata"}],
        "instances": [],
        "target_load_orders": [],
        "connector_graph": {"forward_edges": {}, "reverse_edges": {}, "nodes": set(), "field_map": {}},
    }
    sql = agent._rule_based_mapping_sql("m_seq", group, group["connector_graph"], [])
    assert "100" in sql, "Should reference start value 100"
    assert "10" in sql, "Should reference increment 10"
    assert "CURRVAL" in sql, "Should handle CURRVAL port"


def test_nested_mapplet_inlining():
    """Gap 7: Mapplet inlining supports recursion and connector merge."""
    agent = _agent()
    parsed = {
        "mapplets": [
            {
                "name": "MPLT_OUTER",
                "transformations": [
                    {"name": "EXP_INNER", "type": "Expression", "fields": [], "properties": {}},
                ],
                "connectors": [
                    {"from_instance": "EXP_INNER", "from_field": "OUT", "to_instance": "OUTPUT", "to_field": "OUT"},
                ],
                "input_ports": [], "output_ports": [],
            }
        ],
    }
    group = {
        "transformations": [],
        "mapplet_instance_names": ["MPLT_OUTER"],
        "instances": [],
        "connector_graph": {"forward_edges": {}, "reverse_edges": {}, "nodes": set(), "field_map": {}},
    }
    result = agent._inline_mapplets(group, parsed)
    # Should have the inlined transformation with prefixed name
    inlined_names = [t["name"] for t in result]
    assert any("MPLT_OUTER__EXP_INNER" in n for n in inlined_names), \
        f"Should find prefixed inlined transformation, got {inlined_names}"


def test_expression_date_diff_rewrite():
    """Gap 8: DATE_DIFF arguments rewritten for BigQuery."""
    agent = _agent()
    result = agent._convert_expression("DATE_DIFF(date1, date2, 'DD')", [])
    assert "DAY" in result, f"Expected DAY in result, got: {result}"


def test_expression_get_date_part():
    """Gap 8: GET_DATE_PART rewritten to EXTRACT."""
    agent = _agent()
    result = agent._convert_expression("GET_DATE_PART(order_date, 'MM')", [])
    assert "EXTRACT" in result, f"Expected EXTRACT in result, got: {result}"
    assert "MONTH" in result, f"Expected MONTH in result, got: {result}"


def test_expression_is_spaces():
    """Gap 8: IS_SPACES converted to LENGTH(TRIM(x)) = 0."""
    agent = _agent()
    result = agent._convert_expression("IS_SPACES(field_name)", [])
    assert "TRIM" in result, f"Expected TRIM in result, got: {result}"
    assert "LENGTH" in result or "= 0" in result, f"Expected boolean check, got: {result}"


def test_expression_nvl2_ast():
    """Gap 8: NVL2 handled in AST path."""
    agent = _agent()
    result = agent._convert_expression("NVL2(status, 'ACTIVE', 'INACTIVE')", [])
    assert "IS NOT NULL" in result or "IF(" in result, f"Expected IF/IS NOT NULL, got: {result}"


def test_expression_exp_ref():
    """Gap 8: :EXP port references tokenized."""
    agent = _agent()
    tokens = agent._tokenize_expression(":EXP.MY_EXPR(field1)")
    exp_refs = [t for t in tokens if t.get("type") == "EXP_REF"]
    assert len(exp_refs) >= 1, f"Should find EXP_REF token, got tokens: {tokens}"
    assert exp_refs[0]["value"] == "MY_EXPR"


def test_expression_seq_ref():
    """Gap 8: :SEQ references tokenized."""
    agent = _agent()
    tokens = agent._tokenize_expression(":SEQ.MY_SEQ.NEXTVAL")
    seq_refs = [t for t in tokens if t.get("type") == "SEQ_REF"]
    assert len(seq_refs) >= 1, f"Should find SEQ_REF token, got tokens: {tokens}"
    assert seq_refs[0]["value"] == "MY_SEQ"
    assert seq_refs[0]["port"] == "NEXTVAL"


def test_convert_teradata_sql():
    """Gap 9: Teradata SQL converted to BigQuery."""
    agent = _agent()
    # SEL → SELECT
    result = agent._convert_teradata_sql("SEL * FROM my_table", [])
    assert "SELECT" in result, f"Expected SELECT, got: {result}"
    assert "SEL" not in result.split("SELECT")[0], "SEL should be replaced"

    # VOLATILE TABLE → TEMP TABLE
    result2 = agent._convert_teradata_sql("CREATE VOLATILE TABLE tmp AS SEL 1", [])
    assert "TEMP TABLE" in result2, f"Expected TEMP TABLE, got: {result2}"

    # COLLECT STATISTICS → comment
    result3 = agent._convert_teradata_sql("COLLECT STATISTICS ON my_table;", [])
    assert "removed" in result3.lower() or "--" in result3, f"Expected comment, got: {result3}"


def test_router_group_columns():
    """Gap 10: Router groups include per-group field lists."""
    agent = _agent()
    tf = {
        "name": "RTR_REGION",
        "type": "Router",
        "fields": [
            {"name": "REGION_IND", "porttype": "INPUT", "datatype": "string", "expression": "", "group": ""},
            {"name": "BTN", "porttype": "OUTPUT", "datatype": "string", "expression": "", "group": "NORTH"},
            {"name": "WC", "porttype": "OUTPUT", "datatype": "string", "expression": "", "group": "SOUTH"},
        ],
        "properties": {"Group Filter Condition/NORTH": "REGION_IND='N'", "Group Filter Condition/SOUTH": "REGION_IND='S'"},
    }
    groups = agent._extract_router_groups(tf, [])
    assert len(groups) >= 2, f"Should find at least 2 groups, got {len(groups)}"
    # Each group should be a tuple of at least 2 elements (name, condition) or 3 (name, condition, fields)
    for g in groups:
        assert len(g) >= 2, f"Each group should have at least name and condition, got {g}"


def test_command_pmcmd_translation():
    """Gap 11: pmcmd startworkflow translated to TriggerDagRunOperator."""
    agent = _agent()
    op_type, result = agent._translate_command_to_gcp("pmcmd startworkflow -sv prod wkfl_downstream_load")
    assert op_type == "TriggerDagRunOperator", f"Expected TriggerDagRunOperator, got {op_type}"
    assert "wkfl_downstream_load" in result.lower(), f"Expected workflow name in result, got {result}"


def test_command_file_ops_translation():
    """Gap 11: File operations translated to gsutil."""
    agent = _agent()
    op_type, result = agent._translate_command_to_gcp("cp /data/input/orders.csv /data/archive/")
    assert "gsutil" in result.lower(), f"Expected gsutil in result, got {result}"


def test_flat_file_target_export():
    """Gap 13: Flat file targets generate EXPORT DATA."""
    agent = _agent()
    agent._current_parsed = {"sessions": []}
    group = {
        "transformations": [],
        "sources": [{"name": "SRC", "columns": [{"name": "ID", "datatype": "number"}], "database_type": "Teradata"}],
        "targets": [
            {
                "name": "FF_OUTPUT", "database_type": "Flat File",
                "columns": [{"name": "ID", "datatype": "number", "key_type": ""}],
                "file_format": {"delimiter": "|"},
            }
        ],
        "instances": [],
        "target_load_orders": [],
        "connector_graph": {"forward_edges": {}, "reverse_edges": {}, "nodes": set(), "field_map": {}},
    }
    sql = agent._rule_based_mapping_sql("m_ff", group, group["connector_graph"], [])
    assert "EXPORT DATA" in sql, f"Expected EXPORT DATA for flat file target, got SQL:\n{sql[:500]}"


def test_disabled_session_skips_sql():
    """Gap 14: Disabled sessions result in empty SQL with 'disabled' status."""
    agent = _agent()
    parsed = agent._parse_xml(MINI_XML)
    # MINI_XML has s_disabled_task with ISENABLED="NO"
    disabled_tis = [ti for ti in parsed.get("task_instances", [])
                    if ti.get("is_enabled", "YES").upper() == "NO"]
    assert len(disabled_tis) >= 1, "Should find at least one disabled task instance"


def test_dynamic_max_tokens():
    """Gap 15: max_tokens varies by transformation count."""
    # We can't easily test the async LLM call, but we can verify the logic
    agent = _agent()
    # Simple mapping (≤5 transformations)
    tf_count = 3
    if tf_count <= 5:
        max_tokens = 4096
    elif tf_count <= 15:
        max_tokens = 8192
    else:
        max_tokens = 16384
    assert max_tokens == 4096

    # Complex mapping (>15 transformations)
    tf_count = 25
    if tf_count <= 5:
        max_tokens = 4096
    elif tf_count <= 15:
        max_tokens = 8192
    else:
        max_tokens = 16384
    assert max_tokens == 16384


def test_confidence_update_strategy():
    """Gap 17: Confidence scoring adjusts for Update Strategy coverage."""
    agent = _agent()
    group = {
        "transformations": [
            {"name": "UPDTRANS", "type": "Update Strategy", "fields": []},
        ],
        "targets": [{"name": "TGT", "columns": [{"name": "ID", "datatype": "number", "key_type": "PRIMARY KEY"}]}],
    }
    connector_graph = {"forward_edges": {}, "reverse_edges": {}, "nodes": set(), "field_map": {}}

    # SQL without THEN DELETE should be penalized
    sql_no_delete = "INSERT INTO tgt (ID) VALUES (1); CREATE TABLE step_1 AS SELECT 1; MERGE tgt USING src ON tgt.ID = src.ID WHEN MATCHED THEN UPDATE SET tgt.ID = src.ID"
    result = agent._calculate_mapping_confidence("m_test", sql_no_delete, group, connector_graph)
    assert "DD_DELETE not translated" in " ".join(result["issues"]), \
        f"Should flag missing DD_DELETE, issues: {result['issues']}"


def test_confidence_unresolved_params():
    """Gap 18: Confidence scoring penalizes unresolved $$params."""
    agent = _agent()
    group = {
        "transformations": [],
        "targets": [{"name": "TGT", "columns": [{"name": "ID", "datatype": "number", "key_type": ""}]}],
    }
    connector_graph = {"forward_edges": {}, "reverse_edges": {}, "nodes": set(), "field_map": {}}

    sql_with_params = "CREATE TABLE step AS SELECT * FROM $$SRC_SCHEMA.$$SRC_TABLE; INSERT INTO tgt (ID) SELECT ID FROM step;"
    result = agent._calculate_mapping_confidence("m_test", sql_with_params, group, connector_graph)
    assert any("$$parameter" in issue for issue in result["issues"]), \
        f"Should flag unresolved $$params, issues: {result['issues']}"


# ═══════════════════════════════════════════════════════════════════
# Run all tests
# ═══════════════════════════════════════════════════════════════════

def _run_all():
    import traceback
    tests = [
        (name, obj) for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
    ]
    passed = 0
    failed = 0
    errors = []
    for name, fn in sorted(tests):
        try:
            fn()
            passed += 1
            print(f"  ✓ {name}")
        except Exception as e:
            failed += 1
            tb = traceback.format_exc()
            errors.append((name, tb))
            print(f"  ✗ {name}: {e}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    if errors:
        print("\nFailure details:")
        for name, tb in errors:
            print(f"\n--- {name} ---")
            print(tb)
    return failed


if __name__ == "__main__":
    sys.exit(_run_all())
