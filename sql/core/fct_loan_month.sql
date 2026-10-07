-- Bảng snapshot trung tâm của project.
-- Grain: 1 dòng / hợp đồng / tháng, từ tháng mở (MOB 0) đến tháng quan sát cuối.
-- Định nghĩa cột theo docs/metric_dictionary.md (M01 đến M05).
--
-- ĐỊNH NGHĨA QUÁ HẠN CHÍNH (từ 2026-10-04): SK_DPD_DEF, cột dpd.
--   Mô tả cột chính thức (data/raw/HomeCredit_columns_description.csv):
--     POS_CASH_balance.SK_DPD_DEF: "DPD during the month with tolerance (debts with low loan
--       amounts are ignored) of the previous credit"
--     credit_card_balance.SK_DPD_DEF: "DPD (Days past due) during the month with tolerance
--       (debts with low loan amounts are ignored) of the previous credit"
--   Tức DPD sau khi bỏ qua khoản nợ giá trị thấp, tương ứng khái niệm ngưỡng trọng yếu.
--   Lý do đổi: theo SK_DPD, phần lớn tháng 30+ là khoản dư lẻ sau kỳ trả cuối. Ở các tháng POS
--   đang mở thuộc bucket B4 90+ theo SK_DPD, 95,8% có SK_DPD_DEF = 0, 99,8% không còn kỳ nào
--   phải trả và dư nợ ước lượng có trung vị 0.
--
-- PHÂN TÍCH ĐỘ NHẠY: SK_DPD ("không áp ngưỡng trọng yếu") giữ ở các cột hậu tố _no_threshold.
--   Không dùng làm định nghĩa chính ở bất kỳ đâu.

create or replace table core.fct_loan_month as
with base as (
    select
        m.*,
        d.first_open_month,
        d.annuity_amount
    from core.int_loan_month m
    join core.dim_loan d on d.sk_id_prev = m.sk_id_prev
    where m.months_balance >= d.first_open_month  -- bỏ các tháng trước khi mở (Signed, Approved)
),

bucketed as (
    select
        *,
        case
            when dpd_def is null then null
            when dpd_def = 0     then 0
            when dpd_def <= 30   then 1
            when dpd_def <= 60   then 2
            when dpd_def <= 90   then 3
            else 4
        end as dpd_bucket_order,
        case
            when dpd_raw is null then null
            when dpd_raw = 0     then 0
            when dpd_raw <= 30   then 1
            when dpd_raw <= 60   then 2
            when dpd_raw <= 90   then 3
            else 4
        end as dpd_bucket_order_no_threshold
    from base
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

    -- M01, M02: DPD và bucket theo định nghĩa chính (SK_DPD_DEF)
    dpd_def                               as dpd,
    dpd_bucket_order,
    case dpd_bucket_order
        when 0 then 'B0 Current'
        when 1 then 'B1 1-30'
        when 2 then 'B2 31-60'
        when 3 then 'B3 61-90'
        when 4 then 'B4 90+'
    end                                   as dpd_bucket,
    dpd_def > 30                          as is_30_plus,
    dpd_def > 90                          as is_90_plus,

    -- Độ nhạy: SK_DPD, không áp ngưỡng trọng yếu
    dpd_raw                               as dpd_no_threshold,
    dpd_bucket_order_no_threshold,
    case dpd_bucket_order_no_threshold
        when 0 then 'B0 Current'
        when 1 then 'B1 1-30'
        when 2 then 'B2 31-60'
        when 3 then 'B3 61-90'
        when 4 then 'B4 90+'
    end                                   as dpd_bucket_no_threshold,
    dpd_raw > 30                          as is_30_plus_no_threshold,
    dpd_raw > 90                          as is_90_plus_no_threshold,

    -- M03: nhóm nợ proxy theo DPD chính
    case
        when dpd_def is null then null
        when dpd_def < 10    then 1
        when dpd_def <= 90   then 2
        when dpd_def <= 180  then 3
        when dpd_def <= 360  then 4
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
from bucketed;
