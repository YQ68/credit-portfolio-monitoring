-- severity: error
-- Đối chiếu độc lập: mẫu số tại MOB 0 gom từ mart phải bằng số hợp đồng đủ điều kiện đếm
-- thẳng từ core.dim_loan (loại is_partial_history và end_state = 'never_open').
-- Mọi hợp đồng đủ điều kiện đều có max_mob >= 0 nên đều xuất hiện tại MOB 0.
with from_mart as (
    select sum(n_loans) as n from mart.vintage where mob = 0
),
from_core as (
    select count(*) as n
    from core.dim_loan
    where end_state <> 'never_open'
      and not is_partial_history
)
select from_mart.n as n_mart, from_core.n as n_core
from from_mart, from_core
where from_mart.n <> from_core.n
