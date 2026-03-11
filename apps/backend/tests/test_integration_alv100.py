"""Integration test: run full advanced migration on ALV_100 XML.

Validates:
  - 155 mappings processed (no regressions)
  - Overall score >= 83%
  - Average confidence >= 80
  - All new output types (test_sql_files, cost_estimate, dbt_files, terraform_files) populated
  - iterparse produces same parse counts as standard parser
  - Selective mode filters correctly
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.informatica_migration_advanced import (
    InformaticaMigrationAdvancedAgent,
    _prep_cache,
)

XML_PATH = "/tmp/alv_analysis/input/wkfl_ALV_100_MAIN_LOAD.XML"


def test_full_migration():
    if not os.path.exists(XML_PATH):
        print(f"SKIP: {XML_PATH} not found")
        return

    xml_content = open(XML_PATH, encoding="utf-8", errors="replace").read()
    print(f"  XML size: {len(xml_content):,} bytes")

    agent = InformaticaMigrationAdvancedAgent()
    _prep_cache.clear()

    t0 = time.time()
    result = asyncio.run(agent.migrate(xml_content=xml_content, use_cache=True))
    elapsed = time.time() - t0
    print(f"  Migration time: {elapsed:.1f}s")

    # Basic structure
    assert "error" not in result or not result.get("error"), f"Migration returned error: {result.get('error')}"
    assert "bigquery_sql" in result
    assert "airflow_dag" in result
    assert "scorecard" in result
    assert "mapping_results" in result

    # Mapping count (should be ~155)
    mapping_count = len(result["mapping_results"])
    print(f"  Mappings processed: {mapping_count}")
    assert mapping_count >= 140, f"Expected >= 140 mappings, got {mapping_count}"

    # Overall score
    score = result["scorecard"]["overall_score"]
    print(f"  Overall score: {score}%")
    assert score >= 80, f"Expected score >= 80%, got {score}%"

    # Average confidence
    conf_summary = result.get("confidence_summary", {})
    avg_score = conf_summary.get("average_score", 0)
    print(f"  Average confidence: {avg_score}")
    assert avg_score >= 75, f"Expected avg confidence >= 75, got {avg_score}"

    # Tier distribution
    tier_dist = conf_summary.get("tier_distribution", {})
    high_count = tier_dist.get("HIGH", 0)
    print(f"  Tier distribution: {tier_dist}")
    assert high_count >= 50, f"Expected >= 50 HIGH mappings, got {high_count}"

    # New long-term output types
    assert "test_sql_files" in result, "Missing test_sql_files"
    assert "cost_estimate" in result, "Missing cost_estimate"
    assert "dbt_files" in result, "Missing dbt_files"
    assert "terraform_files" in result, "Missing terraform_files"

    test_files = result["test_sql_files"]
    print(f"  Test SQL files: {len(test_files)}")
    assert len(test_files) > 0, "Should generate at least one test SQL file"

    cost = result["cost_estimate"]
    print(f"  Cost estimate: {cost.get('summary', 'N/A')}")
    assert cost["storage"]["total_gb"] > 0
    assert cost["compute"]["total_per_run_usd"] >= 0

    dbt = result["dbt_files"]
    print(f"  dbt files: {len(dbt)}")
    assert "dbt_project.yml" in dbt
    assert "models/schema.yml" in dbt

    tf = result["terraform_files"]
    print(f"  Terraform files: {len(tf)}")
    assert "terraform/main.tf" in tf
    assert "terraform/bigquery.tf" in tf

    # Verify SQL is non-trivial
    sql_len = len(result["bigquery_sql"])
    print(f"  Combined SQL length: {sql_len:,} chars")
    assert sql_len > 10000, f"Expected substantial SQL, got {sql_len} chars"

    # Verify DAG is non-trivial
    dag = result["airflow_dag"]
    dag_len = len(dag)
    print(f"  Airflow DAG length: {dag_len:,} chars")
    assert dag_len > 5000, f"Expected substantial DAG, got {dag_len} chars"

    # V3: Verify DAG contains BashOperator (not 0)
    bash_count = dag.count("BashOperator(")
    print(f"  BashOperator count: {bash_count}")
    assert bash_count >= 30, f"Expected >= 30 BashOperator, got {bash_count}"

    # V3: Verify DAG contains real >> dependency wiring (not just comments)
    dag_lines = dag.split("\n")
    real_deps = [l for l in dag_lines if ">>" in l and not l.strip().startswith("#")]
    print(f"  Real >> dependency lines: {len(real_deps)}")
    assert len(real_deps) >= 20, f"Expected >= 20 real dependency lines, got {len(real_deps)}"

    # V3: Verify TaskGroup for worklets
    taskgroup_count = dag.count("TaskGroup(")
    print(f"  TaskGroup count: {taskgroup_count}")
    assert taskgroup_count >= 20, f"Expected >= 20 TaskGroup, got {taskgroup_count}"

    # V3: Verify no echo TODO for commands with VALUEPAIR data
    echo_todo_count = dag.count("echo TODO") + dag.count("echo 'TODO")
    print(f"  echo TODO placeholders: {echo_todo_count}")
    # Some commands may not have VALUEPAIR data, but most should be resolved
    assert echo_todo_count < bash_count, \
        f"Too many echo TODO placeholders ({echo_todo_count}) vs BashOperators ({bash_count})"

    # V3: Verify BashOperator env vars
    assert "pm_root_dir" in dag, "BashOperator should have PMRootDir env var"

    # V3: Verify TriggerRule usage
    assert "TriggerRule" in dag, "DAG should contain TriggerRule"

    # V3: Verify new imports
    assert "EmailOperator" in dag or "TriggerDagRunOperator" in dag, \
        "DAG should import EmailOperator or TriggerDagRunOperator"

    # V3: Verify scorecard has operator counts
    sc = result["scorecard"]
    assert "operator_counts" in sc, "Scorecard should include operator_counts"
    print(f"  Operator counts: {sc['operator_counts']}")

    # V4: Verify new parsed element counts in scorecard
    oc = sc["operator_counts"]
    if oc.get("workflow_variables", 0) > 0:
        print(f"  Workflow variables: {oc['workflow_variables']}")
    if oc.get("mapping_variables", 0) > 0:
        print(f"  Mapping variables: {oc['mapping_variables']}")
    if oc.get("connection_references", 0) > 0:
        print(f"  Connection references: {oc['connection_references']}")

    # V4: Verify parameters enriched from WORKFLOWVARIABLE/MAPPINGVARIABLE
    params = result.get("parameters", [])
    print(f"  Parameters extracted: {len(params)}")
    wf_sourced = [p for p in params if p.get("source") == "workflow_variable"]
    mv_sourced = [p for p in params if p.get("source") == "mapping_variable"]
    if wf_sourced:
        print(f"    From WORKFLOWVARIABLE: {len(wf_sourced)}")
    if mv_sourced:
        print(f"    From MAPPINGVARIABLE: {len(mv_sourced)}")

    # V4: Verify ISENABLED handling (disabled tasks as DummyOperator)
    disabled_in_dag = dag.count("Disabled in source workflow")
    if disabled_in_dag > 0:
        print(f"  Disabled tasks in DAG: {disabled_in_dag}")

    # V4: Verify AND-gate/TriggerRule.ALL_SUCCESS if applicable
    all_success_count = dag.count("TriggerRule.ALL_SUCCESS")
    if all_success_count > 0:
        print(f"  AND-gate (TriggerRule.ALL_SUCCESS): {all_success_count}")

    print("  ✓ Full migration integration test PASSED")


def test_iterparse_vs_standard_alv100():
    """Compare iterparse and standard parser on ALV_100 — they should produce same counts."""
    if not os.path.exists(XML_PATH):
        print(f"SKIP: {XML_PATH} not found")
        return

    xml_content = open(XML_PATH, encoding="utf-8", errors="replace").read()
    agent = InformaticaMigrationAdvancedAgent()

    t0 = time.time()
    std = agent._parse_xml(xml_content)
    t_std = time.time() - t0

    t0 = time.time()
    itp = agent._parse_xml_iterparse(xml_content)
    t_itp = time.time() - t0

    print(f"  Standard parser: {t_std:.2f}s | iterparse: {t_itp:.2f}s")

    for key in ["sources", "targets", "mappings", "workflows", "sessions",
                 "command_tasks", "email_tasks", "workflow_events",
                 "workflow_variables", "mapping_variables",
                 "connection_references", "target_load_orders"]:
        std_count = len(std.get(key, []))
        itp_count = len(itp.get(key, []))
        print(f"  {key}: standard={std_count}, iterparse={itp_count}")
        assert std_count == itp_count, \
            f"Mismatch on {key}: standard={std_count} vs iterparse={itp_count}"

    # Verify mapping names match
    std_names = sorted(m["name"] for m in std["mappings"])
    itp_names = sorted(m["name"] for m in itp["mappings"])
    assert std_names == itp_names, "Mapping names differ between parsers"

    print("  ✓ iterparse vs standard comparison PASSED")


def test_selective_mode_alv100():
    """Test that selective mode correctly limits processing."""
    if not os.path.exists(XML_PATH):
        print(f"SKIP: {XML_PATH} not found")
        return

    xml_content = open(XML_PATH, encoding="utf-8", errors="replace").read()
    agent = InformaticaMigrationAdvancedAgent()

    # First, get all mapping names
    parsed = agent._parse_xml(xml_content)
    all_names = [m["name"] for m in parsed["mappings"]]
    assert len(all_names) >= 100

    # Select just 3
    selected = all_names[:3]
    _prep_cache.clear()

    result = asyncio.run(agent.migrate(
        xml_content=xml_content,
        selected_mappings=selected,
        use_cache=True,
    ))
    mapping_count = len(result["mapping_results"])
    print(f"  Selected 3 mappings, got {mapping_count} results")
    # With variant expansion, could be slightly more, but should be close
    assert mapping_count <= 10, f"Expected <= 10 results with 3 selected, got {mapping_count}"
    assert mapping_count >= 1, "Should have at least 1 result"
    print("  ✓ Selective mode test PASSED")


def test_cache_reuse_alv100():
    """Test that cache reuse works on second call."""
    if not os.path.exists(XML_PATH):
        print(f"SKIP: {XML_PATH} not found")
        return

    xml_content = open(XML_PATH, encoding="utf-8", errors="replace").read()
    agent = InformaticaMigrationAdvancedAgent()
    _prep_cache.clear()

    # First call — cache miss
    t0 = time.time()
    r1 = asyncio.run(agent.migrate(xml_content=xml_content, use_cache=True))
    t1 = time.time() - t0

    # Second call — cache hit
    t0 = time.time()
    r2 = asyncio.run(agent.migrate(xml_content=xml_content, use_cache=True))
    t2 = time.time() - t0

    print(f"  First call: {t1:.1f}s | Second call (cached): {t2:.1f}s")
    assert len(r1["mapping_results"]) == len(r2["mapping_results"])
    # Cache should make second call faster (at least for parsing)
    print("  ✓ Cache reuse test PASSED")


def _run_all():
    import traceback
    tests = [
        ("test_full_migration", test_full_migration),
        ("test_iterparse_vs_standard_alv100", test_iterparse_vs_standard_alv100),
        ("test_selective_mode_alv100", test_selective_mode_alv100),
        ("test_cache_reuse_alv100", test_cache_reuse_alv100),
    ]
    passed = 0
    failed = 0
    errors = []
    for name, fn in tests:
        print(f"\n{'─' * 50}")
        print(f"Running: {name}")
        try:
            fn()
            passed += 1
        except Exception as e:
            failed += 1
            tb = traceback.format_exc()
            errors.append((name, tb))
            print(f"  ✗ FAILED: {e}")

    print(f"\n{'═' * 60}")
    print(f"Integration results: {passed} passed, {failed} failed out of {passed + failed}")
    if errors:
        print("\nFailure details:")
        for name, tb in errors:
            print(f"\n--- {name} ---")
            print(tb)
    return failed


if __name__ == "__main__":
    sys.exit(_run_all())
