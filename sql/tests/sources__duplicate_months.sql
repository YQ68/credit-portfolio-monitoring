-- severity: warn
-- Nguồn có nhiều dòng cho cùng hợp đồng và tháng.
-- core.int_loan_month giữ dòng có DPD cao nhất (docs/data_notes.md, mục 10).
select 'pos_cash' as source, sk_id_prev, months_balance, count(*) as n_rows
from stg.pos_cash_balance
group by sk_id_prev, months_balance
having count(*) > 1

union all

select 'credit_card' as source, sk_id_prev, months_balance, count(*) as n_rows
from stg.credit_card_balance
group by sk_id_prev, months_balance
having count(*) > 1
