from __future__ import annotations

import json
import logging
import re
from typing import Optional

from agents.base import BaseAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Real message code templates from production SQL files
# ---------------------------------------------------------------------------
_SQL_PRD_NO_CLOUD_NO_PPLAN_P = r"""-- =================================================================================================
-- Description:       Generates Message Codes by creating several temporary tables to segment
--                    customers and applying business rules before inserting the final codes
--                    into the message table.
--
-- Script Name:       PRD_NO_CLOUD_NO_PPLAN_P.sql
-- DAG Name:          dg_k45v_msgcdo_prd_no_cloud_no_pplan_p
-- Schedule:          0 6 * * *
--
-- Message Codes:     PRD_NO_CLOUD_NO_PPLAN_P
--
-- Tags:              lob:vcg, program:mrktg, sub_lob:marketing
--
-- Labels:            task_type: bq_to_bq_load
--                    car_team: home
--                    service: wireless-wireline
--                    type: product_enablement
--
-- Author:            chima7y (mark chiles)
-- Create Date:       2025-11-24
-- =================================================================================================
BEGIN
/*== INSERT RECORDS INTO VALIDATION TABLE ==*/
BEGIN
  INSERT INTO {{params.k45v_msgcdo}}.ntl_prd_qmtbls.prod_message_cd_validation
    (identity_col_index, loadstarttime, insert_dt, message_cd, mc_owner, mc_owner_email, loadflag, prodflag)
    SELECT NULL AS identity_col_index, CURRENT_DATETIME() AS loadstarttime, current_date(),
        message_xref.message_cd, message_xref.mc_owner, message_xref.mc_owner_email, 'N' AS loadflag, 'N' AS prodflag
      FROM {{params.k3av_scrbdo}}.k45v_msgcdo_0_msgcd_ref_tbls.message_xref
      WHERE message_xref.message_cd IN('PRD_NO_CLOUD_NO_PPLAN_P', 'PRD_CLOUD_600GB_MYPLAN_P', 'PRD_NO_CLOUD_SUB_MYPLAN_P');
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== CREATE MAIN TABLE OF DECISION-MAKERS ==*/
BEGIN
  CREATE TEMPORARY TABLE tmp1 AS
    SELECT a.cust_id, a.acct_num, a.cust_line_seq_id, a.mtn_role, a.primary_line_ind,
           'N' AS phog, 'N' AS myplan_cust, 'N' AS cloud_600gb,
           'N' AS cloud_sfo_supp, 'N' AS cloud_spo_supp, 'N' AS cloud_cust
      FROM {{params.gsyv_adcpdo}}.vzw_dmbm_vws.customer_profile_univ_cons_mini AS a
      INNER JOIN {{params.gk1v_do}}.ntl_prd_allvm.cust_acct_line_v AS e
        ON a.cust_id = e.cust_id AND a.acct_num = e.acct_num AND a.cust_line_seq_id = e.cust_line_seq_id
      WHERE upper(a.consumer_ind) = 'Y'
        AND upper(coalesce(e.prepaid_ind, 'N')) = 'N'
        AND upper(a.dont_mrkt_bb_ind) = 'N'
        AND upper(a.dnsst_ind) = 'N'
        AND a.mtn_status_ind IN('A', 'S')
        AND (upper(a.mtn_role) = 'AH' OR upper(a.primary_line_ind) = 'Y');
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== IDENTIFY CLOUD_SFO ==*/
BEGIN
  CREATE TEMPORARY TABLE tmp2 AS
    SELECT a.cust_id, a.acct_num, a.svc_id
      FROM {{params.gk1v_do}}.ntl_prd_allvm.dly_service_activity_v AS a
      WHERE a.svc_id IN('75527','75528','75529','75530','75531','75532','79814','85128','85548','85551','85553',
        '86210','86211','86212','86213','87260','87264','87481','88132','88133','88134','88158',
        '88920','88929','88930','88932','89090','89091','89573','89729','90081','90312','90317')
        AND a.svc_act_dt <= current_date()
        AND (a.svc_deact_dt >= current_date() OR a.svc_deact_dt IS NULL)
      QUALIFY row_number() OVER (PARTITION BY a.cust_id, a.acct_num ORDER BY a.svc_act_dt DESC) = 1;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== IDENTIFY CLOUD_SPO ==*/
BEGIN
  CREATE TEMPORARY TABLE tmp3 AS
    SELECT a.cust_id, a.acct_num, a.cust_line_seq_id, a.svc_prod_id
      FROM {{params.gk1v_do}}.ntl_prd_allvm.cust_acct_line_svc_prod_tran_v AS a
      WHERE a.svc_prod_id IN('1577','1657','2630','3198','3199','3316')
        AND a.svc_prod_eff_dt <= current_date()
        AND a.svc_prod_exp_dt > current_date()
        AND (a.svc_prod_deact_dt > current_date() OR a.svc_prod_deact_dt IS NULL)
      QUALIFY row_number() OVER (PARTITION BY a.cust_id, a.acct_num, a.svc_prod_id ORDER BY a.svc_prod_id DESC) = 1;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== IDENTIFY MYPLAN_CUST ==*/
BEGIN
  CREATE TEMPORARY TABLE tmp4 AS
    SELECT a.cust_id, a.acct_num, b.pplan_cd
      FROM {{params.gsyv_adcpdo}}.vzw_dmbm_vws_v.customer_profile_univ_cons_mini AS a
      LEFT JOIN {{params.gk1v_do}}.ntl_prd_allvm.cust_acct_line_pplan_v AS b ON a.cust_id = b.cust_id
      WHERE b.pplan_cd IN('63214','63215','63216','63217','69183','69185','32066')
      QUALIFY row_number() OVER (PARTITION BY a.cust_id, a.acct_num ORDER BY a.cust_id) = 1;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== FLAG CLOUD_SFO_SUPP IN MAIN TABLE ==*/
BEGIN
  UPDATE tmp1 AS a SET cloud_sfo_supp = 'Y' FROM (
    SELECT tmp2.cust_id, tmp2.acct_num FROM tmp2 GROUP BY 1, 2
  ) AS b WHERE a.cust_id = b.cust_id AND a.acct_num = b.acct_num;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== FLAG CLOUD_SPO_SUPP IN MAIN TABLE ==*/
BEGIN
  UPDATE tmp1 AS a SET cloud_spo_supp = 'Y' FROM (
    SELECT tmp3.cust_id, tmp3.acct_num FROM tmp3 GROUP BY 1, 2
  ) AS b WHERE a.cust_id = b.cust_id AND a.acct_num = b.acct_num;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== FLAG MYPLAN_CUST IN MAIN TABLE ==*/
BEGIN
  UPDATE tmp1 AS a SET myplan_cust = 'Y' FROM (
    SELECT tmp4.cust_id, tmp4.acct_num FROM tmp4 GROUP BY 1, 2
  ) AS b WHERE a.cust_id = b.cust_id AND a.acct_num = b.acct_num;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== FLAG CLOUD_600GB IN MAIN TABLE ==*/
BEGIN
  UPDATE tmp1 AS a SET cloud_600gb = 'Y' FROM (
    SELECT tmp2.cust_id, tmp2.acct_num FROM tmp2
      WHERE rtrim(tmp2.svc_id, ' ') IN('85548','85551','88158','87481','86211','699952','699953')
      GROUP BY 1, 2
  ) AS b WHERE a.cust_id = b.cust_id AND a.acct_num = b.acct_num;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== Identify PHOG Records ==*/
BEGIN
  UPDATE tmp1 AS a SET phog = 'Y'
    FROM {{params.gk1v_do}}.udm_prdusr_allvm.crm_cust_acct_phog_v AS b
    WHERE a.cust_id = b.cust_id AND a.acct_num = b.acct_num;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== Assign Message Code ==*/
BEGIN
  CREATE TEMPORARY TABLE tmp5 CLUSTER BY message_cd AS
    SELECT 'V' AS sor_id, tmp1.cust_id, tmp1.cust_line_seq_id,
           current_date() AS eff_dt, DATE '9999-12-31' AS exp_dt, 'C' AS curr_prev_ind,
           tmp1.acct_num,
           CAST(datetime(current_date(), time_trunc(current_time(), SECOND)) AS TIMESTAMP) AS insert_timestamp,
           CASE WHEN upper(tmp1.phog) = 'Y' THEN 'P' ELSE 'T' END AS trtmnt_ctrl_ind,
           message_cd AS message_cd, 'I' AS action_cd, 'U' AS src_load_id
      FROM tmp1
      CROSS JOIN UNNEST(ARRAY[
        CASE
          WHEN upper(rtrim(tmp1.cloud_spo_supp, ' ')) = 'N'
           AND upper(rtrim(tmp1.cloud_sfo_supp, ' ')) = 'N'
           AND upper(rtrim(tmp1.myplan_cust, ' ')) = 'N' THEN 'PRD_NO_CLOUD_NO_PPLAN_P'
          WHEN upper(rtrim(tmp1.cloud_600gb, ' ')) = 'Y'
           AND upper(rtrim(tmp1.myplan_cust, ' ')) = 'Y' THEN 'PRD_CLOUD_600GB_MYPLAN_P'
          WHEN upper(rtrim(tmp1.cloud_spo_supp, ' ')) = 'N'
           AND upper(rtrim(tmp1.cloud_sfo_supp, ' ')) = 'N'
           AND upper(rtrim(tmp1.myplan_cust, ' ')) = 'Y' THEN 'PRD_NO_CLOUD_SUB_MYPLAN_P'
          ELSE NULL
        END
      ]) AS message_cd
      WHERE message_cd IS NOT NULL
      QUALIFY row_number() OVER (PARTITION BY tmp1.cust_id, tmp1.acct_num ORDER BY tmp1.cust_id) = 1;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== Insert Records into staging table ==*/
BEGIN
  INSERT INTO {{params.k3av_scrbdo}}.k45v_msgcdo_0_msgcd_ref_tbls.cust_acct_line_message_manual
    (sor_id, cust_id, cust_line_seq_id, eff_dt, exp_dt, curr_prev_ind, acct_num, message_cd,
     insert_timestamp, trtmnt_ctrl_ind, action_cd, src_load_id)
    SELECT tmp5.sor_id, tmp5.cust_id, tmp5.cust_line_seq_id, tmp5.eff_dt, tmp5.exp_dt,
           tmp5.curr_prev_ind, tmp5.acct_num, tmp5.message_cd,
           CURRENT_DATETIME() AS insert_timestamp, tmp5.trtmnt_ctrl_ind, 'U' AS action_cd, tmp5.src_load_id
      FROM tmp5;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== Calc new counts for Validation table ==*/
BEGIN
  UPDATE {{params.k45v_msgcdo}}.ntl_prd_qmtbls.prod_message_cd_validation AS a
    SET loadflag = 'Y', loadendtime = current_datetime(), loadphog = b.loadphog, loadtreat = b.loadtreat
    FROM (
      SELECT xx.message_cd, sum(xx.lp) AS loadphog, sum(xx.ltr) AS loadtreat
        FROM (
          SELECT cust_acct_line_message_manual.message_cd,
            CASE WHEN upper(cust_acct_line_message_manual.trtmnt_ctrl_ind) = 'P' THEN 1 ELSE 0 END AS lp,
            CASE WHEN upper(cust_acct_line_message_manual.trtmnt_ctrl_ind) = 'T' THEN 1 ELSE 0 END AS ltr
            FROM {{params.k3av_scrbdo}}.k45v_msgcdo_0_msgcd_ref_tbls.cust_acct_line_message_manual
            WHERE cust_acct_line_message_manual.message_cd IN(
              'PRD_NO_CLOUD_NO_PPLAN_P', 'PRD_CLOUD_600GB_MYPLAN_P', 'PRD_NO_CLOUD_SUB_MYPLAN_P')
        ) AS xx GROUP BY 1
    ) AS b
    WHERE a.message_cd IN('PRD_NO_CLOUD_NO_PPLAN_P', 'PRD_CLOUD_600GB_MYPLAN_P', 'PRD_NO_CLOUD_SUB_MYPLAN_P')
      AND a.message_cd = b.message_cd AND insert_dt = current_date() AND upper(loadflag) = 'N';
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

RETURN;
END;
"""

