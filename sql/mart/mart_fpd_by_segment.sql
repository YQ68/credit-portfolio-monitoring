-- M11. FPD30 (first payment default 30, tức kỳ trả đầu tiên chưa trả đủ sau 30 ngày
-- kể từ ngày đến hạn): hợp đồng trả góp mà kỳ trả đầu tiên chưa được trả đủ.
-- Câu hỏi: kênh, sản phẩm nào mang về khách có dấu hiệu rủi ro ngay từ kỳ đầu?
-- Grain: 1 dòng / channel_type / contract_type / client_type / yield_group.
--
-- Lưu tử số, mẫu số dạng số đếm để cộng dồn được khi gom nhóm lớn hơn.
--
-- CANH BAO QUAN TRONG (xem docs/data_notes.md mục 11 và profile_findings.md mục 7):
-- bảng stg.installments_payments gần như chỉ ghi các kỳ ĐÃ TRẢ. Hợp đồng bỏ hẳn
-- kỳ 1 (không trả một đồng nào) thì không có dòng nào trong bảng này, nên biến mất
-- khỏi mẫu số thay vì được tính là vỡ nợ. Vì vậy fpd30_rate trong mart này là
-- CHẶN DƯỚI của FPD30 thật, không phải con số cuối cùng. Cột n_approved_no_installment
-- đo quy mô của vùng mù này: số hồ sơ Approved cùng phân khúc mà không có dòng kỳ 1
-- nào trong installments_payments (toàn danh mục khoảng 77.885 hồ sơ, 7,52%).
--
-- Quy tắc kỳ 1: installment_number = 1, bỏ installment_version = 0 (thẻ tín dụng),
-- lấy version nhỏ nhất còn lại. Một kỳ có thể trả nhiều lần: cộng các lần trả có
-- days_late <= 30 trước khi so với installment_amount, dung sai 5%.
-- Mẫu số: hợp đồng có kỳ 1 đến hạn trước thời điểm quan sát ít nhất 30 ngày
-- (days_due <= -30) và installment_amount > 0.
-- Hợp đồng không khớp được previous_application nhận nhãn phân khúc '(không rõ)'.

create or replace table mart.fpd_by_segment as
with first_installment as (
    -- Kỳ 1 của mỗi hợp đồng trả góp. Một kỳ có thể được trả thành nhiều lần: cộng lại.
    select
        sk_id_prev,
        min(days_due)                                              as days_due,
        max(installment_amount)                                    as installment_amount,
        coalesce(sum(payment_amount) filter (where days_late <= 30), 0) as paid_within_30d,
        max(days_late)                                             as max_days_late
    from stg.installments_payments
    where installment_number = 1
      and installment_version > 0          -- version 0 là thẻ tín dụng
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
    -- vốn bỏ version 0 vì mục đích tính FPD30). Cột n_approved_no_installment là chỉ báo về
    -- việc "hoàn toàn không có dòng kỳ 1 nào được ghi nhận", nên phải tính trên toàn bộ dòng.
    select distinct sk_id_prev
    from stg.installments_payments
    where installment_number = 1
),

approved_no_installment as (
    -- Hồ sơ Approved không có dòng kỳ 1 nào trong installments_payments: rủi ro sớm
    -- không quan sát được (xem cảnh báo đầu file). Đếm theo cùng phân khúc để so sánh.
    select
        coalesce(a.contract_type, 'Unknown') as contract_type,
        case
            when a.channel_type in ('Car dealer', 'Channel of corporate sales') then 'Khác'
            else coalesce(a.channel_type, 'Unknown')
        end                                  as channel_type,
        coalesce(a.client_type, 'Unknown')   as client_type,
        coalesce(a.yield_group, 'Unknown')   as yield_group,
        count(*) as n_approved_no_installment
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
    coalesce(n.n_approved_no_installment, 0)   as n_approved_no_installment
from fpd_agg f
full outer join approved_no_installment n
    on f.contract_type = n.contract_type
   and f.channel_type = n.channel_type
   and f.client_type = n.client_type
   and f.yield_group = n.yield_group;
