-- severity: error
-- Nhãn end_state phải đúng định nghĩa trong core/dim_loan.sql, đặc biệt nhãn 'closed_inferred'
-- (thêm 2026-10-04): chỉ gán khi lịch sử dừng trước tháng -1, trạng thái cuối không phải Completed
-- và hồ sơ có DAYS_TERMINATION. Mart vintage coi 'closed_inferred' như 'closed', nên gán sai nhãn
-- là sai mẫu số vintage.
select sk_id_prev, first_open_month, last_status, last_observed_month, days_termination, end_state
from core.dim_loan
where end_state is null
   or end_state not in ('never_open', 'closed', 'censored', 'closed_inferred', 'unknown')
   or (end_state = 'never_open'      and first_open_month is not null)
   or (end_state = 'closed'          and last_status <> 'Completed')
   or (end_state = 'censored'        and last_observed_month <> -1)
   or (end_state = 'closed_inferred' and (last_status = 'Completed' or last_observed_month >= -1
                                          or days_termination is null or first_open_month is null))
   or (end_state = 'unknown'         and (last_status = 'Completed' or last_observed_month >= -1
                                          or days_termination is not null or first_open_month is null))
