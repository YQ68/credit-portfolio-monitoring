-- severity: warn
-- Hợp đồng bị thiếu tháng giữa hai tháng quan sát.
-- Ảnh hưởng roll rate: cặp tháng không liên tiếp không được coi là một lần chuyển bucket.
select
    sk_id_prev,
    prev_month,
    months_balance,
    months_balance - prev_month - 1 as missing_months
from (
    select
        sk_id_prev,
        months_balance,
        lag(months_balance) over (partition by sk_id_prev order by months_balance) as prev_month
    from core.fct_loan_month
)
where months_balance - prev_month > 1
