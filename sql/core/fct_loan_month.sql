-- Bảng snapshot trung tâm của project.
-- Grain: 1 dòng / hợp đồng / tháng, từ tháng mở (MOB 0) đến tháng quan sát cuối.
-- Định nghĩa cột theo docs/metric_dictionary.md (M01 đến M05).

create or replace table core.fct_loan_month as
with base as (
    select
        m.*,
        d.first_open_month,
        d.annuity_amount,
        case
            when m.dpd_raw is null then null
            when m.dpd_raw = 0     then 0
            when m.dpd_raw <= 30   then 1
            when m.dpd_raw <= 60   then 2
            when m.dpd_raw <= 90   then 3
            else 4
        end as dpd_bucket_order
    from core.int_loan_month m
    join core.dim_loan d on d.sk_id_prev = m.sk_id_prev
    where m.months_balance >= d.first_open_month  -- bỏ các tháng trước khi mở (Signed, Approved)
)

select
    sk_id_prev,
    sk_id_curr,
    source,
    months_balance,
    months_balance - first_open_month     as mob,              -- M04
    contract_status,
    core.is_open_status(contract_status)  as is_open,
    contract_status = 'Completed'         as is_closed,

    -- M01, M02: DPD và bucket.
    -- Từ 2026-09-20 cột DPD chính là SK_DPD (không dung sai). SK_DPD_DEF giữ ở dpd_tolerant
    -- làm chỉ tiêu phụ. Lý do đổi: docs/data_notes.md mục 7.
    dpd_raw                               as dpd,
    dpd_def                               as dpd_tolerant,
    dpd_bucket_order,
    case dpd_bucket_order
        when 0 then 'B0 Current'
        when 1 then 'B1 1-30'
        when 2 then 'B2 31-60'
        when 3 then 'B3 61-90'
        when 4 then 'B4 90+'
    end                                   as dpd_bucket,
    dpd_raw > 30                          as is_30_plus,
    dpd_raw > 90                          as is_90_plus,
    dpd_def > 30                          as is_30_plus_tolerant,   -- chỉ tiêu phụ để đối chiếu

    -- M03: nhóm nợ proxy theo DPD
    case
        when dpd_raw is null then null
        when dpd_raw < 10    then 1
        when dpd_raw <= 90   then 2
        when dpd_raw <= 180  then 3
        when dpd_raw <= 360  then 4
        else 5
    end                                   as debt_group_vn,

    -- M05: exposure proxy
    case
        when source = 'pos_cash' then installments_remaining * annuity_amount
        when balance_amount < 0  then 0
        else balance_amount
    end                                   as exposure_proxy,
    credit_limit,
    installments_total,
    installments_remaining
from base;
