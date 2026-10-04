-- M09 (roll rate) và M10 (cure rate). Ma trận chuyển trạng thái: hợp đồng đang ở trạng thái nào
-- tại tháng t thì sang trạng thái nào tại tháng t + 1.
-- Câu hỏi kinh doanh: khách quá hạn di chuyển giữa các nhóm ngày quá hạn thế nào, bao nhiêu phần
-- trăm tiếp tục xấu đi, bao nhiêu phần trăm quay về không quá hạn (cure rate, M10)?
--
-- Grain: 1 dòng / source / contract_type / channel_type / from_state / to_state.
--
-- CẢNH BÁO KHI GOM NHÓM: chỉ được cộng các cột ĐẾM (n_loans, n_from) rồi chia lại.
-- Lấy trung bình cột roll_rate giữa các dòng là SAI.
--
-- Viết tắt: DPD (days past due, số ngày quá hạn). Bucket B0 = 0 ngày, B1 = 1-30, B2 = 31-60,
-- B3 = 61-90, B4 = trên 90 ngày.
--
-- TRẠNG THÁI XUẤT PHÁT (tháng t): chỉ các tháng hợp đồng đang mở, theo bucket B0 đến B4.
-- TRẠNG THÁI ĐÍCH (tháng t + 1):
--   B0 đến B4  hợp đồng còn mở
--   Closed     contract_status = 'Completed'. Coi là trạng thái hấp thụ: chỉ 18 hợp đồng trên
--              1.040.632 quay lại trạng thái mở sau Completed (0,0017%), bỏ qua được.
--   Other      có dòng tháng t + 1 nhưng trạng thái không mở và không Completed
--              (ví dụ 'Returned to the store', 'Canceled').
--   Missing    KHÔNG có dòng cho đúng tháng t + 1. Gồm hai trường hợp, đếm riêng ở cột n_month_gap:
--              (a) lịch sử hợp đồng dừng hẳn ở tháng t: 182.821 dòng đang mở ở tháng t <= -2;
--              (b) hở tháng, dòng kế tiếp cách hơn 1 tháng: 26 dòng trong ma trận (toàn bảng có 375 cặp
--                  hở tháng, 0,003%, phần lớn không xuất phát từ tháng đang mở).
--              Tổng Missing trong ma trận là 182.847 dòng (182.821 + 26).
--              Không được loại âm thầm các dòng này, nếu loại thì tổng mỗi hàng không còn bằng 1.
--              Đừng nhầm với con số 1.036.603: đó là số dòng không có tháng kế tiếp đếm trên TOÀN BẢNG
--              core.fct_loan_month (mỗi hợp đồng có đúng một dòng cuối). Nó gồm cả 144.421 dòng đang mở ở
--              tháng -1 (bị loại khỏi trạng thái xuất phát, xem phần dưới) và 709.361 dòng không ở trạng
--              thái mở. Chỉ 182.821 dòng trong đó đi vào ma trận dưới nhãn Missing.
--
-- PHÂN BIỆT QUAN TRỌNG giữa 'Missing' và tháng bị loại:
--   Tháng t = -1 bị LOẠI KHỎI trạng thái xuất phát. Dữ liệu kết thúc ở tháng -1 nên về nguyên tắc
--   không thể quan sát tháng sau: đây là CẮT PHẢI của cửa sổ dữ liệu, không phải mất dữ liệu.
--   Ngược lại, 'Missing' là những tháng t <= -2 lẽ ra phải có tháng sau mà không có: đó thực sự là
--   thiếu dữ liệu, nên phải nằm trong ma trận và kéo tỷ lệ xuống.
--   Theo profile: 12.693.134 trên 13.730.112 dòng (92,45%) có tháng kế tiếp hợp lệ.
--
-- EXPOSURE: ngoài tỷ lệ theo số hợp đồng còn có tỷ lệ theo dư nợ ước lượng (exposure_proxy, M05).
--   3,41% dòng POS có exposure_proxy null (337.877 dòng, do hợp đồng thiếu hồ sơ nên không có
--   annuity_amount). Các dòng đó KHÔNG được coi như bằng 0: chúng bị bỏ qua khi cộng tiền và đếm
--   riêng ở cột n_exposure_null. Vì vậy mẫu số tiền và mẫu số hợp đồng không tương ứng 1-1.
--
-- M10 CURE RATE lấy trực tiếp từ bảng này, không có mart riêng:
--   select from_state, sum(n_loans) filter (where to_state = 'B0 Current') / sum(n_loans)
--   from mart.roll_rate where from_state <> 'B0 Current' group by from_state;

