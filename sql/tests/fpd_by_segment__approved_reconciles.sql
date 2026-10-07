-- severity: error
-- Hồ sơ Approved (đã lọc trùng) không có dòng kỳ 1 nào phải được chia hết vào hai cột
-- n_approved_not_activated (không có lịch trả) và n_approved_scheduled_no_installment (có lịch trả),
-- không thiếu, không thừa. Đếm độc lập bằng anti join.
select
    (select sum(n_approved_not_activated) + sum(n_approved_scheduled_no_installment)
     from mart.fpd_by_segment) as n_mart,
    (
        select count(*)
        from stg.previous_application a
        where a.application_status = 'Approved'
          and a.is_last_appl_per_contract
          and a.is_last_appl_in_day
          and not exists (
              select 1 from stg.installments_payments i
              where i.sk_id_prev = a.sk_id_prev and i.installment_number = 1
          )
    ) as n_source
having n_mart != n_source
