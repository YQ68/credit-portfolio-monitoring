-- severity: error
-- Grain phải là 1 dòng / channel_type / contract_type / client_type / yield_group, không trùng.
select channel_type, contract_type, client_type, yield_group, count(*) as n_dup
from mart.funnel_by_channel
group by channel_type, contract_type, client_type, yield_group
having count(*) > 1
