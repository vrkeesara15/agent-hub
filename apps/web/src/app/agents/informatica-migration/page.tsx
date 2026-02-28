'use client';
import React, { useState, useCallback, useRef } from 'react';
import Link from 'next/link';
import JSZip from 'jszip';
import { Breadcrumb } from '@/components/layout/Breadcrumb';
import { Button } from '@/components/ui/Button';
import { migrateInformatica } from '@/lib/api';
import { InformaticaMigrationResponse } from '@/lib/types';

const SAMPLE_XML = `<?xml version="1.0" encoding="UTF-8"?>
<POWERMART>
  <REPOSITORY NAME="PROD_REPO">
    <FOLDER NAME="ETL_FINANCE">
      <SOURCE NAME="SRC_CUSTOMER_ACCOUNT" DATABASETYPE="Teradata" OWNERNAME="EDW_PRD">
        <SOURCEFIELD NAME="customer_id" DATATYPE="number" PRECISION="10"/>
        <SOURCEFIELD NAME="customer_name" DATATYPE="string" PRECISION="100"/>
        <SOURCEFIELD NAME="account_status" DATATYPE="string" PRECISION="20"/>
        <SOURCEFIELD NAME="revenue" DATATYPE="decimal" PRECISION="15" SCALE="2"/>
        <SOURCEFIELD NAME="last_updated" DATATYPE="date/time"/>
      </SOURCE>
      <TARGET NAME="TGT_DIM_CUSTOMER" DATABASETYPE="Oracle" OWNERNAME="DW">
        <TARGETFIELD NAME="customer_key" DATATYPE="number" PRECISION="10" KEYTYPE="PRIMARY KEY"/>
        <TARGETFIELD NAME="customer_id" DATATYPE="number" PRECISION="10"/>
        <TARGETFIELD NAME="customer_name" DATATYPE="string" PRECISION="100"/>
        <TARGETFIELD NAME="account_status" DATATYPE="string" PRECISION="20"/>
        <TARGETFIELD NAME="revenue" DATATYPE="decimal" PRECISION="15" SCALE="2"/>
        <TARGETFIELD NAME="effective_start_date" DATATYPE="date/time"/>
        <TARGETFIELD NAME="effective_end_date" DATATYPE="date/time"/>
        <TARGETFIELD NAME="is_current" DATATYPE="string" PRECISION="1"/>
      </TARGET>
      <MAPPING NAME="m_Customer_SCD2" DESCRIPTION="SCD Type 2 for customer dimension">
        <TRANSFORMATION NAME="SQ_SRC_CUSTOMER" TYPE="Source Qualifier" DESCRIPTION="Source qualifier">
          <TRANSFORMFIELD NAME="customer_id" DATATYPE="number" PORTTYPE="INPUT/OUTPUT"/>
          <TRANSFORMFIELD NAME="customer_name" DATATYPE="string" PORTTYPE="INPUT/OUTPUT"/>
          <TRANSFORMFIELD NAME="account_status" DATATYPE="string" PORTTYPE="INPUT/OUTPUT"/>
          <TRANSFORMFIELD NAME="revenue" DATATYPE="decimal" PORTTYPE="INPUT/OUTPUT"/>
          <TRANSFORMFIELD NAME="last_updated" DATATYPE="date/time" PORTTYPE="INPUT/OUTPUT"/>
        </TRANSFORMATION>
        <TRANSFORMATION NAME="EXP_TRANSFORM" TYPE="Expression" DESCRIPTION="Business logic">
          <TRANSFORMFIELD NAME="customer_id" DATATYPE="number" PORTTYPE="INPUT/OUTPUT"/>
          <TRANSFORMFIELD NAME="customer_name_clean" DATATYPE="string" PORTTYPE="OUTPUT" EXPRESSION="UPPER(LTRIM(RTRIM(customer_name)))"/>
          <TRANSFORMFIELD NAME="status_flag" DATATYPE="string" PORTTYPE="OUTPUT" EXPRESSION="IIF(account_status='ACTIVE', 'Y', 'N')"/>
          <TRANSFORMFIELD NAME="revenue_adjusted" DATATYPE="decimal" PORTTYPE="OUTPUT" EXPRESSION="IIF(revenue &lt; 0, 0, revenue)"/>
          <TRANSFORMFIELD NAME="load_date" DATATYPE="date/time" PORTTYPE="OUTPUT" EXPRESSION="SYSDATE"/>
        </TRANSFORMATION>
        <TRANSFORMATION NAME="LKP_EXISTING" TYPE="Lookup" DESCRIPTION="Lookup existing records">
          <TRANSFORMFIELD NAME="customer_id" DATATYPE="number" PORTTYPE="INPUT"/>
          <TRANSFORMFIELD NAME="existing_key" DATATYPE="number" PORTTYPE="OUTPUT"/>
          <TABLEATTRIBUTE NAME="Lookup Sql Override" VALUE="SELECT customer_key, customer_id FROM TGT_DIM_CUSTOMER WHERE is_current='Y'"/>
        </TRANSFORMATION>
        <TRANSFORMATION NAME="RTR_NEW_VS_CHANGED" TYPE="Router" DESCRIPTION="Route new vs changed records">
          <TABLEATTRIBUTE NAME="Group Filter Condition_NEW" VALUE="ISNULL(existing_key)"/>
          <TABLEATTRIBUTE NAME="Group Filter Condition_CHANGED" VALUE="NOT ISNULL(existing_key)"/>
        </TRANSFORMATION>
        <TRANSFORMATION NAME="UPD_SCD_STRATEGY" TYPE="Update Strategy" DESCRIPTION="SCD Type 2 update strategy">
          <TRANSFORMFIELD NAME="update_flag" DATATYPE="number" PORTTYPE="OUTPUT" EXPRESSION="DD_UPDATE"/>
        </TRANSFORMATION>
        <TRANSFORMATION NAME="SEQ_CUSTOMER_KEY" TYPE="Sequence Generator" DESCRIPTION="Generate surrogate key">
          <TRANSFORMFIELD NAME="NEXTVAL" DATATYPE="number" PORTTYPE="OUTPUT"/>
        </TRANSFORMATION>
        <TRANSFORMATION NAME="AGG_REVENUE" TYPE="Aggregator" DESCRIPTION="Aggregate revenue by status">
          <TRANSFORMFIELD NAME="account_status" DATATYPE="string" PORTTYPE="INPUT/OUTPUT"/>
          <TRANSFORMFIELD NAME="total_revenue" DATATYPE="decimal" PORTTYPE="OUTPUT" EXPRESSION="SUM(revenue)"/>
          <TRANSFORMFIELD NAME="customer_count" DATATYPE="number" PORTTYPE="OUTPUT" EXPRESSION="COUNT(customer_id)"/>
        </TRANSFORMATION>
      </MAPPING>
      <WORKFLOW NAME="wf_Customer_Dimension_Load" DESCRIPTION="Daily customer dimension SCD2 load">
        <SCHEDULER SCHEDULETYPE="DAILY" REPEAT="Daily" STARTTIME="02:00:00"/>
        <SESSION NAME="s_m_Customer_SCD2" MAPPINGNAME="m_Customer_SCD2" DESCRIPTION="Run customer SCD2 mapping"/>
      </WORKFLOW>
      <CONNECTOR FROMINSTANCE="SQ_SRC_CUSTOMER" FROMFIELD="customer_id" TOINSTANCE="EXP_TRANSFORM" TOFIELD="customer_id"/>
      <CONNECTOR FROMINSTANCE="EXP_TRANSFORM" FROMFIELD="customer_id" TOINSTANCE="LKP_EXISTING" TOFIELD="customer_id"/>
      <CONNECTOR FROMINSTANCE="LKP_EXISTING" FROMFIELD="existing_key" TOINSTANCE="RTR_NEW_VS_CHANGED" TOFIELD="existing_key"/>
      <CONNECTOR FROMINSTANCE="RTR_NEW_VS_CHANGED" FROMFIELD="customer_id" TOINSTANCE="UPD_SCD_STRATEGY" TOFIELD="customer_id"/>
    </FOLDER>
  </REPOSITORY>
</POWERMART>`;

