-- severity: error
-- Đối chiếu số dòng: bảng gộp phải bằng số cặp (hợp đồng, tháng) duy nhất của thẻ
-- cộng với POS sau khi bỏ các hợp đồng đã có trong thẻ. Trả về 1 dòng nếu lệch.
with source_keys as (
    select sk_id_prev, months_balance
    from stg.credit_card_balance

    union  -- union (không all) để bỏ trùng

    select p.sk_id_prev, p.months_balance
    from stg.pos_cash_balance p
    where not exists (
        select 1 from stg.credit_card_balance c where c.sk_id_prev = p.sk_id_prev
    )
),

counts as (
    select
        (select count(*) from source_keys)         as n_expected,
        (select count(*) from core.int_loan_month) as n_actual
)

select * from counts where n_expected <> n_actual
