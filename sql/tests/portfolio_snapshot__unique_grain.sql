-- severity: error
-- Grain phải là 1 dòng / contract_type / channel_type / dpd_bucket, không trùng.
select contract_type, channel_type, dpd_bucket, count(*) as n_dup
from mart.portfolio_snapshot
group by contract_type, channel_type, dpd_bucket
having count(*) > 1