_SQL_PRD_NO_CLOUD_NO_PPLAN_600GB_P = r"""-- =================================================================================================
-- Description:       Generates Message Codes by creating several temporary tables to segment
--                    customers and applying business rules before inserting the final codes
--                    into the message table.  (600GB variant)
--
-- Script Name:       PRD_NO_CLOUD_NO_PPLAN_600GB_P.sql
-- DAG Name:          dg_k45v_msgcdo_prd_no_cloud_no_pplan_p
-- Schedule:          0 6 * * *
--
-- Message Codes:     PRD_NO_CLOUD_NO_PPLAN_P (600GB variant)
--
-- Tags:              lob:vcg, program:mrktg, sub_lob:marketing
--
-- Labels:            task_type: bq_to_bq_load
--                    car_team: home
--                    service: wireless-wireline
--                    type: product_enablement
--
-- Author:            chima7y (mark chiles)
-- Create Date:       2025-11-24
-- =================================================================================================
BEGIN
/*== INSERT RECORDS INTO VALIDATION TABLE ==*/
BEGIN
  INSERT INTO {{params.k45v_msgcdo}}.ntl_prd_qmtbls.prod_message_cd_validation
    (identity_col_index, loadstarttime, insert_dt, message_cd, mc_owner, mc_owner_email, loadflag, prodflag)
    SELECT NULL AS identity_col_index, CURRENT_DATETIME() AS loadstarttime, current_date(),
        message_xref.message_cd, message_xref.mc_owner, message_xref.mc_owner_email, 'N' AS loadflag, 'N' AS prodflag
      FROM {{params.k3av_scrbdo}}.k45v_msgcdo_0_msgcd_ref_tbls.message_xref
      WHERE message_xref.message_cd IN('PRD_NO_CLOUD_NO_PPLAN_P', 'PRD_CLOUD_600GB_MYPLAN_P', 'PRD_NO_CLOUD_SUB_MYPLAN_P');
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== CREATE MAIN TABLE OF DECISION-MAKERS ==*/
BEGIN
  CREATE TEMPORARY TABLE tmp1 AS
    SELECT a.cust_id, a.acct_num, a.cust_line_seq_id, a.mtn_role, a.primary_line_ind,
           'N' AS phog, 'N' AS myplan_cust, 'N' AS cloud_600gb,
           'N' AS cloud_sfo_supp, 'N' AS cloud_spo_supp, 'N' AS cloud_cust
      FROM {{params.gsyv_adcpdo}}.vzw_dmbm_vws.customer_profile_univ_cons_mini AS a
      INNER JOIN {{params.gk1v_do}}.ntl_prd_allvm.cust_acct_line_v AS e
        ON a.cust_id = e.cust_id AND a.acct_num = e.acct_num AND a.cust_line_seq_id = e.cust_line_seq_id
      WHERE upper(a.consumer_ind) = 'Y'
        AND upper(coalesce(e.prepaid_ind, 'N')) = 'N'
        AND upper(a.dont_mrkt_bb_ind) = 'N'
        AND upper(a.dnsst_ind) = 'N'
        AND a.mtn_status_ind IN('A', 'S')
        AND (upper(a.mtn_role) = 'AH' OR upper(a.primary_line_ind) = 'Y');
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== IDENTIFY CLOUD_SFO ==*/
BEGIN
  CREATE TEMPORARY TABLE tmp2 AS
    SELECT a.cust_id, a.acct_num, a.svc_id
      FROM {{params.gk1v_do}}.ntl_prd_allvm.dly_service_activity_v AS a
      WHERE a.svc_id IN('75527','75528','75529','75530','75531','75532','79814','85128','85548','85551','85553',
        '86210','86211','86212','86213','87260','87264','87481','88132','88133','88134','88158',
        '88920','88929','88930','88932','89090','89091','89573','89729','90081','90312','90317')
        AND a.svc_act_dt <= current_date()
        AND (a.svc_deact_dt >= current_date() OR a.svc_deact_dt IS NULL)
      QUALIFY row_number() OVER (PARTITION BY a.cust_id, a.acct_num ORDER BY a.svc_act_dt DESC) = 1;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== IDENTIFY CLOUD_SPO ==*/
BEGIN
  CREATE TEMPORARY TABLE tmp3 AS
    SELECT a.cust_id, a.acct_num, a.cust_line_seq_id, a.svc_prod_id
      FROM {{params.gk1v_do}}.ntl_prd_allvm.cust_acct_line_svc_prod_tran_v AS a
      WHERE a.svc_prod_id IN('1577','1657','2630','3198','3199','3316')
        AND a.svc_prod_eff_dt <= current_date()
        AND a.svc_prod_exp_dt > current_date()
        AND (a.svc_prod_deact_dt > current_date() OR a.svc_prod_deact_dt IS NULL)
      QUALIFY row_number() OVER (PARTITION BY a.cust_id, a.acct_num, a.svc_prod_id ORDER BY a.svc_prod_id DESC) = 1;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== IDENTIFY MYPLAN_CUST ==*/
BEGIN
  CREATE TEMPORARY TABLE tmp4 AS
    SELECT a.cust_id, a.acct_num, b.pplan_cd
      FROM {{params.gsyv_adcpdo}}.vzw_dmbm_vws_v.customer_profile_univ_cons_mini AS a
      LEFT JOIN {{params.gk1v_do}}.ntl_prd_allvm.cust_acct_line_pplan_v AS b ON a.cust_id = b.cust_id
      WHERE b.pplan_cd IN('63214','63215','63216','63217','69183','69185','32066')
      QUALIFY row_number() OVER (PARTITION BY a.cust_id, a.acct_num ORDER BY a.cust_id) = 1;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== FLAG CLOUD_SFO_SUPP IN MAIN TABLE ==*/
BEGIN
  UPDATE tmp1 AS a SET cloud_sfo_supp = 'Y' FROM (
    SELECT tmp2.cust_id, tmp2.acct_num FROM tmp2 GROUP BY 1, 2
  ) AS b WHERE a.cust_id = b.cust_id AND a.acct_num = b.acct_num;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== FLAG CLOUD_SPO_SUPP IN MAIN TABLE ==*/
BEGIN
  UPDATE tmp1 AS a SET cloud_spo_supp = 'Y' FROM (
    SELECT tmp3.cust_id, tmp3.acct_num FROM tmp3 GROUP BY 1, 2
  ) AS b WHERE a.cust_id = b.cust_id AND a.acct_num = b.acct_num;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== FLAG MYPLAN_CUST IN MAIN TABLE ==*/
BEGIN
  UPDATE tmp1 AS a SET myplan_cust = 'Y' FROM (
    SELECT tmp4.cust_id, tmp4.acct_num FROM tmp4 GROUP BY 1, 2
  ) AS b WHERE a.cust_id = b.cust_id AND a.acct_num = b.acct_num;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== FLAG CLOUD_600GB IN MAIN TABLE ==*/
BEGIN
  UPDATE tmp1 AS a SET cloud_600gb = 'Y' FROM (
    SELECT tmp2.cust_id, tmp2.acct_num FROM tmp2
      WHERE rtrim(tmp2.svc_id, ' ') IN('85548','85551','88158','87481','86211','699952','699953')
      GROUP BY 1, 2
  ) AS b WHERE a.cust_id = b.cust_id AND a.acct_num = b.acct_num;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== Identify PHOG Records ==*/
BEGIN
  UPDATE tmp1 AS a SET phog = 'Y'
    FROM {{params.gk1v_do}}.udm_prdusr_allvm.crm_cust_acct_phog_v AS b
    WHERE a.cust_id = b.cust_id AND a.acct_num = b.acct_num;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== Assign Message Code ==*/
BEGIN
  CREATE TEMPORARY TABLE tmp5 CLUSTER BY message_cd AS
    SELECT 'V' AS sor_id, tmp1.cust_id, tmp1.cust_line_seq_id,
           current_date() AS eff_dt, DATE '9999-12-31' AS exp_dt, 'C' AS curr_prev_ind,
           tmp1.acct_num, CURRENT_DATETIME() AS insert_timestamp,
           CASE WHEN upper(tmp1.phog) = 'Y' THEN 'P' ELSE 'T' END AS trtmnt_ctrl_ind,
           message_cd AS message_cd, 'I' AS action_cd, 'U' AS src_load_id
      FROM tmp1
      CROSS JOIN UNNEST(ARRAY[
        CASE
          WHEN upper(rtrim(tmp1.cloud_spo_supp, ' ')) = 'N'
           AND upper(rtrim(tmp1.cloud_sfo_supp, ' ')) = 'N'
           AND upper(rtrim(tmp1.myplan_cust, ' ')) = 'N' THEN 'PRD_NO_CLOUD_NO_PPLAN_P'
          WHEN upper(rtrim(tmp1.cloud_600gb, ' ')) = 'Y'
           AND upper(rtrim(tmp1.myplan_cust, ' ')) = 'Y' THEN 'PRD_CLOUD_600GB_MYPLAN_P'
          WHEN upper(rtrim(tmp1.cloud_spo_supp, ' ')) = 'N'
           AND upper(rtrim(tmp1.cloud_sfo_supp, ' ')) = 'N'
           AND upper(rtrim(tmp1.myplan_cust, ' ')) = 'Y' THEN 'PRD_NO_CLOUD_SUB_MYPLAN_P'
          ELSE NULL
        END
      ]) AS message_cd
      WHERE message_cd IS NOT NULL
      QUALIFY row_number() OVER (PARTITION BY tmp1.cust_id, tmp1.acct_num ORDER BY tmp1.cust_id) = 1;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== Insert Records into staging table ==*/
BEGIN
  INSERT INTO {{params.k3av_scrbdo}}.k45v_msgcdo_0_msgcd_ref_tbls.cust_acct_line_message_manual
    (sor_id, cust_id, cust_line_seq_id, eff_dt, exp_dt, curr_prev_ind, acct_num, message_cd,
     insert_timestamp, trtmnt_ctrl_ind, action_cd, src_load_id)
    SELECT tmp5.sor_id, tmp5.cust_id, tmp5.cust_line_seq_id, tmp5.eff_dt, tmp5.exp_dt,
           tmp5.curr_prev_ind, tmp5.acct_num, tmp5.message_cd,
           CURRENT_DATETIME() AS insert_timestamp, tmp5.trtmnt_ctrl_ind, 'U' AS action_cd, tmp5.src_load_id
      FROM tmp5;
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

/*== Calc new counts for Validation table ==*/
BEGIN
  UPDATE {{params.k45v_msgcdo}}.ntl_prd_qmtbls.prod_message_cd_validation AS a
    SET loadflag = 'Y', loadendtime = current_datetime(), loadphog = b.loadphog, loadtreat = b.loadtreat
    FROM (
      SELECT xx.message_cd, sum(xx.lp) AS loadphog, sum(xx.ltr) AS loadtreat
        FROM (
          SELECT cust_acct_line_message_manual.message_cd,
            CASE WHEN upper(cust_acct_line_message_manual.trtmnt_ctrl_ind) = 'P' THEN 1 ELSE 0 END AS lp,
            CASE WHEN upper(cust_acct_line_message_manual.trtmnt_ctrl_ind) = 'T' THEN 1 ELSE 0 END AS ltr
            FROM {{params.k3av_scrbdo}}.k45v_msgcdo_0_msgcd_ref_tbls.cust_acct_line_message_manual
            WHERE cust_acct_line_message_manual.message_cd IN(
              'PRD_NO_CLOUD_NO_PPLAN_P', 'PRD_CLOUD_600GB_MYPLAN_P', 'PRD_NO_CLOUD_SUB_MYPLAN_P')
        ) AS xx GROUP BY 1
    ) AS b
    WHERE a.message_cd IN('PRD_NO_CLOUD_NO_PPLAN_P', 'PRD_CLOUD_600GB_MYPLAN_P', 'PRD_NO_CLOUD_SUB_MYPLAN_P')
      AND a.message_cd = b.message_cd AND insert_dt = current_date() AND upper(loadflag) = 'N';
EXCEPTION WHEN ERROR THEN RAISE USING MESSAGE = FORMAT('Query failed: %s | Statement: %s', @@error.message, @@error.statement_text);
END;

RETURN;
END;
"""


