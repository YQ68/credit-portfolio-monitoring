-- severity: warn
-- dpd (SK_DPD_DEF, định nghĩa chính, có ngưỡng trọng yếu) là DPD sau khi bỏ qua khoản nợ nhỏ, nên
-- kỳ vọng không lớn hơn dpd_no_threshold (SK_DPD, không áp ngưỡng). Nếu có nhiều dòng vi phạm, xem
-- lại cách hiểu hai cột (docs/data_notes.md, mục 7).
select sk_id_prev, months_balance, dpd, dpd_no_threshold
from core.fct_loan_month
where dpd > dpd_no_threshold
