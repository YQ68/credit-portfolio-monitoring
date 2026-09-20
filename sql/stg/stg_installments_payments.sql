-- Lịch sử trả nợ theo kỳ.
-- Theo mô tả của Kaggle: 1 dòng cho mỗi lần trả và 1 dòng cho mỗi kỳ bị bỏ lỡ.
-- Một kỳ có thể được trả thành nhiều lần, nên đây KHÔNG phải grain 1 dòng / kỳ.

create or replace table stg.installments_payments as
select
    sk_id_prev,
    sk_id_curr,
    num_instalment_version  as installment_version,  -- lịch trả nợ có thể đổi phiên bản
    num_instalment_number   as installment_number,
    days_instalment         as days_due,
    days_entry_payment      as days_paid,
    amt_instalment          as installment_amount,
    amt_payment             as payment_amount,
    days_entry_payment - days_instalment as days_late  -- âm = trả sớm, NULL = không có ngày trả
from raw.installments_payments;