SAMPLE_TEMPLATES: list[dict] = [
    {
        "id": "prd_no_cloud_no_pplan_p",
        "name": "PRD No Cloud No PPlan (Proactive)",
        "category": "product_enablement",
        "channel": "proactive",
        "description": "Targets consumer customers who do not have cloud products and are not on a myPlan price plan. Assigns message codes for product enablement marketing.",
        "sql": _SQL_PRD_NO_CLOUD_NO_PPLAN_P,
        "tags": ["vcg", "marketing", "product_enablement", "wireless-wireline", "home", "no-cloud", "no-pplan", "proactive"],
        "logic_summary": (
            "1. Build base of consumer decision-makers (AH or primary line, active/suspended, non-prepaid, DNSST=N). "
            "2. Identify Cloud SFO subscribers via dly_service_activity_v service IDs. "
            "3. Identify Cloud SPO subscribers via cust_acct_line_svc_prod_tran_v product IDs. "
            "4. Identify myPlan customers via pplan_cd list. "
            "5. Flag cloud_sfo_supp, cloud_spo_supp, myplan_cust, cloud_600gb, and PHOG in main table. "
            "6. Assign message codes: PRD_NO_CLOUD_NO_PPLAN_P (no cloud, no pplan), "
            "PRD_CLOUD_600GB_MYPLAN_P (600gb cloud + myplan), "
            "PRD_NO_CLOUD_SUB_MYPLAN_P (no cloud + myplan). "
            "7. Insert into staging table with PHOG-based treatment control (P=holdout, T=treatment). "
            "8. Update validation table with load counts."
        ),
    },
    {
        "id": "prd_no_cloud_no_pplan_600gb_p",
        "name": "PRD No Cloud No PPlan 600GB (Proactive)",
        "category": "product_enablement",
        "channel": "proactive",
        "description": "600GB variant of the no-cloud no-pplan message code. Same logic with 600GB-specific cloud service identification. Used for targeted product enablement marketing.",
        "sql": _SQL_PRD_NO_CLOUD_NO_PPLAN_600GB_P,
        "tags": ["vcg", "marketing", "product_enablement", "wireless-wireline", "home", "no-cloud", "600gb", "proactive"],
        "logic_summary": (
            "Same as PRD_NO_CLOUD_NO_PPLAN_P but with 600GB-specific variant. "
            "1. Build consumer decision-maker base (AH/primary, active/suspended, non-prepaid, DNSST=N). "
            "2-4. Identify Cloud SFO, Cloud SPO, and myPlan subscribers. "
            "5. Flag all attributes including cloud_600gb via specific SVC_IDs (85548, 85551, etc.). "
            "6. Assign codes based on cloud/pplan status combinations. "
            "7. Insert into staging with PHOG treatment control. "
            "8. Update validation counts."
        ),
    },
]

