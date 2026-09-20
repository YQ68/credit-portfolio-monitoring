-- Profile dữ liệu sau khi build. Mỗi query kiểm tra một giả định trong docs/data_notes.md.
-- Chạy: python scripts/query.py sql/explore/01_profile.sql
-- Ghi kết quả và quyết định vào docs/data_notes.md, mục 11.

-- 1. Phân phối trạng thái hợp đồng theo nguồn (data_notes mục 8)
select source, contract_status, count(*) as n_rows
from core.int_loan_month
group by source, contract_status
order by source, n_rows desc;

-- 2. So sánh SK_DPD và SK_DPD_DEF: chọn cột nào làm DPD chính (data_notes mục 7)
select
    source,
    count(*)                                              as n_rows,
    count(*) filter (where dpd_raw > 0)                   as n_dpd_raw_positive,
    count(*) filter (where dpd_def > 0)                   as n_dpd_def_positive,
    count(*) filter (where dpd_raw > 30)                  as n_dpd_raw_30_plus,
    count(*) filter (where dpd_def > 30)                  as n_dpd_def_30_plus,
    count(*) filter (where dpd_raw > 30 and dpd_def <= 30) as n_30_plus_only_in_raw
from core.int_loan_month
group by source;

-- 3. Phân phối bucket của các tháng đang mở
select
    source,
    dpd_bucket,
    count(*) as n_rows,
    round(100.0 * count(*) / sum(count(*)) over (partition by source), 2) as pct
from core.fct_loan_month
where is_open
group by source, dpd_bucket
order by source, dpd_bucket;

-- 4. Trạng thái kết thúc và độ dài lịch sử của hợp đồng (data_notes mục 6)
select
    source,
    end_state,
    count(*)                                    as n_loans,
    count(*) filter (where is_left_truncated)   as n_left_truncated,
    min(first_open_month)                       as min_first_open_month,
    median(max_mob)                             as median_max_mob
from core.dim_loan
group by source, end_state
order by source, end_state;

-- 5. Hợp đồng chưa Completed kết thúc ở tháng nào: có dồn về -1 không? (data_notes mục 6)
select last_observed_month, end_state, count(*) as n_loans
from core.dim_loan
where end_state in ('censored', 'unknown')
group by last_observed_month, end_state
order by last_observed_month desc
limit 15;

-- 6. Khoản trả góp ở MOB 0 đã chạy từ trước chưa? (data_notes mục 6)
select
    installments_total - installments_remaining as installments_paid_at_mob0,
    count(*)                                    as n_loans
from core.fct_loan_month
where source = 'pos_cash' and mob = 0
group by installments_paid_at_mob0
order by n_loans desc
limit 10;

-- 7. Kỳ bị bỏ lỡ được ghi thế nào trong installments_payments (metric M11)
select
    count(*)                                      as n_rows,
    count(*) filter (where days_paid is null)     as n_null_days_paid,
    count(*) filter (where payment_amount is null) as n_null_payment,
    count(*) filter (where payment_amount = 0)    as n_zero_payment,
    count(distinct installment_version)           as n_versions
from stg.installments_payments;
