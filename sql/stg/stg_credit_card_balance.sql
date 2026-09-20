-- Lịch sử tháng của thẻ tín dụng.
-- Grain kỳ vọng: 1 dòng / sk_id_prev / months_balance.

create or replace table stg.credit_card_balance as
select
    sk_id_prev,
    sk_id_curr,
    months_balance,
    amt_balance                as balance_amount,
    amt_credit_limit_actual    as credit_limit,
    amt_total_receivable       as total_receivable,
    amt_inst_min_regularity    as min_installment_amount,
    amt_payment_total_current  as payment_amount,
    amt_drawings_current       as drawings_amount,
    cnt_drawings_current       as drawings_count,
    cnt_instalment_mature_cum  as installments_matured_cum,
    name_contract_status       as contract_status,
    sk_dpd                     as dpd_raw,
    sk_dpd_def                 as dpd_def
from raw.credit_card_balance;