# ---------------------------------------------------------------------------
# Demo data: pre-filled form values based on the sample SQL templates
# ---------------------------------------------------------------------------
DEMO_PRESETS: dict[str, dict] = {
    "prd_no_cloud_no_pplan_p": {
        "campaign_manager_name": "Mark Chiles",
        "message_code_type": "Message Code New",
        "message_positioning": "Proactive (Home/Mobile)",
        "refresh_frequency": "Daily",
        "message_codes": "PRD_NO_CLOUD_NO_PPLAN_P, PRD_CLOUD_600GB_MYPLAN_P, PRD_NO_CLOUD_SUB_MYPLAN_P",
        "campaign_name": "Product Enablement - No Cloud No PPlan",
        "date_of_request": "2025-11-24",
        "requested_due_date": "2025-12-01",
        "vz_service_type": "Wireless-Wireline",
        "product_family": "Cloud Storage / myPlan",
        "offer_level": "Account",
        "product_description": "Target consumers without cloud products or myPlan price plans for product enablement marketing. Segments customers by cloud SFO/SPO subscription status, myPlan enrollment, and 600GB cloud tier.",
        "product_owner": "Mark Chiles",
        "employees_included": "No",
        "dnsst_suppression": "YES",
        "suppress_maine": "No",
        "maine_flag": "",
        "feed_cards_live_tiles": "NO",
        "intended_purpose": "Revenue Generating",
        "expected_kpi": "Cloud product adoption rate, myPlan conversion rate, incremental ARPU from product enablement",
        "target_criteria": "Consumer decision-makers (AH or primary line), active/suspended MTN status, non-prepaid, DNSST=N, DONT_MRKT_BB=N. Excludes customers with existing cloud SFO or SPO subscriptions for no-cloud codes.",
        "suppressions": "Prepaid customers, DNSST flagged, Do Not Market BB flagged, non-consumer accounts",
        "additional_info": "Script uses parameterized project spaces (k45v_msgcdo, k3av_scrbdo, gsyv_adcpdo, gk1v_do). DAG: dg_k45v_msgcdo_prd_no_cloud_no_pplan_p. Runs daily at 6 AM UTC.",
        "holdout_group": "PHOG",
        "control_pct": "0",
        "legal_approver": "",
        "legally_approved": "Yes",
        "approval_date": "2025-11-20",
        "viva_data": "No",
        "cpni_data_used": "No",
        "cpni_usage_type": "Not Used",
        "ppi_data": "No",
        "model_criteria_used": "No",
        "mc_developer": "chima7y",
        "dev_start_date": "2025-11-24",
        "completion_date": "2025-12-17",
        "production_date": "2025-12-18",
        "log_check": "YES",
        "new_message_codes": "PRD_NO_CLOUD_NO_PPLAN_P, PRD_CLOUD_600GB_MYPLAN_P, PRD_NO_CLOUD_SUB_MYPLAN_P",
        "total_message_codes": "3",
        "scope": "3",
        "script_name": "PRD_NO_CLOUD_NO_PPLAN_P.sql",
        "automation_folder": "dg_k45v_msgcdo_prd_no_cloud_no_pplan_p",
        "development_scope": "Multiple channels with high effort selection criteria",
        "message_code": "PRD_NO_CLOUD_NO_PPLAN_P",
        "name": "Product Enablement - No Cloud No PPlan",
        "description": "Target consumers without cloud products or myPlan price plans for product enablement marketing.",
        "channel": "proactive",
        "category": "product_enablement",
        "owner": "chima7y (mark chiles)",
        "schedule": "0 6 * * *",
        "audience_rules": "Consumer decision-makers (AH or primary), active/suspended, non-prepaid, no DNSST, no Do-Not-Market-BB",
        "exclusion_rules": "Exclude prepaid, DNSST, Do-Not-Market-BB",
    },
    "prd_no_cloud_no_pplan_600gb_p": {
        "campaign_manager_name": "Mark Chiles",
        "message_code_type": "Message Code New",
        "message_positioning": "Proactive (Home/Mobile)",
        "refresh_frequency": "Daily",
        "message_codes": "PRD_NO_CLOUD_NO_PPLAN_P, PRD_CLOUD_600GB_MYPLAN_P, PRD_NO_CLOUD_SUB_MYPLAN_P",
        "campaign_name": "Product Enablement - No Cloud No PPlan 600GB",
        "date_of_request": "2025-11-24",
        "requested_due_date": "2025-12-01",
        "vz_service_type": "Wireless-Wireline",
        "product_family": "Cloud Storage 600GB / myPlan",
        "offer_level": "Account",
        "product_description": "600GB variant targeting consumers without cloud products. Identifies 600GB cloud tier via specific service IDs (85548, 85551, 88158, 87481, 86211) for myPlan cross-sell enablement.",
        "product_owner": "Mark Chiles",
        "employees_included": "No",
        "dnsst_suppression": "YES",
        "suppress_maine": "No",
        "maine_flag": "",
        "feed_cards_live_tiles": "NO",
        "intended_purpose": "Revenue Generating",
        "expected_kpi": "600GB cloud tier adoption, myPlan conversion from 600GB subscribers",
        "target_criteria": "Consumer decision-makers (AH or primary line), active/suspended, non-prepaid, DNSST=N. 600GB cloud identified via SVC_IDs: 85548, 85551, 88158, 87481, 86211, 699952, 699953.",
        "suppressions": "Prepaid customers, DNSST flagged, Do Not Market BB flagged",
        "additional_info": "Updated filename to PRD_NO_CLOUD_NO_PPLAN_600GB_P.sql to reflect 600GB message code changes. Same DAG as base variant.",
        "holdout_group": "PHOG",
        "control_pct": "0",
        "legal_approver": "",
        "legally_approved": "Yes",
        "approval_date": "2025-11-20",
        "viva_data": "No",
        "cpni_data_used": "No",
        "cpni_usage_type": "Not Used",
        "ppi_data": "No",
        "model_criteria_used": "No",
        "mc_developer": "chima7y",
        "dev_start_date": "2025-11-24",
        "completion_date": "2026-01-14",
        "production_date": "2026-01-16",
        "log_check": "YES",
        "new_message_codes": "PRD_NO_CLOUD_NO_PPLAN_P, PRD_CLOUD_600GB_MYPLAN_P, PRD_NO_CLOUD_SUB_MYPLAN_P",
        "total_message_codes": "3",
        "scope": "3",
        "script_name": "PRD_NO_CLOUD_NO_PPLAN_600GB_P.sql",
        "automation_folder": "dg_k45v_msgcdo_prd_no_cloud_no_pplan_p",
        "development_scope": "Multiple channels with high effort selection criteria",
        "message_code": "PRD_NO_CLOUD_NO_PPLAN_600GB_P",
        "name": "Product Enablement - No Cloud No PPlan 600GB",
        "description": "600GB variant targeting consumers without cloud products for product enablement.",
        "channel": "proactive",
        "category": "product_enablement",
        "owner": "chima7y (mark chiles)",
        "schedule": "0 6 * * *",
        "audience_rules": "Consumer decision-makers (AH or primary), active/suspended, non-prepaid, no DNSST, no Do-Not-Market-BB. 600GB cloud via specific SVC_IDs.",
        "exclusion_rules": "Exclude prepaid, DNSST, Do-Not-Market-BB",
    },
}

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
        description = (requirements.get("description") or requirements.get("product_description") or "").lower()
        positioning = (requirements.get("message_positioning") or "").lower()
        service_type = (requirements.get("vz_service_type") or "").lower()
        target_criteria = (requirements.get("target_criteria") or requirements.get("audience_rules") or "").lower()

        scored: list[tuple[int, dict]] = []
        for t in templates:
            score = 0
            t_channel = (t.get("channel") or "").lower()
            t_category = (t.get("category") or "").lower()
            t_tags = [tag.lower() for tag in (t.get("tags") or [])]
            t_desc = (t.get("description") or "").lower()

            # Channel / positioning match is most important
            if channel and channel == t_channel:
                score += 40
            if "proactive" in positioning and "proactive" in t_channel:
                score += 40

            # Category match
            if category and category == t_category:
                score += 30

            # Service type / tag overlap
            if service_type:
                svc_words = set(re.findall(r'\w+', service_type))
                svc_overlap = svc_words & set(t_tags)
                score += len(svc_overlap) * 15

            # Keyword overlap from description + target criteria
            all_text = f"{description} {target_criteria}"
            desc_words = set(re.findall(r'\w+', all_text))
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
        req_channel = (requirements.get("channel") or "").lower()
        tmpl_channel = (template.get("channel") or "").lower()
        if req_channel and req_channel == tmpl_channel:
            reasons.append(f"Same channel: {template.get('channel')}")
        positioning = (requirements.get("message_positioning") or "").lower()
        if "proactive" in positioning and "proactive" in tmpl_channel:
            reasons.append(f"Positioning match: proactive")
        if (requirements.get("category") or "").lower() == (template.get("category") or "").lower():
            reasons.append(f"Same category: {template.get('category')}")
        desc_text = (requirements.get("description") or requirements.get("product_description") or "").lower()
        desc_words = set(re.findall(r'\w+', desc_text))
        tag_overlap = desc_words & set(t.lower() for t in (template.get("tags") or []))
        if tag_overlap:
            reasons.append(f"Matching tags: {', '.join(sorted(tag_overlap))}")
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

        msg_code = requirements.get("message_code") or requirements.get("message_codes", "").split(",")[0].strip() or "MC_NEW_MESSAGE"
        msg_name = requirements.get("name") or requirements.get("campaign_name") or "New Message"
        owner = requirements.get("owner") or requirements.get("product_owner") or requirements.get("campaign_manager_name") or "team"
        schedule = requirements.get("schedule", "0 6 * * *")
        channel = requirements.get("channel") or requirements.get("message_positioning", "proactive").split("(")[0].strip().lower() or "email"
        description = requirements.get("description") or requirements.get("product_description") or ""
        audience_rules = requirements.get("audience_rules") or requirements.get("target_criteria") or ""
        exclusion_rules = requirements.get("exclusion_rules") or requirements.get("suppressions") or ""
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
        msg_code = requirements.get("message_code") or requirements.get("message_codes", "").split(",")[0].strip() or "MC_NEW_MESSAGE"
        dag_id = f"dg_k45v_msgcdo_{msg_code.lower()}"
        owner = requirements.get("owner") or requirements.get("product_owner") or requirements.get("campaign_manager_name") or "data-team"
        schedule = requirements.get("schedule", "0 6 * * *")
        description = requirements.get("description") or requirements.get("product_description") or ""

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

    def generate_erules(self, requirements: dict) -> dict:
        """Generate eRules output (General, Rule, CDP Select, eRule JSON) from requirements."""
        msg_code = (
            requirements.get("message_code")
            or requirements.get("message_codes", "").split(",")[0].strip()
            or "MC_NEW_MESSAGE"
        )
        campaign_name = requirements.get("campaign_name") or requirements.get("name") or msg_code
        description = requirements.get("description") or requirements.get("product_description") or ""
        target_id = f"TG_{abs(hash(msg_code)) % 10000}"
        base_universe = "Pricing Universe"
        holdout = requirements.get("holdout_group", "BOTH")
        dnsst = requirements.get("dnsst_suppression", "YES")
        offer_level = requirements.get("offer_level", "Account")

        # --- General tab ---
        general = {
            "name": msg_code,
            "enabled": True,
            "description": description or campaign_name,
            "base": base_universe,
            "target_id": target_id,
            "campaign": campaign_name,
            "pillars": ["Pricing", "Treatments", "Progi"],
            "status": "Pending Update",
            "audit_effective_date": "",
            "include_target_groups": [],
            "exclude_target_groups": [],
        }

        # --- Rule tab: build rules from the SQL template logic ---
        rules = []
        rule_idx = 1

        # Consumer indicator
        rules.append({
            "id": f"E{rule_idx}",
            "variable": "consumer_ind",
            "operator": "=",
            "value": "Y",
            "root_level": offer_level,
            "join": "AND",
        })
        rule_idx += 1

        # Prepaid exclusion
        rules.append({
            "id": f"E{rule_idx}",
            "variable": "prepaid_ind",
            "operator": "=",
            "value": "N",
            "root_level": offer_level,
            "join": "AND",
        })
        rule_idx += 1

        # DNSST suppression
        if dnsst == "YES":
            rules.append({
                "id": f"E{rule_idx}",
                "variable": "dnsst_ind",
                "operator": "=",
                "value": "N",
                "root_level": offer_level,
                "join": "AND",
            })
            rule_idx += 1

        # Do not market broadband
        rules.append({
            "id": f"E{rule_idx}",
            "variable": "dont_mrkt_bb_ind",
            "operator": "=",
            "value": "N",
            "root_level": offer_level,
            "join": "AND",
        })
        rule_idx += 1

        # MTN status
        rules.append({
            "id": f"E{rule_idx}",
            "variable": "mtn_status_ind",
            "operator": "in",
            "value": "A | S",
            "root_level": "Line",
            "join": "AND",
        })
        rule_idx += 1

        # MTN role / primary line
        rules.append({
            "id": f"E{rule_idx}",
            "variable": "mtn_role",
            "operator": "=",
            "value": "AH",
            "root_level": "Line",
            "join": "OR",
        })
        rule_idx += 1
        rules.append({
            "id": f"E{rule_idx}",
            "variable": "primary_line_ind",
            "operator": "=",
            "value": "Y",
            "root_level": "Line",
            "join": "AND",
        })
        rule_idx += 1

        # Cloud SFO suppression (service IDs)
        cloud_sfo_ids = (
            "75527 | 75528 | 75529 | 75530 | 75531 | 75532 | 79814 | 85128 | 85548 | 85551 | 85553 | "
            "86210 | 86211 | 86212 | 86213 | 87260 | 87264 | 87481 | 88132 | 88133 | 88134 | 88158 | "
            "88920 | 88929 | 88930 | 88932 | 89090 | 89091 | 89573 | 89729 | 90081 | 90312 | 90317"
        )
        rules.append({
            "id": f"E{rule_idx}",
            "variable": "svc_id (cloud_sfo)",
            "operator": "not in",
            "value": cloud_sfo_ids,
            "root_level": "Line",
            "join": "AND",
        })
        rule_idx += 1

        # Cloud SPO suppression (product IDs)
        rules.append({
            "id": f"E{rule_idx}",
            "variable": "svc_prod_id (cloud_spo)",
            "operator": "not in",
            "value": "1577 | 1657 | 2630 | 3198 | 3199 | 3316",
            "root_level": "Line",
            "join": "AND",
        })
        rule_idx += 1

        # myPlan suppression (pplan codes)
        rules.append({
            "id": f"E{rule_idx}",
            "variable": "pplan_cd (myplan)",
            "operator": "not in",
            "value": "63214 | 63215 | 63216 | 63217 | 69183 | 69185 | 32066",
            "root_level": "Line",
            "join": "AND",
        })
        rule_idx += 1

        # PHOG holdout
        if holdout in ("PHOG", "BOTH"):
            rules.append({
                "id": f"E{rule_idx}",
                "variable": "phog_flag",
                "operator": "exists in",
                "value": "crm_cust_acct_phog_v",
                "root_level": offer_level,
                "join": "AND",
            })
            rule_idx += 1

        # --- CDP Select statement ---
        cdp_select = (
            f"SELECT\n"
            f"  cust_id,\n"
            f"  cust_line_seq_id,\n"
            f"  acct_num,\n"
            f"  mtn_role,\n"
            f"  primary_line_ind\n"
            f"FROM\n"
            f"  customer_profile_univ_cons_mini\n"
            f"WHERE consumer_ind = 'Y'\n"
            f"  AND coalesce(prepaid_ind, 'N') = 'N'\n"
            f"  AND dont_mrkt_bb_ind = 'N'\n"
            f"  AND dnsst_ind = 'N'\n"
            f"  AND mtn_status_ind IN ('A', 'S')\n"
            f"  AND (mtn_role = 'AH' OR primary_line_ind = 'Y')\n"
            f"  AND cust_id NOT IN (\n"
            f"    SELECT cust_id FROM dly_service_activity_v WHERE svc_id IN (\n"
            f"      '75527','75528','75529','75530','75531','75532','79814','85128',\n"
            f"      '85548','85551','85553','86210','86211','86212','86213','87260',\n"
            f"      '87264','87481','88132','88133','88134','88158','88920','88929',\n"
            f"      '88930','88932','89090','89091','89573','89729','90081','90312','90317'\n"
            f"    ) AND svc_act_dt <= CURRENT_DATE\n"
            f"      AND (svc_deact_dt >= CURRENT_DATE OR svc_deact_dt IS NULL)\n"
            f"  )\n"
            f"  AND cust_id NOT IN (\n"
            f"    SELECT cust_id FROM cust_acct_line_svc_prod_tran_v WHERE svc_prod_id IN (\n"
            f"      '1577','1657','2630','3198','3199','3316'\n"
            f"    ) AND svc_prod_eff_dt <= CURRENT_DATE AND svc_prod_exp_dt > CURRENT_DATE\n"
            f"  )\n"
            f"  AND cust_id NOT IN (\n"
            f"    SELECT cust_id FROM cust_acct_line_pplan_v WHERE pplan_cd IN (\n"
            f"      '63214','63215','63216','63217','69183','69185','32066'\n"
            f"    )\n"
            f"  )"
        )

        # --- eRule JSON (Page-a-Rule format) ---
        sys_logic_parts = [f"TE1 AND ({' AND '.join(r['id'] for r in rules)})"]
        pts_conditions = []

        # Universe condition
        pts_conditions.append({
            "NBDSName": "NBR_TE_KAST",
            "TS_HashUniversalId": "",
            "TsyLabel": "0",
            "TsyValue": f"universe.{base_universe.upper().replace(' ', '_')}",
        })

        # Test universe
        pts_conditions.append({
            "NBDSName": "NBR_TE_KAST",
            "TS_HashUniversalId": "",
            "TsyLabel": "0",
            "TsyValue": f"universe.FTO2_TST_ACCTS_UNIVERSE_{target_id}",
        })

        # Rule conditions
        for rule in rules:
            op_map = {"=": "eq", "in": "in", "not in": "notIn", "exists in": "existsIn", "not exists in": "notExistsIn", "between": "between"}
            pts_conditions.append({
                "NBDSName": "NBR_TE_KXGF",
                "sysInfo": f"InternalCDPWithoutbasicDP",
                "TsyLabel": rule["id"],
                "TsyValue": f"{rule['variable']}|{op_map.get(rule['operator'], rule['operator'])}|{rule['value']}",
                "rootLevel": rule["root_level"],
            })

        erule_json = {
            "id": target_id,
            "sByRespStatusTxt": "Established",
            "sByMeta": "",
            "sysLogic": sys_logic_parts[0],
            "PtsCondition": pts_conditions,
        }

        return {
            "target_id": target_id,
            "general": general,
            "rules": rules,
            "cdp_select": cdp_select,
            "erule_json": erule_json,
        }

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
