-- M08. Vintage ever 30+@MOBn: tỷ lệ hợp đồng TỪNG có DPD (days past due, số ngày quá hạn)
-- trên 30 ngày tính đến MOB n (month on book, số tháng kể từ tháng hợp đồng bắt đầu mở).
-- Câu hỏi kinh doanh: phân khúc nào xấu đi nhanh hơn khi so ở cùng tuổi hợp đồng?
--
-- Grain: 1 dòng / source / contract_type / channel_type / client_type / yield_group / tenor_group / mob.
-- Báo cáo MOB 0 đến 36.
--
-- CẢNH BÁO KHI GOM NHÓM: chỉ được cộng các cột ĐẾM (n_loans, n_ever_30_plus, ...) rồi chia lại.
-- Lấy trung bình cột ever_30_plus_rate giữa các dòng là SAI.
--
-- Mẫu số tại MOB n (theo docs/metric_dictionary.md M08):
--   hợp đồng đã biết kết quả đến MOB n, tức max_mob >= n HOẶC đã tất toán (end_state = 'closed').
--   Không lọc theo nhãn end_state cho phần còn lại: nhãn 'unknown' (183.144 hợp đồng) thực chất
--   cũng chỉ là cắt phải (lịch sử dừng ở tháng -2, -3), không phải lỗi dữ liệu.
-- Loại khỏi mẫu số:
--   - is_partial_history: thiếu lịch sử đầu nên MOB không đáng tin (cắt trái theo cửa sổ dữ liệu,
--     hoặc đã trả kỳ ngay tại tháng mở đầu tiên). 93.751 hợp đồng.
--   - end_state = 'never_open': chưa bao giờ ở trạng thái mở nên không có MOB 0. 4.029 hợp đồng.
--   Tổng cộng loại 95.695 hợp đồng trên 1.040.632, mẫu số gốc còn 944.937. Hai nhóm giao nhau
--   2.085 hợp đồng, nên tổng loại không phải 93.751 + 4.029.
--   Chi tiết ghi ở docs/metric_dictionary.md mục M08.
--
-- Cột n_observed_full tách riêng số hợp đồng ĐÃ QUAN SÁT ĐỦ đến MOB n (max_mob >= n), khác với
-- n_loans vốn còn gồm cả hợp đồng tất toán sớm. Tại MOB 24 chỉ có 70.635 hợp đồng quan sát đủ
-- trên 679.223 của mẫu số, người đọc phải thấy được độ mỏng này trước khi diễn giải đường cong.
--
-- Cột ..._tolerant tính theo dpd_tolerant (SK_DPD_DEF, DPD có dung sai) để đối chiếu, xem
-- docs/data_notes.md mục 7. Chỉ tiêu chính vẫn theo cột dpd (SK_DPD).

create or replace table mart.vintage as
with first_30_plus as (
    -- MOB đầu tiên mà hợp đồng quá hạn trên 30 ngày. Hợp đồng chưa bao giờ 30+ không có dòng.
    select
        sk_id_prev,
        min(mob) filter (where is_30_plus)           as first_30_plus_mob,
        min(mob) filter (where is_30_plus_tolerant)  as first_30_plus_tolerant_mob
    from core.fct_loan_month
    group by sk_id_prev
),

loans as (
    select
        d.sk_id_prev,
        d.source,
        -- Hợp đồng không khớp previous_application (48.794 hợp đồng) mang nhãn '(không rõ)'
        -- ở mọi cột phân khúc, không loại âm thầm khỏi mart.
        case when d.has_application then coalesce(d.contract_type, 'Unknown') else '(không rõ)' end as contract_type,
        case
            when not d.has_application                          then '(không rõ)'
            when d.channel_type is null                         then 'Unknown'
            -- Hai kênh quá nhỏ (Car dealer 452 hồ sơ, Channel of corporate sales 6.117) gom vào 'Khác'
            when d.channel_type in ('Car dealer', 'Channel of corporate sales') then 'Khác'
            else d.channel_type
        end                                                                                        as channel_type,
        case when d.has_application then coalesce(d.client_type, 'Unknown') else '(không rõ)' end   as client_type,
        -- yield_group null ở khoảng 30% hồ sơ, giữ thành một nhóm riêng có nhãn rõ ràng.
        case when d.has_application then coalesce(d.yield_group, 'Unknown') else '(không rõ)' end   as yield_group,
        case
            when not d.has_application     then '(không rõ)'
            when d.source = 'credit_card'  then 'Revolving'
            when d.tenor_months is null    then 'Unknown'
            when d.tenor_months <= 12      then '<=12m'
            when d.tenor_months <= 24      then '13-24m'
            else '>24m'
        end                                                                                        as tenor_group,
        d.max_mob,
        d.end_state,
        f.first_30_plus_mob,            -- NULL: chưa bao giờ 30+
        f.first_30_plus_tolerant_mob
    from core.dim_loan d
    left join first_30_plus f on f.sk_id_prev = d.sk_id_prev
    where d.end_state <> 'never_open'
      and not d.is_partial_history
),

mob_grid as (
    select mob from range(0, 37) t(mob)
),

loan_mob as (
    select
        l.source,
        l.contract_type,
        l.channel_type,
        l.client_type,
        l.yield_group,
        l.tenor_group,
        g.mob,
        l.max_mob >= g.mob                                              as is_observed_full,
        coalesce(l.first_30_plus_mob <= g.mob, false)                   as is_ever_30_plus,
        coalesce(l.first_30_plus_tolerant_mob <= g.mob, false)          as is_ever_30_plus_tolerant
    from loans l
    join mob_grid g
      on g.mob <= l.max_mob          -- đã quan sát thực sự tới MOB n
      or l.end_state = 'closed'      -- đã tất toán: kết quả không thể đổi sau khi đóng
)

select
    source,
    contract_type,
    channel_type,
    client_type,
    yield_group,
    tenor_group,
    mob,
    count(*)                                                   as n_loans,              -- mẫu số M08
    count(*) filter (where is_observed_full)                   as n_observed_full,      -- thật sự sống đến MOB n
    count(*) - count(*) filter (where is_observed_full)        as n_closed_early,       -- tất toán trước MOB n
    count(*) filter (where is_ever_30_plus)                    as n_ever_30_plus,       -- tử số M08
    count(*) filter (where is_ever_30_plus_tolerant)           as n_ever_30_plus_tolerant,
    count(*) filter (where is_ever_30_plus) * 1.0 / count(*)            as ever_30_plus_rate,
    count(*) filter (where is_ever_30_plus_tolerant) * 1.0 / count(*)   as ever_30_plus_rate_tolerant
from loan_mob
group by source, contract_type, channel_type, client_type, yield_group, tenor_group, mob;
