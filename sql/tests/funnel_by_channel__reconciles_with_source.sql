-- severity: error
-- Đối chiếu tổng số hồ sơ trong mart với đếm độc lập từ stg.previous_application
-- (cùng điều kiện lọc trùng). Hai số phải bằng nhau.
select
    (select sum(n_applications) from mart.funnel_by_channel) as n_mart,
    (
        select count(*)
        from stg.previous_application
        where is_last_appl_per_contract and is_last_appl_in_day
    ) as n_source
having n_mart != n_source
