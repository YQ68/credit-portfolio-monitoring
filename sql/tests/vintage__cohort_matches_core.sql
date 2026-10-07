-- severity: error
-- Đối chiếu độc lập theo đợt mở hợp đồng: tại MOB 0, mẫu số của từng origination_cohort gom từ mart
-- phải bằng số hợp đồng đủ điều kiện đếm thẳng từ core.dim_loan, với đợt tính lại từ
-- first_open_month bằng phép chia khác (floor thay vì chia nguyên). Kiểm luôn nhãn đợt khớp
-- origination_cohort_start và đợt nằm trong khoảng -96 đến -1, bước 12 tháng.
with from_mart as (
    select origination_cohort, origination_cohort_start, sum(n_loans) as n
    from mart.vintage where mob = 0
    group by 1, 2
),
from_core as (
    select cast(-96 + 12 * floor((first_open_month + 96) / 12.0) as integer) as cohort_start, count(*) as n
    from core.dim_loan
    where end_state <> 'never_open'
      and not is_partial_history
    group by 1
)
select coalesce(m.origination_cohort_start, c.cohort_start) as cohort_start, m.origination_cohort, m.n as n_mart, c.n as n_core
from from_mart m
full outer join from_core c on c.cohort_start = m.origination_cohort_start
where m.n is distinct from c.n
   or m.origination_cohort is distinct from (c.cohort_start::varchar || ' đến ' || (c.cohort_start + 11)::varchar)
   or c.cohort_start not in (-96, -84, -72, -60, -48, -36, -24, -12)
