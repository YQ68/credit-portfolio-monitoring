-- severity: warn
-- dpd_tolerant (SK_DPD_DEF) là DPD sau dung sai nên kỳ vọng không lớn hơn dpd (SK_DPD).
-- Nếu có nhiều dòng vi phạm, xem lại cách hiểu hai cột (docs/data_notes.md, mục 7).
select sk_id_prev, months_balance, dpd, dpd_tolerant
from core.fct_loan_month
where dpd_tolerant > dpd
