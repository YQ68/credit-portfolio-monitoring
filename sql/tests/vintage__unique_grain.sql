-- severity: error
-- Grain của mart.vintage không được trùng: mỗi tổ hợp phân khúc và MOB chỉ một dòng.
select
    source, contract_type, channel_type, client_type, yield_group, tenor_group, mob,
    count(*) as n_rows
from mart.vintage
group by source, contract_type, channel_type, client_type, yield_group, tenor_group, mob
having count(*) > 1