type ActiveTab = 'report' | 'sql' | 'dag' | 'map' | 'scd';
type InputMode = 'upload' | 'paste';

export default function InformaticaMigrationPage() {
  const [xmlInput, setXmlInput] = useState('');
  const [fileName, setFileName] = useState<string | null>(null);
  const [result, setResult] = useState<InformaticaMigrationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>('report');
  const [inputMode, setInputMode] = useState<InputMode>('upload');
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((file: File) => {
    if (!file.name.endsWith('.xml') && !file.name.endsWith('.XML')) {
      setError('Please upload an XML file (.xml)');
      return;
    }
    setFileName(file.name);
    setError(null);
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      setXmlInput(text);
    };
    reader.onerror = () => setError('Failed to read file');
    reader.readAsText(file);
  }, []);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    if (e.type === 'dragleave') setDragActive(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.[0]) handleFile(e.dataTransfer.files[0]);
  }, [handleFile]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) handleFile(e.target.files[0]);
  }, [handleFile]);

  const handleMigrate = useCallback(async () => {
    if (!xmlInput.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setActiveTab('report');
    try {
      const data = await migrateInformatica(xmlInput, fileName || 'workflow.xml');
      if (data.error) {
        setError(data.error);
      } else {
        setResult(data);
      }
    } catch {
      setError('Failed to migrate. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  }, [xmlInput, fileName]);

  const loadSample = () => {
    setXmlInput(SAMPLE_XML);
    setFileName('sample_customer_scd2.xml');
    setResult(null);
    setError(null);
  };

  const clearInput = () => {
    setXmlInput('');
    setFileName(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ── Download helpers ──
  const downloadFile = (content: string, name: string) => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const buildTransformMapCSV = (r: InformaticaMigrationResponse) => {
    const header = 'Informatica Type,GCP Equivalent,Conversion Type\n';
    const rows = (r.transformation_map || []).map(
      (t) => `"${t.informatica}","${t.gcp}","${t.type}"`
    ).join('\n');
    return header + rows;
  };

  const buildReportMarkdown = (r: InformaticaMigrationResponse) => {
    const { good, attention } = getReportData(r);
    const sqlPct = r.analysis?.total_transformations
      ? Math.round((r.analysis.sql_convertible / r.analysis.total_transformations) * 100)
      : 0;
    let md = `# Informatica Migration Report\n`;
    md += `**Workflow:** ${r.workflow_name || 'N/A'}\n`;
    md += `**Complexity:** ${(r.complexity || 'N/A').toUpperCase()}\n`;
    md += `**Conversion Score:** ${sqlPct}%\n\n`;
    md += `## Summary\n${r.summary || 'N/A'}\n\n`;
    md += `## Analysis\n`;
    md += `| Metric | Value |\n|---|---|\n`;
    md += `| Total Transformations | ${r.analysis?.total_transformations || 0} |\n`;
    md += `| SQL Convertible | ${r.analysis?.sql_convertible || 0} |\n`;
    md += `| Needs Dataflow | ${r.analysis?.needs_dataflow || 0} |\n`;
    md += `| SCD Pattern Detected | ${r.analysis?.has_scd_pattern ? 'Yes' : 'No'} |\n`;
    md += `| Sources | ${(r.sources || []).join(', ') || 'N/A'} |\n`;
    md += `| Targets | ${(r.targets || []).join(', ') || 'N/A'} |\n\n`;
    if (good.length > 0) {
      md += `## What Went Well\n`;
      good.forEach((g) => { md += `- **${g.label}** — ${g.detail}\n`; });
      md += '\n';
    }
    if (attention.length > 0) {
      md += `## Needs Attention\n`;
      attention.forEach((a) => { md += `- **[${a.severity.toUpperCase()}]** ${a.label} — ${a.detail}\n`; });
      md += '\n';
    }
    if (r.unsupported_patterns?.length) {
      md += `## Unsupported Patterns\n`;
      r.unsupported_patterns.forEach((p) => { md += `- **${p.pattern}** — ${p.suggestion}\n`; });
      md += '\n';
    }
    if (r.recommendations?.length) {
      md += `## Recommendations\n`;
      r.recommendations.forEach((rec, i) => { md += `${i + 1}. ${rec}\n`; });
    }
    return md;
  };

  const getBaseFilename = () => {
    if (fileName) return fileName.replace(/\.(xml|XML)$/, '');
    if (result?.workflow_name) return result.workflow_name;
    return 'informatica_migration';
  };

  const handleDownloadAll = async () => {
    if (!result) return;
    const base = getBaseFilename();
    const zip = new JSZip();
    zip.file(`${base}_bigquery.sql`, result.bigquery_sql || '-- No SQL generated');
    zip.file(`${base}_airflow_dag.py`, result.airflow_dag || '# No DAG generated');
    zip.file(`${base}_transformation_map.csv`, buildTransformMapCSV(result));
    zip.file(`${base}_migration_report.md`, buildReportMarkdown(result));
    if (result.scd_merge) {
      zip.file(`${base}_scd_merge.sql`, result.scd_merge);
    }
    const blob = await zip.generateAsync({ type: 'blob' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${base}_gcp_migration.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const complexityColor = (c: string) => {
    if (c === 'high') return 'text-red-600 bg-red-50 dark:bg-red-950 border-red-200';
    if (c === 'medium') return 'text-amber-600 bg-amber-50 dark:bg-amber-950 border-amber-200';
    return 'text-green-600 bg-green-50 dark:bg-green-950 border-green-200';
  };

  const complexityIcon = (c: string) => {
    if (c === 'high') return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
    );
    if (c === 'medium') return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
    );
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
    );
  };

  // Compute report data from result
  const getReportData = (r: InformaticaMigrationResponse) => {
    const good: { label: string; detail: string; icon: 'check' | 'bolt' | 'shield' | 'clock' }[] = [];
    const attention: { label: string; detail: string; severity: 'warning' | 'critical' }[] = [];

    const sqlPct = r.analysis?.total_transformations
      ? Math.round((r.analysis.sql_convertible / r.analysis.total_transformations) * 100)
      : 0;

    if (sqlPct >= 70) good.push({ label: `${sqlPct}% SQL Convertible`, detail: `${r.analysis?.sql_convertible} of ${r.analysis?.total_transformations} transformations convert directly to BigQuery SQL`, icon: 'check' });
    else if (sqlPct > 0) attention.push({ label: `Only ${sqlPct}% SQL Convertible`, detail: `${r.analysis?.total_transformations - r.analysis?.sql_convertible} transformations need Dataflow or manual review`, severity: 'warning' });

    if (r.analysis?.has_scd_pattern) good.push({ label: 'SCD Pattern Detected', detail: 'MERGE statement auto-generated for slowly changing dimension handling', icon: 'shield' });

    if (r.workflow_name) good.push({ label: 'Workflow Preserved', detail: `Workflow "${r.workflow_name}" scheduling converted to Airflow DAG`, icon: 'clock' });

    if (r.sources?.length > 0) good.push({ label: `${r.sources.length} Source(s) Mapped`, detail: `Sources: ${r.sources.join(', ')}`, icon: 'bolt' });

    if (r.targets?.length > 0) good.push({ label: `${r.targets.length} Target(s) Mapped`, detail: `Targets: ${r.targets.join(', ')}`, icon: 'bolt' });

    if (r.bigquery_sql && r.bigquery_sql.length > 50) good.push({ label: 'BigQuery SQL Generated', detail: 'Complete SQL output ready for BigQuery execution', icon: 'check' });

    if (r.airflow_dag && r.airflow_dag.length > 50) good.push({ label: 'Airflow DAG Generated', detail: 'Cloud Composer DAG with task dependencies and scheduling', icon: 'check' });

    if (r.analysis?.needs_dataflow > 0) attention.push({ label: `${r.analysis.needs_dataflow} Transformation(s) Need Dataflow`, detail: 'Complex transformations require Apache Beam / Dataflow pipelines instead of SQL', severity: 'warning' });

    if (r.unsupported_patterns?.length > 0) attention.push({ label: `${r.unsupported_patterns.length} Unsupported Pattern(s)`, detail: r.unsupported_patterns.map(p => p.pattern).join(', '), severity: 'critical' });

    if (r.complexity === 'high') attention.push({ label: 'High Complexity Migration', detail: 'This workflow has complex logic that may require additional manual review and testing', severity: 'critical' });

    if (r.transformation_map?.some(t => t.type === 'dataflow')) attention.push({ label: 'Dataflow Components Required', detail: 'Some transformations need Dataflow (Apache Beam) pipelines for correct conversion', severity: 'warning' });

    return { good, attention };
  };

  const GoodIcon = ({ type }: { type: 'check' | 'bolt' | 'shield' | 'clock' }) => {
    if (type === 'check') return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16A34A" strokeWidth="2.5" strokeLinecap="round"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>;
    if (type === 'bolt') return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16A34A" strokeWidth="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>;
    if (type === 'shield') return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16A34A" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>;
    return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16A34A" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>;
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/agents/code-accelerator" className="flex items-center gap-1 text-sm text-text-secondary hover:text-brand-blue transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
            Back to Gcp Launchpad
          </Link>
          <span className="text-surface-border">|</span>
          <h1 className="text-lg font-bold text-text-primary tracking-wide">Informatica Migration</h1>
        </div>
        <Breadcrumb items={[{ label: 'Home', href: '/' }, { label: 'Gcp Launchpad', href: '/agents/code-accelerator' }, { label: 'Informatica Migration' }]} />
      </div>

      {/* Info Banner */}
      <div className="mb-6 p-4 bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800 rounded-card">
        <div className="flex items-start gap-3">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="mt-0.5 flex-shrink-0" stroke="#6366F1" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
          <div>
            <p className="text-sm font-bold text-text-primary">Informatica PowerCenter to GCP Migration</p>
            <p className="text-xs text-text-secondary mt-1">
              Upload your Informatica XML export to convert it into BigQuery SQL + Cloud Composer (Airflow) DAGs.
              Transformations are mapped to BigQuery ELT. Complex logic flags Dataflow / Dataproc. SCD patterns generate MERGE statements.
            </p>
          </div>
        </div>
      </div>

      {/* Input Mode Toggle */}
      <div className="flex items-center gap-2 mb-4">
        <div className="inline-flex bg-surface-bg border border-surface-border rounded-button overflow-hidden">
          <button
            onClick={() => setInputMode('upload')}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              inputMode === 'upload'
                ? 'bg-brand-blue text-white'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            <span className="flex items-center gap-1.5">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              Upload File
            </span>
          </button>
          <button
            onClick={() => setInputMode('paste')}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              inputMode === 'paste'
                ? 'bg-brand-blue text-white'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            <span className="flex items-center gap-1.5">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>
              Paste XML
            </span>
          </button>
        </div>
        <div className="flex-1" />
        <button onClick={loadSample} className="text-xs text-brand-blue hover:underline flex items-center gap-1">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          Load Sample XML
        </button>
        {xmlInput && (
          <button onClick={clearInput} className="text-xs text-red-500 hover:underline flex items-center gap-1">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            Clear
          </button>
        )}
      </div>

      {/* Upload Zone */}
      {inputMode === 'upload' && (
        <div className="mb-6">
          <input
            ref={fileInputRef}
            type="file"
            accept=".xml,.XML"
            onChange={handleFileInput}
            className="hidden"
          />
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`relative border-2 border-dashed rounded-card p-10 text-center cursor-pointer transition-all ${
              dragActive
                ? 'border-brand-blue bg-blue-50/50 dark:bg-blue-950/20'
                : fileName
                  ? 'border-green-400 bg-green-50/30 dark:bg-green-950/10'
                  : 'border-surface-border hover:border-brand-blue/50 hover:bg-surface-bg/50'
            }`}
          >
            {fileName ? (
              <div className="flex flex-col items-center gap-3">
                <div className="w-14 h-14 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#16A34A" strokeWidth="2" strokeLinecap="round">
                    <path d="M22 11.08V12a10 10 0 11-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-bold text-text-primary">{fileName}</p>
                  <p className="text-xs text-text-secondary mt-1">{(xmlInput.length / 1024).toFixed(1)} KB loaded</p>
                </div>
                <p className="text-xs text-text-muted">Click or drop another file to replace</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <div className="w-14 h-14 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#6366F1" strokeWidth="1.5" strokeLinecap="round">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-bold text-text-primary">Drop your Informatica XML file here</p>
                  <p className="text-xs text-text-secondary mt-1">or click to browse files</p>
                </div>
                <span className="inline-block text-[10px] font-medium text-text-muted bg-surface-bg px-3 py-1 rounded-full border border-surface-border">
                  Supports .xml files from PowerCenter Export
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Paste Zone */}
      {inputMode === 'paste' && (
        <div className="mb-6">
          <textarea
            value={xmlInput}
            onChange={(e) => { setXmlInput(e.target.value); setFileName(null); }}
            placeholder="Paste your Informatica PowerCenter XML export here..."
            className="w-full h-64 p-4 bg-surface-card border border-surface-border rounded-card text-sm font-mono text-text-primary placeholder-text-muted resize-y focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
          />
        </div>
      )}

      {/* Migrate Button */}
      <div className="flex justify-center mb-8">
        <Button
          variant="primary"
          size="lg"
          onClick={handleMigrate}
          disabled={loading || !xmlInput.trim()}
          className="px-12"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
              Analyzing & Migrating...
            </span>
          ) : 'Migrate to GCP'}
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-card text-sm text-red-700 dark:text-red-400 mb-6 flex items-start gap-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mt-0.5 flex-shrink-0"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-4">
            <div className="relative">
              <svg className="animate-spin h-12 w-12 text-brand-blue" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-text-primary">Analyzing Informatica XML...</p>
              <p className="text-xs text-text-secondary mt-1">Parsing transformations, generating BigQuery SQL & Airflow DAG</p>
            </div>
          </div>
        </div>
      )}

      {/* ──────────── RESULTS ──────────── */}
      {result && !loading && (
        <div className="space-y-6">

          {/* ── Result Header with Download All + Complexity Badge ── */}
          <div className="flex items-center justify-between flex-wrap gap-3">
            <h2 className="text-lg font-bold text-text-primary flex items-center gap-2">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6366F1" strokeWidth="2" strokeLinecap="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              Migration Results
              {fileName && <span className="text-sm font-normal text-text-secondary ml-2">({fileName})</span>}
            </h2>
            <div className="flex items-center gap-3">
              <button
                onClick={handleDownloadAll}
                className="flex items-center gap-2 px-4 py-2 rounded-full border border-brand-blue text-brand-blue text-sm font-bold hover:bg-brand-blue hover:text-white transition-colors"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                Download All (.zip)
              </button>
              <div className={`flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-bold uppercase ${complexityColor(result.complexity)}`}>
                {complexityIcon(result.complexity)}
                {result.complexity} Complexity
              </div>
            </div>
          </div>

          {/* ── Stats Cards ── */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="p-4 bg-surface-card border border-surface-border rounded-card text-center">
              <div className="text-2xl font-bold text-brand-blue">{result.analysis?.total_transformations || 0}</div>
              <div className="text-xs text-text-secondary mt-1">Transformations</div>
            </div>
            <div className="p-4 bg-surface-card border border-surface-border rounded-card text-center">
              <div className="text-2xl font-bold text-green-600">{result.analysis?.sql_convertible || 0}</div>
              <div className="text-xs text-text-secondary mt-1">SQL Convertible</div>
            </div>
            <div className="p-4 bg-surface-card border border-surface-border rounded-card text-center">
              <div className="text-2xl font-bold text-amber-600">{result.analysis?.needs_dataflow || 0}</div>
              <div className="text-xs text-text-secondary mt-1">Needs Dataflow</div>
            </div>
            <div className="p-4 bg-surface-card border border-surface-border rounded-card text-center">
              <div className="text-2xl font-bold text-purple-600">{result.sources?.length || 0} / {result.targets?.length || 0}</div>
              <div className="text-xs text-text-secondary mt-1">Sources / Targets</div>
            </div>
            <div className="p-4 bg-surface-card border border-surface-border rounded-card text-center">
              <div className="text-2xl font-bold text-indigo-600">{result.transformation_map?.length || 0}</div>
              <div className="text-xs text-text-secondary mt-1">Mappings Created</div>
            </div>
          </div>

          {/* ── Summary ── */}
          <div className="p-4 bg-surface-card border border-surface-border rounded-card">
            <p className="text-sm text-text-primary leading-relaxed">{result.summary}</p>
          </div>

          {/* ── Tabs ── */}
          <div className="flex gap-1 border-b border-surface-border overflow-x-auto">
            {([
              { key: 'report' as ActiveTab, label: 'Migration Report', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 17H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><path d="M15 3h4a2 2 0 012 2v10a2 2 0 01-2 2h-4"/><polyline points="13 15 9 19 5 15"/><line x1="9" y1="12" x2="9" y2="19"/></svg> },
              { key: 'sql' as ActiveTab, label: 'BigQuery SQL', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg> },
              { key: 'dag' as ActiveTab, label: 'Airflow DAG', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v6m0 6v6m8.66-13.5l-5.2 3m-5 2.88l-5.2 3m10.4 0l-5.2-3m-4.92-2.88l-5.2-3"/></svg> },
              { key: 'map' as ActiveTab, label: 'Transformation Map', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg> },
              ...(result.scd_merge ? [{ key: 'scd' as ActiveTab, label: 'SCD MERGE', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg> }] : []),
            ]).map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                  activeTab === tab.key
                    ? 'border-brand-blue text-brand-blue'
                    : 'border-transparent text-text-secondary hover:text-text-primary'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          {/* ══════ Tab: Migration Report ══════ */}
          {activeTab === 'report' && (() => {
            const { good, attention } = getReportData(result);
            return (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* What Went Well */}
                <div className="bg-gradient-to-br from-green-50 to-emerald-50/50 dark:from-green-950/20 dark:to-emerald-950/10 border border-green-200 dark:border-green-800 rounded-card overflow-hidden">
                  <div className="px-5 py-4 border-b border-green-200 dark:border-green-800 bg-green-100/50 dark:bg-green-900/20">
                    <h3 className="text-sm font-bold text-green-800 dark:text-green-300 flex items-center gap-2">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16A34A" strokeWidth="2.5" strokeLinecap="round">
                        <path d="M22 11.08V12a10 10 0 11-5.93-9.14"/>
                        <polyline points="22 4 12 14.01 9 11.01"/>
                      </svg>
                      What Went Well ({good.length})
                    </h3>
                  </div>
                  <div className="p-5 space-y-4">
                    {good.length === 0 ? (
                      <p className="text-sm text-text-muted">No highlights for this migration.</p>
                    ) : good.map((item, i) => (
                      <div key={i} className="flex items-start gap-3 group">
                        <div className="mt-0.5 flex-shrink-0 w-8 h-8 rounded-full bg-green-100 dark:bg-green-900/40 flex items-center justify-center">
                          <GoodIcon type={item.icon} />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-green-800 dark:text-green-300">{item.label}</p>
                          <p className="text-xs text-green-700/80 dark:text-green-400/70 mt-0.5 leading-relaxed">{item.detail}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Needs Attention */}
                <div className="bg-gradient-to-br from-amber-50 to-orange-50/50 dark:from-amber-950/20 dark:to-orange-950/10 border border-amber-200 dark:border-amber-800 rounded-card overflow-hidden">
                  <div className="px-5 py-4 border-b border-amber-200 dark:border-amber-800 bg-amber-100/50 dark:bg-amber-900/20">
                    <h3 className="text-sm font-bold text-amber-800 dark:text-amber-300 flex items-center gap-2">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#D97706" strokeWidth="2">
                        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                        <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                      </svg>
                      Needs Attention ({attention.length})
                    </h3>
                  </div>
                  <div className="p-5 space-y-4">
                    {attention.length === 0 ? (
                      <div className="flex items-center gap-3 text-sm text-green-700 dark:text-green-400">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                        No issues found. Migration looks clean!
                      </div>
                    ) : attention.map((item, i) => (
                      <div key={i} className="flex items-start gap-3">
                        <div className={`mt-0.5 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                          item.severity === 'critical'
                            ? 'bg-red-100 dark:bg-red-900/40'
                            : 'bg-amber-100 dark:bg-amber-900/40'
                        }`}>
                          {item.severity === 'critical' ? (
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#DC2626" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                          ) : (
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#D97706" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                          )}
                        </div>
                        <div className="min-w-0">
                          <p className={`text-sm font-semibold ${
                            item.severity === 'critical' ? 'text-red-700 dark:text-red-400' : 'text-amber-800 dark:text-amber-300'
                          }`}>
                            {item.label}
                            <span className={`ml-2 inline-block text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-full ${
                              item.severity === 'critical' ? 'bg-red-200/60 text-red-700 dark:bg-red-800/40 dark:text-red-300' : 'bg-amber-200/60 text-amber-700 dark:bg-amber-800/40 dark:text-amber-300'
                            }`}>{item.severity}</span>
                          </p>
                          <p className="text-xs text-amber-700/80 dark:text-amber-400/70 mt-0.5 leading-relaxed">{item.detail}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Recommendations - spans full width */}
                {result.recommendations && result.recommendations.length > 0 && (
                  <div className="lg:col-span-2 bg-gradient-to-br from-blue-50 to-indigo-50/50 dark:from-blue-950/20 dark:to-indigo-950/10 border border-blue-200 dark:border-blue-800 rounded-card overflow-hidden">
                    <div className="px-5 py-4 border-b border-blue-200 dark:border-blue-800 bg-blue-100/50 dark:bg-blue-900/20">
                      <h3 className="text-sm font-bold text-blue-800 dark:text-blue-300 flex items-center gap-2">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                        Recommendations
                      </h3>
                    </div>
                    <div className="p-5">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {result.recommendations.map((rec, i) => (
                          <div key={i} className="flex items-start gap-2.5 p-3 bg-white/50 dark:bg-black/10 rounded-lg border border-blue-100 dark:border-blue-800/50">
                            <div className="mt-0.5 flex-shrink-0 w-5 h-5 rounded-full bg-blue-200 dark:bg-blue-800 flex items-center justify-center text-[10px] font-bold text-blue-700 dark:text-blue-300">{i + 1}</div>
                            <p className="text-sm text-blue-800 dark:text-blue-300 leading-relaxed">{rec}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Conversion Score Bar - full width */}
                <div className="lg:col-span-2 p-5 bg-surface-card border border-surface-border rounded-card">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-bold text-text-primary">Overall Conversion Score</h3>
                    <span className="text-sm font-bold text-brand-blue">
                      {result.analysis?.total_transformations
                        ? Math.round((result.analysis.sql_convertible / result.analysis.total_transformations) * 100)
                        : 0}%
                    </span>
                  </div>
                  <div className="w-full h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-700 bg-gradient-to-r from-green-500 to-emerald-400"
                      style={{
                        width: `${result.analysis?.total_transformations
                          ? Math.round((result.analysis.sql_convertible / result.analysis.total_transformations) * 100)
                          : 0}%`
                      }}
                    />
                  </div>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-text-muted">SQL convertible transformations vs total</span>
                    <span className="text-xs text-text-secondary">{result.analysis?.sql_convertible || 0} / {result.analysis?.total_transformations || 0} transformations</span>
                  </div>
                </div>

                {/* Download Section - full width */}
                <div className="lg:col-span-2 p-5 bg-gradient-to-r from-indigo-50 to-blue-50 dark:from-indigo-950/20 dark:to-blue-950/20 border border-indigo-200 dark:border-indigo-800 rounded-card">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-indigo-800 dark:text-indigo-300 flex items-center gap-2">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        Download Generated Files
                      </h3>
                      <p className="text-xs text-indigo-600/70 dark:text-indigo-400/60 mt-1">
                        Download all migration artifacts as a single ZIP package
                      </p>
                    </div>
                    <button
                      onClick={handleDownloadAll}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-button bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                      Download All (.zip)
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2 mt-4">
                    {[
                      { label: 'BigQuery SQL', ext: '.sql', action: () => downloadFile(result.bigquery_sql, `${getBaseFilename()}_bigquery.sql`) },
                      { label: 'Airflow DAG', ext: '.py', action: () => downloadFile(result.airflow_dag, `${getBaseFilename()}_airflow_dag.py`) },
                      { label: 'Transform Map', ext: '.csv', action: () => downloadFile(buildTransformMapCSV(result), `${getBaseFilename()}_transformation_map.csv`) },
                      { label: 'Migration Report', ext: '.md', action: () => downloadFile(buildReportMarkdown(result), `${getBaseFilename()}_migration_report.md`) },
                      ...(result.scd_merge ? [{ label: 'SCD MERGE', ext: '.sql', action: () => downloadFile(result.scd_merge, `${getBaseFilename()}_scd_merge.sql`) }] : []),
                    ].map((item) => (
                      <button
                        key={item.label}
                        onClick={item.action}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white/70 dark:bg-black/20 border border-indigo-200 dark:border-indigo-700 text-indigo-700 dark:text-indigo-300 hover:bg-white dark:hover:bg-black/40 transition-colors"
                      >
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        {item.label} <span className="opacity-60">{item.ext}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            );
          })()}

          {/* ══════ Tab: BigQuery SQL ══════ */}
          {activeTab === 'sql' && (
            <div className="bg-surface-card border border-surface-border rounded-card overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-surface-border bg-surface-bg/50">
                <span className="text-xs font-medium text-text-secondary uppercase tracking-wide">BigQuery SQL Output</span>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => downloadFile(result.bigquery_sql, `${getBaseFilename()}_bigquery.sql`)}
                    className="text-xs text-brand-blue hover:underline flex items-center gap-1"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    Download .sql
                  </button>
                  <button
                    onClick={() => navigator.clipboard.writeText(result.bigquery_sql)}
                    className="text-xs text-brand-blue hover:underline flex items-center gap-1"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                    Copy
                  </button>
                </div>
              </div>
              <pre className="p-4 text-sm font-mono text-text-primary overflow-x-auto max-h-[500px] overflow-y-auto whitespace-pre">
                {result.bigquery_sql}
              </pre>
            </div>
          )}

          {/* ══════ Tab: Airflow DAG ══════ */}
          {activeTab === 'dag' && (
            <div className="bg-surface-card border border-surface-border rounded-card overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-surface-border bg-surface-bg/50">
                <span className="text-xs font-medium text-text-secondary uppercase tracking-wide">Airflow DAG (Python)</span>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => downloadFile(result.airflow_dag, `${getBaseFilename()}_airflow_dag.py`)}
                    className="text-xs text-brand-blue hover:underline flex items-center gap-1"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    Download .py
                  </button>
                  <button
                    onClick={() => navigator.clipboard.writeText(result.airflow_dag)}
                    className="text-xs text-brand-blue hover:underline flex items-center gap-1"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                    Copy
                  </button>
                </div>
              </div>
              <pre className="p-4 text-sm font-mono text-text-primary overflow-x-auto max-h-[500px] overflow-y-auto whitespace-pre">
                {result.airflow_dag}
              </pre>
            </div>
          )}

          {/* ══════ Tab: SCD MERGE ══════ */}
          {activeTab === 'scd' && result.scd_merge && (
            <div className="bg-surface-card border border-surface-border rounded-card overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-surface-border bg-surface-bg/50">
                <span className="text-xs font-medium text-text-secondary uppercase tracking-wide">SCD Type 2 MERGE Statement</span>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => downloadFile(result.scd_merge, `${getBaseFilename()}_scd_merge.sql`)}
                    className="text-xs text-brand-blue hover:underline flex items-center gap-1"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    Download .sql
                  </button>
                  <button
                    onClick={() => navigator.clipboard.writeText(result.scd_merge)}
                    className="text-xs text-brand-blue hover:underline flex items-center gap-1"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                    Copy
                  </button>
                </div>
              </div>
              <pre className="p-4 text-sm font-mono text-text-primary overflow-x-auto max-h-[500px] overflow-y-auto whitespace-pre">
                {result.scd_merge}
              </pre>
            </div>
          )}

          {/* ══════ Tab: Transformation Map ══════ */}
          {activeTab === 'map' && (
            <div className="bg-surface-card border border-surface-border rounded-card overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-surface-border bg-surface-bg/50">
                <span className="text-xs font-medium text-text-secondary uppercase tracking-wide">Informatica to GCP Transformation Mapping</span>
                <button
                  onClick={() => downloadFile(buildTransformMapCSV(result), `${getBaseFilename()}_transformation_map.csv`)}
                  className="text-xs text-brand-blue hover:underline flex items-center gap-1"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                  Download .csv
                </button>
              </div>
              <div className="p-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-border">
                      <th className="text-left py-2.5 px-3 text-text-secondary font-medium">Informatica Type</th>
                      <th className="text-left py-2.5 px-3 text-text-secondary font-medium">GCP Equivalent</th>
                      <th className="text-left py-2.5 px-3 text-text-secondary font-medium">Conversion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.transformation_map?.map((item, i) => (
                      <tr key={i} className="border-b border-surface-border/50 last:border-0 hover:bg-surface-bg/30 transition-colors">
                        <td className="py-2.5 px-3 font-mono text-text-primary">{item.informatica}</td>
                        <td className="py-2.5 px-3 text-text-primary">{item.gcp}</td>
                        <td className="py-2.5 px-3">
                          <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            item.type === 'sql' ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' :
                            item.type === 'dataflow' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300' :
                            'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                          }`}>
                            {item.type}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Unsupported Patterns (always visible below tabs) ── */}
          {result.unsupported_patterns && result.unsupported_patterns.length > 0 && activeTab !== 'report' && (
            <div className="p-4 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-card">
              <h3 className="text-sm font-bold text-red-700 dark:text-red-400 mb-3 flex items-center gap-2">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                  <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
                Unsupported Patterns ({result.unsupported_patterns.length})
              </h3>
              {result.unsupported_patterns.map((p, i) => (
                <div key={i} className="mb-2 last:mb-0">
                  <span className="text-sm font-medium text-red-700 dark:text-red-400">{p.pattern}</span>
                  <p className="text-xs text-red-600 dark:text-red-500 mt-0.5">{p.suggestion}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
