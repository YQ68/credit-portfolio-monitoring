-- Grain: 1 dòng / hợp đồng có lịch sử tháng (sk_id_prev).
-- Gắn thuộc tính sản phẩm, kênh từ hồ sơ vay và các mốc vòng đời dùng cho vintage.

create or replace table core.dim_loan as
with lifecycle as (
    select
        sk_id_prev,
        any_value(sk_id_curr)                     as sk_id_curr,
        any_value(source)                         as source,
        min(months_balance)                       as first_observed_month,
        min(months_balance) filter (where core.is_open_status(contract_status))
                                                  as first_open_month,
        max(months_balance)                       as last_observed_month,
        arg_max(contract_status, months_balance)  as last_status,
        arg_max(installments_remaining, months_balance)
                                                  as installments_remaining_at_last,  -- NULL với thẻ
        count(*)                                  as n_months_observed,
        -- Số kỳ đã trả tại tháng mở đầu tiên. Nếu lớn hơn 0 thì hợp đồng đã chạy
        -- trước khi dữ liệu bắt đầu, nên MOB tính ra thấp hơn thực tế.
        arg_min(installments_total - installments_remaining, months_balance)
            filter (where core.is_open_status(contract_status))
                                                  as installments_paid_at_open
    from core.int_loan_month
    group by sk_id_prev
),

data_window as (
    select min(months_balance) as earliest_month
    from core.int_loan_month
)

select
    l.sk_id_prev,
    l.sk_id_curr,
    l.source,

    -- Thuộc tính sản phẩm, kênh, khách hàng
    a.contract_type,
    a.portfolio,
    a.product_type,
    a.channel_type,
    a.client_type,
    a.yield_group,
    a.product_combination,
    a.goods_category,
    a.seller_industry,

    -- Số tiền và kỳ hạn
    a.credit_amount,
    a.annuity_amount,
    a.down_payment_amount,
    a.tenor_months,
    a.days_decision,

    -- Mốc vòng đời (tháng tương đối)
    l.first_observed_month,
    l.first_open_month,                                        -- MOB 0
    l.last_observed_month,
    l.last_observed_month - l.first_open_month  as max_mob,
    l.last_status,
    l.installments_remaining_at_last,
    l.n_months_observed,
    a.days_termination,                          -- NULL: 365243 hoặc trống trong dữ liệu gốc
    -- Nhãn kết thúc. 'closed_inferred' (thêm 2026-10-04): lịch sử dừng trước tháng -1 khi trạng thái
    -- cuối vẫn là trạng thái mở, nhưng hồ sơ có DAYS_TERMINATION đã qua. Bằng chứng (ghi ở comment
    -- mart_vintage.sql): trong nhóm trước đây gọi là 'unknown', 74.270 trên 74.294 hợp đồng POS có hồ
    -- sơ dừng ở tháng -17 hoặc sớm hơn có DAYS_TERMINATION, trung vị 0,9 tháng sau dòng cuối; hợp đồng
    -- 'closed' có DAYS_TERMINATION trùng tháng Completed; hợp đồng 'censored' gần như toàn bộ là
    -- 365243 (chưa kết thúc). Tức đây là hợp đồng đã kết thúc mà thiếu dòng Completed.
    -- Mô tả cột chính thức ghi "expected termination", nên đây là suy luận, không phải xác nhận.
    case
        when l.first_open_month is null   then 'never_open'
        when l.last_status = 'Completed'  then 'closed'          -- đã tất toán, biết kết quả cuối
        when l.last_observed_month = -1   then 'censored'        -- còn mở khi dữ liệu kết thúc
        when a.days_termination is not null
                                          then 'closed_inferred' -- dừng sớm, hồ sơ có ngày kết thúc
        else 'unknown'                                           -- dừng sớm, không có ngày kết thúc
    end                                         as end_state,
    l.first_observed_month = w.earliest_month   as is_left_truncated,  -- có thể đã mở trước cửa sổ dữ liệu
    l.installments_paid_at_open,
    -- Cờ tổng hợp cho vintage: hợp đồng thiếu lịch sử đầu, MOB không đáng tin.
    -- Gồm cắt trái theo cửa sổ dữ liệu và hợp đồng đã trả kỳ ngay tại tháng mở đầu tiên.
    l.first_observed_month = w.earliest_month
        or coalesce(l.installments_paid_at_open, 0) > 0
                                                as is_partial_history,
    a.sk_id_prev is not null                    as has_application
from lifecycle l
cross join data_window w
left join stg.previous_application a on a.sk_id_prev = l.sk_id_prev;
