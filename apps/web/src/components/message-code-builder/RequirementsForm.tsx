'use client';
import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import type { MessageCodeRequirements } from '@/lib/types';

interface RequirementsFormProps {
  requirements: MessageCodeRequirements;
  onChange: (reqs: MessageCodeRequirements) => void;
  onSubmit: () => void;
  loading: boolean;
  demoPresets: Record<string, Partial<MessageCodeRequirements>> | null;
  onLoadDemo: (presetId: string) => void;
  demoMode: boolean;
  onToggleDemo: (on: boolean) => void;
}

// --- Option lists matching the MC FORM docx ---
const CODE_TYPES = ['Message Code New', 'Message Code Existing', 'Dynamic Audience Code (DAC)'];
const POSITIONINGS = ['Proactive (Home/Mobile)', 'Reactive (Mobile)', 'Dynamic Audience Code (DAC)', 'CMID/SED (Mobile)'];
const FREQUENCIES = ['Adhoc', 'Daily', 'Monthly', 'Weekly', 'Dynamic Audience Code'];
const OFFER_LEVELS = ['Account', 'Line'];
const YES_NO = ['Yes', 'No'];
const HOLDOUT_GROUPS = ['CARHOG ( aka OHOG )', 'PHOG', 'BOTH', 'CS_PHOG + PRS FIOS PHOG as OHOG', 'None'];
const FEED_CARD_OPTIONS = [
  'Yes- AAL_P (Mobile)',
  'Yes- LOYALTY_PROMO_P (Mobile)',
  'Yes- PROMO_PRICING_P (Mobile)',
  'Yes- REV GEN_P (Mobile)',
  'Yes- RIGHT_PRICING_P (Mobile)',
  'Yes- UPGRADE_P (Mobile)',
  'Home Mixed (Joint Customer MC No/ fios Only Customer MC Yes)',
  'Yes- PROD_P (FIOS / WIRELINE)',
  'NO',
];
const INTENDED_PURPOSES = ['Engagement', 'Revenue Generating', 'Stem Churn'];
const LEGAL_STATUSES = ['Yes', 'No', 'Pending'];
const VIVA_STATUSES = ['Yes', 'No', 'Pending', 'NA'];
const CPNI_TYPES = ['Not Used', 'Home Voice', 'Mobile'];
const SCOPES = ['1', '2', '3', '4', '5'];
const DEV_SCOPES = [
  'Single channel low effort selection criteria (Dynamic Audience Code Only)',
  'Real time/near real time campaign targeting (Dynamic Audience Code Only)',
  'Multiple channels with low effort selection (Vehicle Dependent)',
  'Single use campaign, data outside of Adobe ACE',
  'Multiple channels (all channels cannot target) with low effort selection',
  'Single channel with high effort selection criteria',
  'Multiple channels with high effort selection criteria',
  'Specific campaigns designed to automate delivery',
  'Message Code Request changed to DAC by DBM',
];
const MAINE_FLAGS = [
  'Flag 1 BB Broadband Only Mobile Customer',
  'Flag 2 MB All Maine Mobile Customer',
  'Used in Customer Facing Channel',
];

