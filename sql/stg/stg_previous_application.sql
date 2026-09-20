-- Hồ sơ vay trước đây, gồm cả hồ sơ bị từ chối. Grain: 1 dòng / sk_id_prev.
-- 365243 trong cột DAYS_* và XNA, XAP được đổi thành NULL (docs/data_notes.md, mục 4).

create or replace table stg.previous_application as
select
    sk_id_prev,
    sk_id_curr,

    -- Sản phẩm, kênh, khách hàng
    nullif(name_contract_type, 'XNA')                    as contract_type,
    nullif(name_portfolio, 'XNA')                        as portfolio,
    nullif(name_product_type, 'XNA')                     as product_type,
    channel_type,
    nullif(name_client_type, 'XNA')                      as client_type,
    nullif(name_yield_group, 'XNA')                      as yield_group,
    product_combination,
    nullif(name_goods_category, 'XNA')                   as goods_category,
    nullif(name_seller_industry, 'XNA')                  as seller_industry,
    nullif(nullif(name_cash_loan_purpose, 'XAP'), 'XNA') as cash_loan_purpose,

    -- Quyết định
    name_contract_status                                 as application_status,  -- Approved, Refused, Canceled, Unused offer
    nullif(nullif(code_reject_reason, 'XAP'), 'XNA')     as reject_reason,
    days_decision,

    -- Số tiền và kỳ hạn
    amt_application                                      as application_amount,
    amt_credit                                           as credit_amount,
    amt_annuity                                          as annuity_amount,
    amt_down_payment                                     as down_payment_amount,
    amt_goods_price                                      as goods_price,
    cnt_payment                                          as tenor_months,

    -- Mốc thời gian của hợp đồng
    nullif(days_first_drawing, 365243)                   as days_first_drawing,
    nullif(days_first_due, 365243)                       as days_first_due,
    nullif(days_last_due_1st_version, 365243)            as days_last_due_1st_version,
    nullif(days_last_due, 365243)                        as days_last_due,
    nullif(days_termination, 365243)                     as days_termination,

    -- Cờ lọc hồ sơ trùng (docs/data_notes.md, mục 10)
    flag_last_appl_per_contract = 'Y'                    as is_last_appl_per_contract,
    nflag_last_appl_in_day = 1                           as is_last_appl_in_day,
    nflag_insured_on_approval = 1                        as is_insured
from raw.previous_application;
