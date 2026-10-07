-- severity: error
-- Đối chiếu độc lập: tổng số hợp đồng, số hợp đồng 30+ (chính và độ nhạy) và số hợp đồng có
-- exposure trong mart phải bằng số đếm thẳng từ core.fct_loan_month (hợp đồng đang mở tại
-- months_balance = -1). Hai phép đếm chỉ lệch khi phép join với core.dim_loan làm rơi hoặc
-- nhân bản dòng. Tại thời điểm viết, tổng là 144.421.
with from_mart as (
    select sum(n_loans) as n_loans, sum(n_30_plus) as n_30_plus,
           sum(n_30_plus_no_threshold) as n_30_plus_nt, sum(n_loans_exposure_known) as n_exp
    from mart.portfolio_snapshot
),
from_core as (
    select count(*) as n_loans,
           count(*) filter (where is_30_plus) as n_30_plus,
           count(*) filter (where is_30_plus_no_threshold) as n_30_plus_nt,
           count(exposure_proxy) as n_exp
    from core.fct_loan_month
    where is_open
      and months_balance = -1
)
select
    from_mart.n_loans      as n_loans_mart,
    from_core.n_loans      as n_loans_core,
    from_mart.n_30_plus    as n_30_plus_mart,
    from_core.n_30_plus    as n_30_plus_core,
    from_mart.n_30_plus_nt as n_30_plus_nt_mart,
    from_core.n_30_plus_nt as n_30_plus_nt_core,
    from_mart.n_exp        as n_exp_mart,
    from_core.n_exp        as n_exp_core
from from_mart, from_core
where from_mart.n_loans <> from_core.n_loans
   or from_mart.n_30_plus <> from_core.n_30_plus
   or from_mart.n_30_plus_nt <> from_core.n_30_plus_nt
   or from_mart.n_exp <> from_core.n_exp
