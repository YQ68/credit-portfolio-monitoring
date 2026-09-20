-- severity: error
-- Đối chiếu tổng mẫu số n_loans trong mart với đếm độc lập từ stg.installments_payments:
-- hợp đồng có kỳ 1 (bỏ version 0, lấy version nhỏ nhất) đến hạn trước ít nhất 30 ngày
-- và installment_amount > 0. Hai số phải bằng nhau.
with first_installment as (
    select
        sk_id_prev,
        min(days_due)            as days_due,
        max(installment_amount)  as installment_amount
    from stg.installments_payments
    where installment_number = 1
      and installment_version > 0
    group by sk_id_prev
)
select
    (select sum(n_loans) from mart.fpd_by_segment) as n_mart,
    (
        select count(*)
        from first_installment
        where days_due <= -30
          and installment_amount > 0
    ) as n_source
having n_mart != n_source
