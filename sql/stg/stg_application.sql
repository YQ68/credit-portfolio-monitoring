-- Hồ sơ vay hiện tại. Grain: 1 dòng / sk_id_curr.
-- Chỉ lấy các cột dùng để phân khúc khách hàng; thêm cột khi cần.

create or replace table stg.application as
select
    sk_id_curr,
    target,                                     -- 1 = khách gặp khó khăn trả nợ ở khoản vay hiện tại
    name_contract_type          as contract_type,
    nullif(code_gender, 'XNA')  as gender,
    cnt_children                as children_count,
    amt_income_total            as income_total,
    amt_credit                  as credit_amount,
    amt_annuity                 as annuity_amount,
    amt_goods_price             as goods_price,
    name_income_type            as income_type,
    name_education_type         as education_type,
    name_family_status          as family_status,
    name_housing_type           as housing_type,
    occupation_type,
    region_rating_client,
    -days_birth / 365.25        as age_years,
    -nullif(days_employed, 365243) / 365.25 as employed_years,
    ext_source_1,
    ext_source_2,
    ext_source_3
from raw.application_train;
