-- M08. Vintage ever 30+@MOBn: tỷ lệ hợp đồng TỪNG có DPD (days past due, số ngày quá hạn)
-- trên 30 ngày tính đến MOB n (month on book, số tháng kể từ tháng hợp đồng bắt đầu mở).
-- Câu hỏi kinh doanh: phân khúc nào xấu đi nhanh hơn khi so ở cùng tuổi hợp đồng?
--
-- Grain: 1 dòng / source / contract_type / channel_type / client_type / yield_group / tenor_group /
-- origination_cohort / mob. Báo cáo MOB 0 đến 36.
--
-- ĐỢT MỞ HỢP ĐỒNG (origination_cohort, thêm 2026-10-04 sau lần soát thứ hai): nhóm 12 tháng của
-- core.dim_loan.first_open_month (tháng tương đối của MOB 0 so với ngày nộp hồ sơ hiện tại), căn
-- từ tháng -96 nên đợt cuối kết thúc đúng tháng -1: '-96 đến -85', '-84 đến -73', ..., '-12 đến -1'.
-- origination_cohort_start là tháng đầu của đợt, dùng để sắp xếp. Lý do: đợt mở là biến gây nhiễu
-- mạnh. Ever 30+@MOB12 giảm hàng chục lần từ đợt cũ nhất đến đợt gần nhất trong cùng sản phẩm, và
-- các kênh có cơ cấu đợt mở rất khác nhau, nên mọi so sánh kênh, sản phẩm phải phân tầng theo đợt.
-- Mốc 12 tháng là một năm tương đối, đủ mịn để bắt xu hướng và đủ dày để hầu hết ô sản phẩm × đợt
-- có trên 1.000 hợp đồng. Độ nhạy theo cách cắt khác (3 nhóm: -60 trở về trước, -59 đến -36, -35
-- trở về sau; và nhóm 24 tháng) tính trong scripts/compute_findings.py, khóa origination_cohort.
-- Đây là tháng TƯƠNG ĐỐI của từng khách, không phải tháng lịch: hai hợp đồng cùng đợt có thể giải
-- ngân ở hai thời điểm lịch khác nhau.
-- Lưu ý khi so đợt: đợt chưa đủ tuổi tới MOB n (first_open_month > -1 - n) chỉ có hợp đồng đã đóng
-- sớm trong mẫu số tại MOB n, nên không so được với đợt khác ở MOB đó.
--
-- CẢNH BÁO KHI GOM NHÓM: chỉ được cộng các cột ĐẾM (n_loans, n_ever_30_plus, ...) rồi chia lại.
-- Lấy trung bình cột ever_30_plus_rate giữa các dòng là SAI.
--
-- ĐỊNH NGHĨA QUÁ HẠN CHÍNH: SK_DPD_DEF (cột is_30_plus của core.fct_loan_month, có ngưỡng trọng
-- yếu). Cột hậu tố _no_threshold tính theo SK_DPD (không áp ngưỡng trọng yếu), chỉ dùng cho phân
-- tích độ nhạy.
--
-- Mẫu số tại MOB n (theo docs/metric_dictionary.md M08):
--   hợp đồng đã biết kết quả đến MOB n, tức max_mob >= n HOẶC đã kết thúc
--   (end_state in ('closed', 'closed_inferred')).
--   Nhãn 'closed_inferred' (core.dim_loan) là hợp đồng lịch sử dừng trước tháng -1 khi còn trạng
--   thái mở nhưng hồ sơ có DAYS_TERMINATION. Trước 2026-10-04 cả nhóm này nằm trong 'unknown'
--   (183.144 hợp đồng) và bị mô tả nhầm là "dừng sớm 1 đến 3 tháng". Thực tế nhóm 'unknown' cũ tách
--   làm hai: (a) dừng ở tháng -2 đến -4 (106.569 hợp đồng, POS và thẻ), DAYS_TERMINATION phần lớn
--   là 365243 (chưa kết thúc), giống cắt phải; (b) dừng ở tháng -17 hoặc sớm hơn (76.575 hợp đồng,
--   toàn POS, không hợp đồng nào dừng ở tháng -5 đến -16), gần như toàn bộ có DAYS_TERMINATION
--   khoảng 1 tháng sau dòng cuối, tức đã kết thúc mà thiếu dòng Completed.
--   Hợp đồng 'unknown' còn lại (không có ngày kết thúc) vẫn chỉ vào mẫu số khi max_mob >= n.
--   Độ nhạy của lựa chọn này (quy tắc cũ, quy tắc "còn 0 kỳ thì coi là đóng") tính trong
--   scripts/compute_findings.py, mục unknown_sensitivity của data/export/findings.json.
-- Loại khỏi mẫu số:
--   - is_partial_history: thiếu lịch sử đầu nên MOB không đáng tin (cắt trái theo cửa sổ dữ liệu,
--     hoặc đã trả kỳ ngay tại tháng mở đầu tiên). 93.751 hợp đồng.
--   - end_state = 'never_open': chưa bao giờ ở trạng thái mở nên không có MOB 0. 4.029 hợp đồng.
--   Tổng cộng loại 95.695 hợp đồng trên 1.040.632, mẫu số gốc còn 944.937. Hai nhóm giao nhau
--   2.085 hợp đồng, nên tổng loại không phải 93.751 + 4.029.
--   Chi tiết ghi ở docs/metric_dictionary.md mục M08.
--
-- Cột n_observed_full tách riêng số hợp đồng ĐÃ QUAN SÁT ĐỦ đến MOB n (max_mob >= n), khác với
-- n_loans vốn còn gồm cả hợp đồng đã kết thúc sớm. Tại MOB 24 chỉ có 70.635 hợp đồng quan sát đủ
-- trên 763.989 của mẫu số (9,2%; trước khi có nhãn closed_inferred là 679.223), người đọc phải thấy
-- được độ mỏng này trước khi diễn giải đường cong.
--
-- ĐỘ NHẠY THỨ HAI (n_ever_30_plus_due_only, thêm 2026-10-04): định nghĩa "giữa" hai định nghĩa
-- trên. Khoản trả góp: SK_DPD > 30 nhưng chỉ tính ở tháng còn kỳ phải trả (installments_remaining
-- > 0), tức bỏ khoản dư lẻ sau kỳ trả cuối mà không dùng ngưỡng không công bố của SK_DPD_DEF. Thẻ:
-- giữ định nghĩa chính SK_DPD_DEF (thẻ không có khái niệm số kỳ còn lại).
--
-- Đổi tên cột 2026-10-04: n_ever_30_plus và ever_30_plus_rate nay theo SK_DPD_DEF (trước là
-- SK_DPD). Cặp n_ever_30_plus_tolerant, ever_30_plus_rate_tolerant bị bỏ (trùng cột chính); thay
-- bằng n_ever_30_plus_no_threshold, ever_30_plus_rate_no_threshold theo SK_DPD.