create or replace table mart.roll_rate as
with months as (
    select
        f.sk_id_prev,
        f.source,
        d.contract_type,
        d.channel_type,
        d.has_application,
        f.months_balance,
        f.is_open,
        f.dpd_bucket,
        f.dpd_bucket_order,
        f.exposure_proxy,
        lead(f.months_balance)  over w as next_month,
        lead(f.is_open)         over w as next_is_open,
        lead(f.is_closed)       over w as next_is_closed,
        lead(f.dpd_bucket)      over w as next_bucket,
        lead(f.exposure_proxy)  over w as next_exposure
    from core.fct_loan_month f
    join core.dim_loan d on d.sk_id_prev = f.sk_id_prev
    window w as (partition by f.sk_id_prev order by f.months_balance)
),

transitions as (
    select
        source,
        -- Hợp đồng không khớp previous_application mang nhãn '(không rõ)', không loại âm thầm.
        case when has_application then coalesce(contract_type, 'Unknown') else '(không rõ)' end as contract_type,
        case
            when not has_application                            then '(không rõ)'
            when channel_type is null                           then 'Unknown'
            when channel_type in ('Car dealer', 'Channel of corporate sales') then 'Khác'
            else channel_type
        end                                                                                    as channel_type,
        dpd_bucket        as from_state,
        dpd_bucket_order  as from_order,
        case
            when next_month is null or next_month <> months_balance + 1 then 'Missing'
            when next_is_open   then next_bucket
            when next_is_closed then 'Closed'
            else 'Other'
        end               as to_state,
        -- Tách riêng phần Missing do hở tháng (có dòng sau nhưng cách hơn 1 tháng)
        next_month is not null and next_month > months_balance + 1                as is_month_gap,
        exposure_proxy,
        case when next_month = months_balance + 1 then next_exposure end          as next_exposure
    from months
    where is_open
      and months_balance < -1   -- loại tháng -1: cắt phải, không quan sát được tháng sau
),

cells as (
    select
        source,
        contract_type,
        channel_type,
        from_state,
        from_order,
        to_state,
        count(*)                                        as n_loans,
        count(*) filter (where is_month_gap)            as n_month_gap,
        count(*) filter (where exposure_proxy is null)  as n_exposure_null,
        coalesce(sum(exposure_proxy), 0)                as exposure_from,
        coalesce(sum(next_exposure), 0)                 as exposure_to
    from transitions
    group by source, contract_type, channel_type, from_state, from_order, to_state
)

select
    source,
    contract_type,
    channel_type,
    from_state,
    from_order,
    to_state,
    case to_state
        when 'B0 Current' then 0
        when 'B1 1-30'    then 1
        when 'B2 31-60'   then 2
        when 'B3 61-90'   then 3
        when 'B4 90+'     then 4
        when 'Closed'     then 5
        when 'Other'      then 6
        when 'Missing'    then 7
    end                                                                as to_order,
    n_loans,
    sum(n_loans) over w                                                as n_from,
    n_loans * 1.0 / sum(n_loans) over w                                as roll_rate,
    n_month_gap,
    n_exposure_null,
    sum(n_exposure_null) over w                                        as n_exposure_null_from,
    exposure_from,
    sum(exposure_from) over w                                          as exposure_from_total,
    -- Tỷ lệ theo tiền: dư nợ tháng t của các hợp đồng đi tới trạng thái j, chia cho tổng dư nợ
    -- tháng t của cả hàng. Chỉ tính trên các dòng có exposure_proxy khác null.
    case when sum(exposure_from) over w > 0
         then exposure_from / sum(exposure_from) over w end            as exposure_roll_rate,
    exposure_to
from cells
window w as (partition by source, contract_type, channel_type, from_state);
