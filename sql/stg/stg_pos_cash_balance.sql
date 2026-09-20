-- Lịch sử tháng của khoản vay trả góp (POS và tiền mặt).
-- Grain kỳ vọng: 1 dòng / sk_id_prev / months_balance (có thể trùng, xem test sources__duplicate_months).

create or replace table stg.pos_cash_balance as
select
    sk_id_prev,
    sk_id_curr,
    months_balance,                             -- tháng tương đối, -1 = tháng gần nhất
    cnt_instalment         as installments_total,
    cnt_instalment_future  as installments_remaining,
    name_contract_status   as contract_status,
    sk_dpd                 as dpd_raw,
    sk_dpd_def             as dpd_def           -- DPD có dung sai, bỏ qua khoản nợ nhỏ
from raw.pos_cash_balance;
