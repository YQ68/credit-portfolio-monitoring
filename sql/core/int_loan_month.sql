-- Gộp lịch sử tháng của khoản trả góp (POS, tiền mặt) và thẻ tín dụng về một cấu trúc.
-- Grain: 1 dòng / sk_id_prev / months_balance.
--
-- Quy tắc 1: hợp đồng có trong credit_card_balance lấy dữ liệu thẻ, bỏ bản ghi POS của cùng hợp đồng.
-- Quy tắc 2: nếu một tháng có nhiều dòng, giữ dòng có DPD cao nhất (thận trọng về rủi ro).
--   DPD chính của project là dpd_def (SK_DPD_DEF, có ngưỡng trọng yếu), nên xếp theo dpd_def trước;
--   dpd_raw (SK_DPD, không áp ngưỡng) chỉ làm tiêu chí phụ khi hòa.
-- Trên dữ liệu thật, cả hai quy tắc quan sát được 0 trường hợp: không có hợp đồng nào ở cả hai bảng
-- (tests/sources__loan_in_both.sql) và không có cặp (hợp đồng, tháng) nào trùng
-- (tests/sources__duplicate_months.sql). Hai quy tắc là phòng vệ, chưa từng loại dòng nào và
-- không ảnh hưởng số liệu hiện tại.
-- Kiểm tra: tests/int_loan_month__reconciles_with_sources.sql

create or replace table core.int_loan_month as
with unioned as (
    select
        sk_id_prev,
        sk_id_curr,
        'credit_card'         as source,
        months_balance,
        contract_status,
        dpd_raw,
        dpd_def,
        null::double          as installments_total,
        null::double          as installments_remaining,
        balance_amount,
        credit_limit
    from stg.credit_card_balance

    union all

    select
        p.sk_id_prev,
        p.sk_id_curr,
        'pos_cash'            as source,
        p.months_balance,
        p.contract_status,
        p.dpd_raw,
        p.dpd_def,
        p.installments_total,
        p.installments_remaining,
        null::double          as balance_amount,
        null::double          as credit_limit
    from stg.pos_cash_balance p
    where not exists (
        select 1 from stg.credit_card_balance c where c.sk_id_prev = p.sk_id_prev
    )
)

select *
from unioned
qualify row_number() over (
    partition by sk_id_prev, months_balance
    order by dpd_def desc nulls last, dpd_raw desc nulls last
) = 1;
