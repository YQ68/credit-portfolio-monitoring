-- severity: error
-- Grain không được trùng: mỗi ô của ma trận chỉ một dòng. Kiểm cả bảng chính mart.roll_rate
-- (SK_DPD_DEF) và bảng độ nhạy mart.roll_rate_no_threshold (SK_DPD).
with both_tables as (
    select 'roll_rate' as tbl, * from mart.roll_rate
    union all
    select 'roll_rate_no_threshold' as tbl, * from mart.roll_rate_no_threshold
)
select
    tbl, source, contract_type, channel_type, from_state, to_state,
    count(*) as n_rows
from both_tables
group by tbl, source, contract_type, channel_type, from_state, to_state
having count(*) > 1
