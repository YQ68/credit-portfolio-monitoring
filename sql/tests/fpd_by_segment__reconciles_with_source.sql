-- severity: error
-- Đối chiếu tổng mẫu số n_loans trong mart với đếm độc lập từ stg.installments_payments:
-- hợp đồng có kỳ 1 (bỏ version 0, lấy ĐÚNG version nhỏ nhất còn lại) đến hạn trước ít nhất
-- 30 ngày và installment_amount > 0. Đồng thời đối chiếu tử số FPD30: tính độc lập bằng
-- arg_min theo version thay vì window function như trong mart. Hai cặp số phải bằng nhau.
with per_version as (
    select
        sk_id_prev,
        installment_version,
        min(days_due)                                                   as days_due,
        max(installment_amount)                                         as installment_amount,
        coalesce(sum(payment_amount) filter (where days_late <= 30), 0) as paid_within_30d
    from stg.installments_payments
    where installment_number = 1
      and installment_version > 0
    group by sk_id_prev, installment_version
),
first_installment as (
    select
        sk_id_prev,
        arg_min(days_due, installment_version)           as days_due,
        arg_min(installment_amount, installment_version) as installment_amount,
        arg_min(paid_within_30d, installment_version)    as paid_within_30d
    from per_version
    group by sk_id_prev
),
eligible as (
    select * from first_installment
    where days_due <= -30 and installment_amount > 0
)
select
    (select sum(n_loans) from mart.fpd_by_segment)  as n_mart,
    (select count(*) from eligible)                 as n_source,
    (select sum(n_fpd30) from mart.fpd_by_segment)  as n_fpd30_mart,
    (select count(*) from eligible where paid_within_30d < installment_amount * 0.95) as n_fpd30_source
having n_mart != n_source or n_fpd30_mart != n_fpd30_source
