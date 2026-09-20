-- Ảnh chụp cơ cấu nhóm quá hạn của danh mục đang mở, tại tháng gần nhất trong dữ
-- liệu (months_balance = -1, đây là tháng tương đối chứ KHÔNG phải tháng lịch).
--
-- Mã chỉ tiêu: M02 (DPD bucket), M06 (tỷ lệ 30+ coincident).
-- Grain: 1 dòng = sản phẩm x kênh x bucket.
--
-- CẢNH BÁO KHI GOM NHÓM: chỉ được cộng n_loans và exposure rồi chia lại.
--
-- Bảng này sinh ra để trang 1 của báo cáo Power BI bám đúng trang 1 của
-- dashboard/index.html, vốn đọc thẳng core.fct_loan_month chứ không qua mart.
--
-- QUY ƯỚC NHÃN PHÂN KHÚC: dùng y hệt mart.vintage, mart.fpd_by_segment và
-- mart.roll_rate, nếu không thì Dim Channel/Dim Product trong model Power BI sẽ
-- tách cùng một kênh thành nhiều thành viên khác nhau. Ba nhãn KHÁC NGHĨA nhau:
--   '(không rõ)' hợp đồng không khớp previous_application, mọi thuộc tính phân
--                khúc đều không biết được
--   'Unknown'    có hồ sơ nhưng chính cột đó null
--   'Khác'       hai kênh quá nhỏ (Car dealer, Channel of corporate sales)
create or replace table mart.portfolio_snapshot as
with loans as (
    select
        d.sk_id_prev,
        d.source,
        case when d.has_application then coalesce(d.contract_type, 'Unknown') else '(không rõ)' end as contract_type,
        case
            when not d.has_application                                         then '(không rõ)'
            when d.channel_type is null                                        then 'Unknown'
            when d.channel_type in ('Car dealer', 'Channel of corporate sales') then 'Khác'
            else d.channel_type
        end                                                                                        as channel_type
    from core.dim_loan d
)
select
    l.contract_type,
    l.channel_type,
    f.dpd_bucket,
    f.dpd_bucket_order,
    count(*)                                          as n_loans,
    sum(f.exposure_proxy)                             as exposure,
    count(*) filter (where f.is_30_plus)              as n_30_plus,
    sum(f.exposure_proxy) filter (where f.is_30_plus) as exposure_30_plus
from core.fct_loan_month f
join loans l
  on f.sk_id_prev = l.sk_id_prev
 and f.source     = l.source
where f.is_open
  and f.months_balance = -1
group by 1, 2, 3, 4
order by 1, 2, 4
