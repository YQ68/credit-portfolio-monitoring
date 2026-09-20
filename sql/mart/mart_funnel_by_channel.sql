-- M12. Funnel hồ sơ vay: approval rate và take-up rate.
-- Câu hỏi: kênh nào duyệt nhiều, chuyển đổi tốt và mang lại khoản vay lớn?
-- Grain: 1 dòng / channel_type / contract_type / client_type / yield_group.
--
-- Lưu tử số, mẫu số dạng số đếm để cộng dồn được khi gom nhóm lớn hơn.
-- Không lấy trung bình các cột *_rate: tính lại từ số đếm.
--
-- Kênh 'Car dealer' (452 hồ sơ) và 'Channel of corporate sales' (6.117 hồ sơ) quá nhỏ
-- để báo cáo riêng (xem docs/data_notes.md mục 11), gom chung vào nhãn 'Khác'.
-- 'Canceled' (khách hủy trước khi có quyết định) không nằm trong mẫu số approval rate,
-- nhưng vẫn được đếm riêng ở cột n_canceled để không loại âm thầm.

create or replace table mart.funnel_by_channel as
with applications as (
    select
        case
            when channel_type in ('Car dealer', 'Channel of corporate sales') then 'Khác'
            else coalesce(channel_type, 'Unknown')
        end                                  as channel_type,
        coalesce(contract_type, 'Unknown')  as contract_type,
        coalesce(client_type, 'Unknown')    as client_type,
        coalesce(yield_group, 'Unknown')    as yield_group,
        application_status,
        credit_amount
    from stg.previous_application
    where is_last_appl_per_contract   -- bỏ hồ sơ nhập trùng (docs/data_notes.md, mục 10)
      and is_last_appl_in_day
),

counts as (
    select
        channel_type,
        contract_type,
        client_type,
        yield_group,
        count(*)                                                   as n_applications,
        count(*) filter (where application_status = 'Approved')     as n_approved,
        count(*) filter (where application_status = 'Unused offer') as n_unused_offer,
        count(*) filter (where application_status = 'Refused')      as n_refused,
        count(*) filter (where application_status = 'Canceled')     as n_canceled,
        -- Số tiền chỉ tính trên hồ sơ Approved: đây là khoản vay thực sự giải ngân.
        sum(credit_amount) filter (where application_status = 'Approved')
                                                                    as credit_amount_approved_total,
        median(credit_amount) filter (where application_status = 'Approved')
                                                                    as credit_amount_approved_median
    from applications
    group by channel_type, contract_type, client_type, yield_group
)

select
    *,
    n_approved + n_unused_offer                  as n_offered,   -- được duyệt, dù khách có dùng hay không
    n_approved + n_unused_offer + n_refused      as n_decided,   -- đã có quyết định, mẫu số của approval rate
    (n_approved + n_unused_offer)
        / nullif(n_approved + n_unused_offer + n_refused, 0)   as approval_rate,
    n_approved / nullif(n_approved + n_unused_offer, 0)        as take_up_rate
from counts;
