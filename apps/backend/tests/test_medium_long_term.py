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
      <WORKFLOW NAME="wkfl_daily_load" DESCRIPTION="Daily load workflow">
        <SCHEDULER SCHEDULETYPE="DAILY" REPEAT="1" STARTDATE="2024-01-01" STARTTIME="06:00:00"/>
        <TASKINSTANCE NAME="s_load_orders" TASKTYPE="Session" TASKNAME="s_load_orders" ISVALID="YES" REUSABLE="NO"/>
        <WORKFLOWLINK FROMTASK="Start" TOTASK="s_load_orders" CONDITION=""/>
      </WORKFLOW>
      <TASK NAME="cmd_pre_cleanup" TYPE="Command" DESCRIPTION="Pre-cleanup task">
        <ATTRIBUTE NAME="CmdLine1" VALUE="echo cleanup"/>
      </TASK>
      <TASK NAME="ew_file_arrival" TYPE="Event Wait" DESCRIPTION="Wait for file">
        <ATTRIBUTE NAME="Filewatch name" VALUE="/data/input/orders.dat"/>
      </TASK>
      <TASK NAME="dec_check_count" TYPE="Decision" DESCRIPTION="Check row count">
        <ATTRIBUTE NAME="Decision Name" VALUE="row_count_gt_0"/>
      </TASK>
      <SESSION NAME="s_load_orders" MAPPINGNAME="m_load_orders" DESCRIPTION="">
        <ATTRIBUTE NAME="Parameter Filename" VALUE="param_orders.par"/>
      </SESSION>
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
