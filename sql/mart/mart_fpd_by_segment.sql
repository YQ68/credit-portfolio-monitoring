-- M11. FPD30 (first payment default 30, tức kỳ trả đầu tiên chưa trả đủ sau 30 ngày
-- kể từ ngày đến hạn): hợp đồng trả góp mà kỳ trả đầu tiên chưa được trả đủ.
-- Câu hỏi: kênh, sản phẩm nào mang về khách có dấu hiệu rủi ro ngay từ kỳ đầu?
-- Grain: 1 dòng / channel_type / contract_type / client_type / yield_group.
--
-- Lưu tử số, mẫu số dạng số đếm để cộng dồn được khi gom nhóm lớn hơn.
--
-- HỒ SƠ DUYỆT KHÔNG CÓ DÒNG KỲ 1 (sửa 2026-10-04): trước đây nhóm này (77.885 hồ sơ) bị gọi là
-- "vùng mù" và fpd30_rate bị gọi là chặn dưới, với giả định đó là hợp đồng xấu bỏ hẳn kỳ 1. Kiểm
-- tra lại: 77.884 trên 77.885 hồ sơ không có lịch trả (DAYS_FIRST_DUE là 365243 hoặc trống, tức
-- stg.previous_application.days_first_due IS NULL), nghĩa là được duyệt nhưng không giải ngân hoặc
-- chưa kích hoạt. Chúng không bao giờ thuộc mẫu số FPD và không phải hợp đồng xấu biến mất. Đếm
-- riêng ở hai cột:
--   n_approved_not_activated             duyệt, không có lịch trả, không có dòng kỳ 1
--   n_approved_scheduled_no_installment  duyệt, CÓ lịch trả nhưng không có dòng kỳ 1 (phần thực sự
--                                        không quan sát được, 1 hồ sơ trên toàn danh mục)
--
-- Quy tắc kỳ 1: installment_number = 1, bỏ installment_version = 0 (thẻ tín dụng, theo mô tả cột
-- NUM_INSTALMENT_VERSION), lấy ĐÚNG version nhỏ nhất còn lại của hợp đồng (lịch trả gốc). Trước
-- 2026-10-04 code cộng tiền trả qua mọi version và lấy max(installment_amount), ngược với tài liệu.
-- 18.903 hợp đồng có từ 2 version kỳ 1; ở 18.595 hợp đồng trong số đó cùng một lần trả được ghi
-- lặp nguyên ở mỗi version, còn số tiền phải trả bị tách ra giữa các version (tổng installment_amount
-- các version đúng bằng số tiền trả), nên cộng qua version làm phồng tiền đã trả. Một kỳ có thể trả nhiều lần: cộng các lần trả có days_late <= 30 trong version đó trước khi
-- so với installment_amount, dung sai 5%.
-- Mẫu số: hợp đồng có kỳ 1 đến hạn trước thời điểm quan sát ít nhất 30 ngày
-- (days_due <= -30) và installment_amount > 0.
-- Hợp đồng không khớp được previous_application nhận nhãn phân khúc '(không rõ)'.

create or replace table mart.fpd_by_segment as
with first_installment_rows as (
    -- Các dòng kỳ 1, kèm version nhỏ nhất (khác 0) của từng hợp đồng.
    select
        *,
        min(installment_version) over (partition by sk_id_prev) as min_version
    from stg.installments_payments
    where installment_number = 1
      and installment_version > 0          -- version 0 là thẻ tín dụng
),

first_installment as (
    -- Kỳ 1 theo lịch trả gốc (version nhỏ nhất). Một kỳ có thể được trả thành nhiều lần: cộng lại.
    select
        sk_id_prev,
        min(days_due)                                              as days_due,
        max(installment_amount)                                    as installment_amount,
        coalesce(sum(payment_amount) filter (where days_late <= 30), 0) as paid_within_30d,
        max(days_late)                                             as max_days_late
    from first_installment_rows
    where installment_version = min_version
    group by sk_id_prev
),

