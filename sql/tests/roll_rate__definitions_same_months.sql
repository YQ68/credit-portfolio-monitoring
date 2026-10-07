-- severity: error
-- Bảng chính và bảng độ nhạy đếm CÙNG một tập tháng xuất phát, chỉ khác cách xếp bucket. Vì vậy
-- trong mỗi phân khúc: tổng số lượt, tổng số lượt đi tới Closed, Other, Missing phải bằng nhau.
-- Lệch nghĩa là hai bảng đã tách logic.
with a as (
    select source, contract_type, channel_type,
           sum(n_loans) as n_all,
           sum(n_loans) filter (where to_state in ('Closed', 'Other', 'Missing')) as n_exit
    from mart.roll_rate group by 1, 2, 3
),
b as (
    select source, contract_type, channel_type,
           sum(n_loans) as n_all,
           sum(n_loans) filter (where to_state in ('Closed', 'Other', 'Missing')) as n_exit
    from mart.roll_rate_no_threshold group by 1, 2, 3
)
select coalesce(a.source, b.source) as source,
       coalesce(a.contract_type, b.contract_type) as contract_type,
       coalesce(a.channel_type, b.channel_type) as channel_type,
       a.n_all as n_all_primary, b.n_all as n_all_no_threshold,
       a.n_exit as n_exit_primary, b.n_exit as n_exit_no_threshold
from a
full outer join b using (source, contract_type, channel_type)
where a.n_all is distinct from b.n_all
   or a.n_exit is distinct from b.n_exit