create or replace table mart.vintage as
with first_30_plus as (
    -- MOB đầu tiên mà hợp đồng quá hạn trên 30 ngày. Hợp đồng chưa bao giờ 30+ không có dòng.
    select
        sk_id_prev,
        min(mob) filter (where is_30_plus)               as first_30_plus_mob,
        min(mob) filter (where is_30_plus_no_threshold)  as first_30_plus_no_threshold_mob,
        min(mob) filter (where (source = 'credit_card' and is_30_plus)
                            or (source = 'pos_cash' and is_30_plus_no_threshold and installments_remaining > 0))
                                                         as first_30_plus_due_only_mob
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
        -- Đợt mở 12 tháng, căn từ tháng -96 (tháng sớm nhất của dữ liệu).
        -96 + 12 * ((d.first_open_month + 96) // 12)                                               as origination_cohort_start,
        d.max_mob,
        d.end_state,
        f.first_30_plus_mob,            -- NULL: chưa bao giờ 30+
        f.first_30_plus_no_threshold_mob,
        f.first_30_plus_due_only_mob
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
        l.origination_cohort_start,
        g.mob,
        l.max_mob >= g.mob                                              as is_observed_full,
        coalesce(l.first_30_plus_mob <= g.mob, false)                   as is_ever_30_plus,
        coalesce(l.first_30_plus_no_threshold_mob <= g.mob, false)      as is_ever_30_plus_no_threshold,
        coalesce(l.first_30_plus_due_only_mob <= g.mob, false)          as is_ever_30_plus_due_only
    from loans l
    join mob_grid g
      on g.mob <= l.max_mob          -- đã quan sát thực sự tới MOB n
      or l.end_state in ('closed', 'closed_inferred')  -- đã kết thúc: kết quả không đổi sau khi đóng
)

select
    source,
    contract_type,
    channel_type,
    client_type,
    yield_group,
    tenor_group,
    origination_cohort_start::varchar || ' đến ' || (origination_cohort_start + 11)::varchar as origination_cohort,
    origination_cohort_start,
    mob,
    count(*)                                                   as n_loans,              -- mẫu số M08
    count(*) filter (where is_observed_full)                   as n_observed_full,      -- thật sự sống đến MOB n
    count(*) - count(*) filter (where is_observed_full)        as n_closed_early,       -- tất toán trước MOB n
    count(*) filter (where is_ever_30_plus)                    as n_ever_30_plus,       -- tử số M08
    count(*) filter (where is_ever_30_plus_no_threshold)       as n_ever_30_plus_no_threshold,  -- độ nhạy
    count(*) filter (where is_ever_30_plus_due_only)           as n_ever_30_plus_due_only,      -- độ nhạy thứ hai
    count(*) filter (where is_ever_30_plus) * 1.0 / count(*)                as ever_30_plus_rate,
    count(*) filter (where is_ever_30_plus_no_threshold) * 1.0 / count(*)   as ever_30_plus_rate_no_threshold
from loan_mob
group by source, contract_type, channel_type, client_type, yield_group, tenor_group, origination_cohort_start, mob;