function FormField({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-text-primary mb-1.5">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  );
}

function SectionHeader({
  title,
  icon,
  expanded,
  onToggle,
}: {
  title: string;
  icon: React.ReactNode;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      className="w-full flex items-center gap-3 py-3 border-b border-surface-border mb-4 hover:opacity-80 transition-opacity"
    >
      <div className="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-950 flex items-center justify-center flex-shrink-0">
        {icon}
      </div>
      <span className="text-sm font-bold text-text-primary flex-1 text-left">{title}</span>
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        className={`text-text-muted transition-transform ${expanded ? 'rotate-180' : ''}`}
      >
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </button>
  );
}

const inputClass =
  'w-full px-3 py-2 text-sm bg-surface-card border border-surface-border rounded-lg focus:ring-2 focus:ring-brand-blue focus:border-brand-blue outline-none text-text-primary placeholder:text-text-muted transition-colors';
const selectClass =
  'w-full px-3 py-2 text-sm bg-surface-card border border-surface-border rounded-lg focus:ring-2 focus:ring-brand-blue focus:border-brand-blue outline-none text-text-primary transition-colors';

const iconSvg = (d: string, color = '#2563EB') => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

export function RequirementsForm({
  requirements,
  onChange,
  onSubmit,
  loading,
  demoPresets,
  onLoadDemo,
  demoMode,
  onToggleDemo,
}: RequirementsFormProps) {
  const [sections, setSections] = useState<Record<string, boolean>>({
    basic: true,
    product: true,
    business: false,
    holdout: false,
    compliance: false,
    cdae: false,
  });

  const toggle = (key: string) => setSections((s) => ({ ...s, [key]: !s[key] }));
  const update = (field: keyof MessageCodeRequirements, value: string) => {
    onChange({ ...requirements, [field]: value });
  };

  const presetKeys = demoPresets ? Object.keys(demoPresets) : [];

  return (
    <Card>
      {/* Header + Demo Toggle */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-50 dark:bg-blue-950 flex items-center justify-center">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
            </svg>
          </div>
          <div>
            <h2 className="text-base font-bold text-text-primary">CDAE Message Code Request</h2>
            <p className="text-xs text-text-muted">Define your new message code requirements</p>
          </div>
        </div>

        {/* Demo Mode Toggle */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-text-muted">Demo Mode</span>
            <button
              onClick={() => onToggleDemo(!demoMode)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                demoMode ? 'bg-brand-blue' : 'bg-gray-300 dark:bg-gray-600'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
                  demoMode ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
          {demoMode && presetKeys.length > 0 && (
            <select
              className="px-2 py-1 text-xs bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-lg text-amber-800 dark:text-amber-200 font-medium"
              onChange={(e) => { if (e.target.value) onLoadDemo(e.target.value); }}
              defaultValue=""
            >
              <option value="">Load demo data...</option>
              {presetKeys.map((k) => (
                <option key={k} value={k}>
                  {k.replace(/_/g, ' ').toUpperCase()}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {demoMode && (
        <div className="mb-4 p-3 rounded-lg bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800">
          <p className="text-xs text-amber-800 dark:text-amber-200">
            Demo mode is active. Select a preset above to auto-fill the form with sample data from production SQL scripts.
          </p>
        </div>
      )}

      {/* === SECTION 1: Basic Info === */}
      <SectionHeader
        title="Basic Information"
        icon={iconSvg('M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z')}
        expanded={sections.basic}
        onToggle={() => toggle('basic')}
      />
      {sections.basic && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <FormField label="Campaign Manager Name" required>
            <input className={inputClass} value={requirements.campaign_manager_name} onChange={(e) => update('campaign_manager_name', e.target.value)} placeholder="First Last" />
          </FormField>
          <FormField label="Message/Audience Code Type" required>
            <select className={selectClass} value={requirements.message_code_type} onChange={(e) => update('message_code_type', e.target.value)}>
              {CODE_TYPES.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FormField>
          <FormField label="Message Positioning" required>
            <select className={selectClass} value={requirements.message_positioning} onChange={(e) => update('message_positioning', e.target.value)}>
              {POSITIONINGS.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FormField>
          <FormField label="Message Code Refresh Frequency" required>
            <select className={selectClass} value={requirements.refresh_frequency} onChange={(e) => update('refresh_frequency', e.target.value)}>
              {FREQUENCIES.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FormField>
          <FormField label="Message Code(s)" required>
            <input className={inputClass} value={requirements.message_codes} onChange={(e) => update('message_codes', e.target.value.toUpperCase())} placeholder="PRD_NEW_CODE_P (comma-separated if multiple)" />
          </FormField>
          <FormField label="Campaign Name" required>
            <input className={inputClass} value={requirements.campaign_name} onChange={(e) => update('campaign_name', e.target.value)} placeholder="Campaign name" />
          </FormField>
          <FormField label="Date of Request" required>
            <input type="date" className={inputClass} value={requirements.date_of_request} onChange={(e) => update('date_of_request', e.target.value)} />
          </FormField>
          <FormField label="Requested Due Date" required>
            <input type="date" className={inputClass} value={requirements.requested_due_date} onChange={(e) => update('requested_due_date', e.target.value)} />
          </FormField>
        </div>
      )}

      {/* === SECTION 2: Product Info === */}
      <SectionHeader
        title="Product Information"
        icon={iconSvg('M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4')}
        expanded={sections.product}
        onToggle={() => toggle('product')}
      />
      {sections.product && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <FormField label="Vz Service Type" required>
            <input className={inputClass} value={requirements.vz_service_type} onChange={(e) => update('vz_service_type', e.target.value)} placeholder="e.g., Wireless-Wireline" />
          </FormField>
          <FormField label="Product Family" required>
            <input className={inputClass} value={requirements.product_family} onChange={(e) => update('product_family', e.target.value)} placeholder="e.g., Cloud Storage / myPlan" />
          </FormField>
          <FormField label="Offer Level (Always Account for Home)" required>
            <select className={selectClass} value={requirements.offer_level} onChange={(e) => update('offer_level', e.target.value)}>
              {OFFER_LEVELS.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FormField>
          <FormField label="Product Owner (First & Last Name)" required>
            <input className={inputClass} value={requirements.product_owner} onChange={(e) => update('product_owner', e.target.value)} placeholder="First Last" />
          </FormField>
          <div className="md:col-span-2">
            <FormField label="Product Description" required>
              <textarea className={`${inputClass} min-h-[72px] resize-y`} value={requirements.product_description} onChange={(e) => update('product_description', e.target.value)} placeholder="Describe the product and targeting criteria" rows={3} />
            </FormField>
          </div>
        </div>
      )}

      {/* === SECTION 3: Business Rules === */}
      <SectionHeader
        title="Business Rules & Targeting"
        icon={iconSvg('M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2')}
        expanded={sections.business}
        onToggle={() => toggle('business')}
      />
      {sections.business && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <FormField label="Employees Included" required>
            <select className={selectClass} value={requirements.employees_included} onChange={(e) => update('employees_included', e.target.value)}>
              {YES_NO.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FormField>
          <FormField label="DNSST Suppression Required" required>
            <select className={selectClass} value={requirements.dnsst_suppression} onChange={(e) => update('dnsst_suppression', e.target.value)}>
              <option value="YES">YES</option>
              <option value="No">No</option>
            </select>
          </FormField>
          <FormField label="Suppress Maine" required>
            <select className={selectClass} value={requirements.suppress_maine} onChange={(e) => update('suppress_maine', e.target.value)}>
              {YES_NO.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FormField>
          {requirements.suppress_maine === 'Yes' && (
            <FormField label="Maine Flag">
              <select className={selectClass} value={requirements.maine_flag} onChange={(e) => update('maine_flag', e.target.value)}>
                <option value="">Select flag...</option>
                {MAINE_FLAGS.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </FormField>
          )}
          <FormField label="Using in Feed Cards and/or Live Tiles?" required>
            <select className={selectClass} value={requirements.feed_cards_live_tiles} onChange={(e) => update('feed_cards_live_tiles', e.target.value)}>
              {FEED_CARD_OPTIONS.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FormField>
          <FormField label="Intended Purpose" required>
            <select className={selectClass} value={requirements.intended_purpose} onChange={(e) => update('intended_purpose', e.target.value)}>
              <option value="">Select purpose...</option>
              {INTENDED_PURPOSES.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FormField>
          <div className="md:col-span-2">
            <FormField label="Expected KPI (How is success being measured?)" required>
              <textarea className={`${inputClass} min-h-[56px] resize-y`} value={requirements.expected_kpi} onChange={(e) => update('expected_kpi', e.target.value)} placeholder="Be specific about measurable outcomes" rows={2} />
            </FormField>
          </div>
          <div className="md:col-span-2">
            <FormField label="Target Criteria" required>
              <textarea className={`${inputClass} min-h-[56px] resize-y`} value={requirements.target_criteria} onChange={(e) => update('target_criteria', e.target.value)} placeholder="Who should be included in the audience?" rows={2} />
            </FormField>
          </div>
          <div className="md:col-span-2">
            <FormField label="Suppressions" required>
              <textarea className={`${inputClass} min-h-[56px] resize-y`} value={requirements.suppressions} onChange={(e) => update('suppressions', e.target.value)} placeholder="Who should be excluded?" rows={2} />
            </FormField>
          </div>
          <div className="md:col-span-2">
            <FormField label="Additional Information">
              <textarea className={`${inputClass} min-h-[56px] resize-y`} value={requirements.additional_info} onChange={(e) => update('additional_info', e.target.value)} placeholder="Any extra context or notes" rows={2} />
            </FormField>
          </div>
        </div>
      )}

      {/* === SECTION 4: Holdout & Control === */}
      <SectionHeader
        title="Holdout & Control Group"
        icon={iconSvg('M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M17 11l2 2 4-4M12.5 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0z')}
        expanded={sections.holdout}
        onToggle={() => toggle('holdout')}
      />
      {sections.holdout && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <FormField label="Holdout Group" required>
            <select className={selectClass} value={requirements.holdout_group} onChange={(e) => update('holdout_group', e.target.value)}>
              {HOLDOUT_GROUPS.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FormField>
          <FormField label="Message Code Control % (enter 0 if not used)" required>
            <input className={inputClass} type="number" min="0" max="100" value={requirements.control_pct} onChange={(e) => update('control_pct', e.target.value)} placeholder="0" />
          </FormField>
        </div>
      )}

      {/* === SECTION 5: Compliance === */}
      <SectionHeader
        title="Legal & Compliance"
        icon={iconSvg('M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0 1 12 2.944a11.955 11.955 0 0 1-8.618 3.04A12.02 12.02 0 0 0 3 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z', '#16a34a')}
        expanded={sections.compliance}
        onToggle={() => toggle('compliance')}
      />
      {sections.compliance && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <FormField label="Legal Approver" required>
            <input className={inputClass} value={requirements.legal_approver} onChange={(e) => update('legal_approver', e.target.value)} placeholder="Approver name" />
          </FormField>
          <FormField label="Legally Approved" required>
            <select className={selectClass} value={requirements.legally_approved} onChange={(e) => update('legally_approved', e.target.value)}>
              {LEGAL_STATUSES.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FormField>
          {requirements.legally_approved === 'Yes' && (
            <FormField label="Approval Date">
              <input type="date" className={inputClass} value={requirements.approval_date} onChange={(e) => update('approval_date', e.target.value)} />
            </FormField>
          )}

          {/* VIVA Data */}
          <FormField label="VIVA Data (FIOS Video Usage)" required>
            <select className={selectClass} value={requirements.viva_data} onChange={(e) => update('viva_data', e.target.value)}>
              {YES_NO.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FormField>
          {requirements.viva_data === 'Yes' && (
            <>
              <FormField label="VIVA Jira Request Number">
                <input className={inputClass} value={requirements.viva_jira_number} onChange={(e) => update('viva_jira_number', e.target.value)} placeholder="VIVA-1234" />
              </FormField>
              <FormField label="VIVA Privacy and Legal Approved">
                <select className={selectClass} value={requirements.viva_privacy_legal_approved} onChange={(e) => update('viva_privacy_legal_approved', e.target.value)}>
                  {VIVA_STATUSES.map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </FormField>
            </>
          )}

          {/* CPNI */}
          <FormField label="CPNI Data Used" required>
            <select className={selectClass} value={requirements.cpni_data_used} onChange={(e) => update('cpni_data_used', e.target.value)}>
              {YES_NO.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FormField>
          {requirements.cpni_data_used === 'Yes' && (
            <FormField label="CPNI Usage Type">
              <select className={selectClass} value={requirements.cpni_usage_type} onChange={(e) => update('cpni_usage_type', e.target.value)}>
                {CPNI_TYPES.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </FormField>
          )}

          {/* PPI */}
          <FormField label="PPI Data" required>
            <select className={selectClass} value={requirements.ppi_data} onChange={(e) => update('ppi_data', e.target.value)}>
              {YES_NO.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FormField>
          {requirements.ppi_data === 'Yes' && (
            <FormField label="PPI Usage Type">
              <input className={inputClass} value={requirements.ppi_usage_type} onChange={(e) => update('ppi_usage_type', e.target.value)} placeholder="Describe PPI usage" />
            </FormField>
          )}

          {/* Model Criteria */}
          <FormField label="Model Criteria Used" required>
            <select className={selectClass} value={requirements.model_criteria_used} onChange={(e) => update('model_criteria_used', e.target.value)}>
              <option value="Yes">Yes</option>
              <option value="No">No</option>
              <option value="NA">NA</option>
            </select>
          </FormField>
        </div>
      )}

      {/* === SECTION 6: CDAE Internal === */}
      <SectionHeader
        title="CDAE Internal (DBM Use Only)"
        icon={iconSvg('M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 0 0 2.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 0 0 1.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 0 0-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 0 0-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 0 0-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 0 0-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 0 0 1.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.573-1.066z', '#9333ea')}
        expanded={sections.cdae}
        onToggle={() => toggle('cdae')}
      />
      {sections.cdae && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <FormField label="Message Code Developer">
            <input className={inputClass} value={requirements.mc_developer} onChange={(e) => update('mc_developer', e.target.value)} placeholder="Developer ID" />
          </FormField>
          <FormField label="DBM Script Name">
            <input className={inputClass} value={requirements.script_name} onChange={(e) => update('script_name', e.target.value)} placeholder="SCRIPT_NAME.sql" />
          </FormField>
          <FormField label="Development Start Date">
            <input type="date" className={inputClass} value={requirements.dev_start_date} onChange={(e) => update('dev_start_date', e.target.value)} />
          </FormField>
          <FormField label="Completion Date">
            <input type="date" className={inputClass} value={requirements.completion_date} onChange={(e) => update('completion_date', e.target.value)} />
          </FormField>
          <FormField label="Data Validation Send Date">
            <input type="date" className={inputClass} value={requirements.validation_send_date} onChange={(e) => update('validation_send_date', e.target.value)} />
          </FormField>
          <FormField label="Data Validation Due Date">
            <input type="date" className={inputClass} value={requirements.validation_due_date} onChange={(e) => update('validation_due_date', e.target.value)} />
          </FormField>
          <FormField label="Production Date">
            <input type="date" className={inputClass} value={requirements.production_date} onChange={(e) => update('production_date', e.target.value)} />
          </FormField>
          <FormField label="Log Check (without errors)">
            <select className={selectClass} value={requirements.log_check} onChange={(e) => update('log_check', e.target.value)}>
              <option value="YES">YES</option>
              <option value="No">No</option>
            </select>
          </FormField>
          <FormField label="New Message Codes">
            <input className={inputClass} value={requirements.new_message_codes} onChange={(e) => update('new_message_codes', e.target.value)} placeholder="Comma-separated codes" />
          </FormField>
          <FormField label="Total Number of Message Codes">
            <input className={inputClass} type="number" min="0" value={requirements.total_message_codes} onChange={(e) => update('total_message_codes', e.target.value)} placeholder="0" />
          </FormField>
          <FormField label="SCOPE (1-5)">
            <select className={selectClass} value={requirements.scope} onChange={(e) => update('scope', e.target.value)}>
              <option value="">Select scope...</option>
              {SCOPES.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FormField>
          <FormField label="Automation Folder">
            <input className={inputClass} value={requirements.automation_folder} onChange={(e) => update('automation_folder', e.target.value)} placeholder="DAG folder name" />
          </FormField>
          <div className="md:col-span-2">
            <FormField label="Development Scope">
              <select className={selectClass} value={requirements.development_scope} onChange={(e) => update('development_scope', e.target.value)}>
                <option value="">Select development scope...</option>
                {DEV_SCOPES.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </FormField>
          </div>
          <div className="md:col-span-2">
            <FormField label="DBM Comments">
              <textarea className={`${inputClass} min-h-[56px] resize-y`} value={requirements.dbm_comments} onChange={(e) => update('dbm_comments', e.target.value)} placeholder="Internal notes" rows={2} />
            </FormField>
          </div>
          <FormField label="MVP Prioritization">
            <input className={inputClass} value={requirements.mvp_prioritization} onChange={(e) => update('mvp_prioritization', e.target.value)} placeholder="Priority info" />
          </FormField>
          <FormField label="Preliminary Message Code Counts">
            <input className={inputClass} value={requirements.preliminary_counts} onChange={(e) => update('preliminary_counts', e.target.value)} placeholder="Estimated counts" />
          </FormField>
        </div>
      )}

      {/* Submit */}
      <div className="mt-6 flex justify-end">
        <Button
          variant="primary"
          size="lg"
          onClick={onSubmit}
          disabled={
            loading ||
            !requirements.campaign_manager_name ||
            !requirements.message_codes ||
            !requirements.campaign_name
          }
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Analyzing...
            </span>
          ) : (
            'Find Best Template'
          )}
        </Button>
      </div>
    </Card>
  );
}
