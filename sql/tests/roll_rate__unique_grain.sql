-- severity: error
-- Grain của mart.roll_rate không được trùng: mỗi ô của ma trận chỉ một dòng.
select
    source, contract_type, channel_type, from_state, to_state,
    count(*) as n_rows
from mart.roll_rate
group by source, contract_type, channel_type, from_state, to_state
having count(*) > 1
