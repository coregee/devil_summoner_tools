; Wrap the stock FONT16 blitter and return the generated proportional advance.
; A 0xffff padding word consumes no horizontal space.
text_vwf:
    mov     r4, r0
    extu.w  r0, r0
    mov.w   =PADDING_CODE, r1
    extu.w  r1, r1
    cmp/eq  r1, r0
    bt      tv_padding
    mov.l   =text_scratch, r0
    mov.l   r4, @r0
    sts     pr, r1
    mov.l   r1, @(4,r0)
    mov.l   =ORIGINAL_BLITTER, r0
    jsr     @r0
    nop

    mov.l   =text_scratch, r0
    mov.l   @(4,r0), r1
    lds     r1, pr
    mov.l   @r0, r3
    extu.w  r3, r3
    mov.l   =WIDTH_LIMIT, r1
    cmp/hs  r1, r3
    bt      tv_stock
    mov     r3, r0
    mov.l   =width_table, r1
    mov.b   @(r0,r1), r0
    extu.b  r0, r0
    tst     r0, r0
    bf      tv_return
tv_stock:
    mov     #16, r0
tv_return:
    rts
    nop
tv_padding:
    rts
    mov     #0, r0
    .pool