loans as (
    select
        i.sk_id_prev,
        case when a.sk_id_prev is null then '(không rõ)' else coalesce(a.contract_type, 'Unknown') end as contract_type,
        -- Gom hai kênh quá nhỏ vào 'Khác', GIỐNG HỆT mart.funnel_by_channel và mart.vintage.
        -- Nếu ba mart đặt tên kênh khác nhau thì ghép chúng trên dashboard sẽ khuyết dòng.
        case
            when a.sk_id_prev is null then '(không rõ)'
            when a.channel_type in ('Car dealer', 'Channel of corporate sales') then 'Khác'
            else coalesce(a.channel_type, 'Unknown')
        end                                                                                            as channel_type,
        case when a.sk_id_prev is null then '(không rõ)' else coalesce(a.client_type, 'Unknown') end   as client_type,
        case when a.sk_id_prev is null then '(không rõ)' else coalesce(a.yield_group, 'Unknown') end   as yield_group,
        i.installment_amount,
        i.paid_within_30d,
        -- dung sai 5%: thiếu dưới 5% số tiền phải trả không tính là vỡ nợ kỳ đầu
        i.paid_within_30d < i.installment_amount * 0.95 as is_fpd30,
        -- biến thể theo quy tắc ngày: kỳ 1 trả trễ quá 30 ngày (kể cả nếu đã trả đủ tiền)
        coalesce(i.max_days_late > 30, false)           as is_fpd30_late_rule
    from first_installment i
    left join stg.previous_application a using (sk_id_prev)
    where i.days_due <= -30                 -- đã quan sát đủ 30 ngày sau ngày đến hạn
      and i.installment_amount > 0
),

any_first_installment as (
    -- Sự tồn tại của dòng kỳ 1, KHÔNG lọc installment_version (khác first_installment ở trên,
    -- vốn bỏ version 0 vì mục đích tính FPD30): đây là chỉ báo "hoàn toàn không có dòng kỳ 1".
    select distinct sk_id_prev
    from stg.installments_payments
    where installment_number = 1
),

approved_no_installment as (
    -- Hồ sơ Approved không có dòng kỳ 1 nào, tách theo có hay không có lịch trả (xem đầu file).
    select
        coalesce(a.contract_type, 'Unknown') as contract_type,
        case
            when a.channel_type in ('Car dealer', 'Channel of corporate sales') then 'Khác'
            else coalesce(a.channel_type, 'Unknown')
        end                                  as channel_type,
        coalesce(a.client_type, 'Unknown')   as client_type,
        coalesce(a.yield_group, 'Unknown')   as yield_group,
        count(*) filter (where a.days_first_due is null)     as n_approved_not_activated,
        count(*) filter (where a.days_first_due is not null) as n_approved_scheduled_no_installment
    from stg.previous_application a
    left join any_first_installment f on f.sk_id_prev = a.sk_id_prev
    where a.application_status = 'Approved'
      and f.sk_id_prev is null
      -- Lọc hồ sơ nhập trùng, giống mart.funnel_by_channel, để hai mart đếm cùng một tập hồ sơ.
      and a.is_last_appl_per_contract
      and a.is_last_appl_in_day
    group by 1, 2, 3, 4
),

fpd_agg as (
    select
        contract_type,
        channel_type,
        client_type,
        yield_group,
        count(*)                                            as n_loans,
        count(*) filter (where is_fpd30)                    as n_fpd30,
        count(*) filter (where is_fpd30_late_rule)           as n_fpd30_late_rule
    from loans
    group by contract_type, channel_type, client_type, yield_group
)

select
    coalesce(f.contract_type, n.contract_type) as contract_type,
    coalesce(f.channel_type, n.channel_type)   as channel_type,
    coalesce(f.client_type, n.client_type)     as client_type,
    coalesce(f.yield_group, n.yield_group)     as yield_group,
    coalesce(f.n_loans, 0)                     as n_loans,
    coalesce(f.n_fpd30, 0)                     as n_fpd30,
    coalesce(f.n_fpd30, 0) / nullif(coalesce(f.n_loans, 0), 0)              as fpd30_rate,
    coalesce(f.n_fpd30_late_rule, 0)           as n_fpd30_late_rule,
    coalesce(f.n_fpd30_late_rule, 0) / nullif(coalesce(f.n_loans, 0), 0)    as fpd30_late_rule_rate,
    coalesce(n.n_approved_not_activated, 0)    as n_approved_not_activated,
    coalesce(n.n_approved_scheduled_no_installment, 0) as n_approved_scheduled_no_installment
from fpd_agg f
full outer join approved_no_installment n
    on f.contract_type = n.contract_type
   and f.channel_type = n.channel_type
   and f.client_type = n.client_type
   and f.yield_group = n.yield_group;
