-- severity: warn
-- Hợp đồng xuất hiện ở cả POS_CASH_balance và credit_card_balance.
-- core.int_loan_month lấy dữ liệu thẻ (docs/data_notes.md, mục 10).
select distinct p.sk_id_prev
from stg.pos_cash_balance p
join stg.credit_card_balance c on c.sk_id_prev = p.sk_id_prev
