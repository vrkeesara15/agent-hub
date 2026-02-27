'use client';
import React, { useState, useCallback } from 'react';
import Link from 'next/link';
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
          <TRANSFORMFIELD NAME="revenue_adjusted" DATATYPE="decimal" PORTTYPE="OUTPUT" EXPRESSION="IIF(revenue < 0, 0, revenue)"/>
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

type ActiveTab = 'sql' | 'dag' | 'map' | 'scd';

export default function InformaticaMigrationPage() {
  const [xmlInput, setXmlInput] = useState('');
  const [result, setResult] = useState<InformaticaMigrationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>('sql');

  const handleMigrate = useCallback(async () => {
    if (!xmlInput.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await migrateInformatica(xmlInput, 'workflow.xml');
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
  }, [xmlInput]);

  const loadSample = () => {
    setXmlInput(SAMPLE_XML);
    setResult(null);
    setError(null);
  };

  const complexityColor = (c: string) => {
    if (c === 'high') return 'text-red-600 bg-red-50 dark:bg-red-950 border-red-200';
    if (c === 'medium') return 'text-amber-600 bg-amber-50 dark:bg-amber-950 border-amber-200';
    return 'text-green-600 bg-green-50 dark:bg-green-950 border-green-200';
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-1 text-sm text-text-secondary hover:text-brand-blue transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
            Back
          </Link>
          <span className="text-surface-border">|</span>
          <h1 className="text-lg font-bold text-text-primary uppercase tracking-wide">Informatica Migration</h1>
        </div>
        <Breadcrumb items={[{ label: 'Home', href: '/' }, { label: 'Informatica Migration' }]} />
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

      {/* XML Input */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-bold text-text-primary uppercase tracking-wide">
            Informatica XML
          </label>
          <button onClick={loadSample} className="text-xs text-brand-blue hover:underline">
            Load Sample XML
          </button>
        </div>
        <textarea
          value={xmlInput}
          onChange={(e) => setXmlInput(e.target.value)}
          placeholder="Paste your Informatica PowerCenter XML export here..."
          className="w-full h-64 p-4 bg-surface-card border border-surface-border rounded-card text-sm font-mono text-text-primary placeholder-text-muted resize-y focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
        />
      </div>

      {/* Migrate Button */}
      <div className="flex justify-center mb-8">
        <Button
          variant="primary"
          size="lg"
          onClick={handleMigrate}
          disabled={loading || !xmlInput.trim()}
          className="px-12"
        >
          {loading ? 'Migrating...' : 'Migrate to GCP'}
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-card text-sm text-red-700 dark:text-red-400 mb-6">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center gap-3">
            <svg className="animate-spin h-8 w-8 text-brand-blue" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            <span className="text-sm text-text-secondary">Analyzing Informatica XML and generating GCP artifacts...</span>
          </div>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="space-y-6">
          {/* Summary Bar */}
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
            <div className={`p-4 border rounded-card text-center ${complexityColor(result.complexity)}`}>
              <div className="text-2xl font-bold uppercase">{result.complexity}</div>
              <div className="text-xs mt-1">Complexity</div>
            </div>
          </div>

          {/* Summary text */}
          <div className="p-4 bg-surface-card border border-surface-border rounded-card">
            <p className="text-sm text-text-primary">{result.summary}</p>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 border-b border-surface-border">
            {([
              { key: 'sql' as ActiveTab, label: 'BigQuery SQL' },
              { key: 'dag' as ActiveTab, label: 'Airflow DAG' },
              { key: 'map' as ActiveTab, label: 'Transformation Map' },
              ...(result.scd_merge ? [{ key: 'scd' as ActiveTab, label: 'SCD MERGE' }] : []),
            ]).map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.key
                    ? 'border-brand-blue text-brand-blue'
                    : 'border-transparent text-text-secondary hover:text-text-primary'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div className="bg-surface-card border border-surface-border rounded-card overflow-hidden">
            {activeTab === 'sql' && (
              <pre className="p-4 text-sm font-mono text-text-primary overflow-x-auto max-h-[500px] overflow-y-auto whitespace-pre">
                {result.bigquery_sql}
              </pre>
            )}
            {activeTab === 'dag' && (
              <pre className="p-4 text-sm font-mono text-text-primary overflow-x-auto max-h-[500px] overflow-y-auto whitespace-pre">
                {result.airflow_dag}
              </pre>
            )}
            {activeTab === 'scd' && result.scd_merge && (
              <pre className="p-4 text-sm font-mono text-text-primary overflow-x-auto max-h-[500px] overflow-y-auto whitespace-pre">
                {result.scd_merge}
              </pre>
            )}
            {activeTab === 'map' && (
              <div className="p-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-border">
                      <th className="text-left py-2 px-3 text-text-secondary font-medium">Informatica</th>
                      <th className="text-left py-2 px-3 text-text-secondary font-medium">GCP Equivalent</th>
                      <th className="text-left py-2 px-3 text-text-secondary font-medium">Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.transformation_map?.map((item, i) => (
                      <tr key={i} className="border-b border-surface-border/50 last:border-0">
                        <td className="py-2 px-3 font-mono text-text-primary">{item.informatica}</td>
                        <td className="py-2 px-3 text-text-primary">{item.gcp}</td>
                        <td className="py-2 px-3">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
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
            )}
          </div>

          {/* Unsupported Patterns */}
          {result.unsupported_patterns && result.unsupported_patterns.length > 0 && (
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

          {/* Recommendations */}
          {result.recommendations && result.recommendations.length > 0 && (
            <div className="p-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-card">
              <h3 className="text-sm font-bold text-blue-700 dark:text-blue-400 mb-3">Recommendations</h3>
              <ul className="space-y-1.5">
                {result.recommendations.map((rec, i) => (
                  <li key={i} className="text-sm text-blue-700 dark:text-blue-300 flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">&#8226;</span>
                    {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
