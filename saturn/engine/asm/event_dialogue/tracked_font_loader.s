; Record whether the VM loaded FONT12 or FONT16 and update the special zero
; cell's advance before delegating to the stock loader.

tracked_font_loader:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    mov.l   @(4,r4), r1
    mov.l   =FONT12_TAG, r0
    cmp/eq  r0, r1
    mov.l   =FONT_MODE, r8
    mov     #0, r0
    mov     #16, r1
    bf      store_mode
    mov     #1, r0
    mov     #FONT12_SPACE, r1
store_mode:
    mov.b   r0, @r8
    mov.l   =SPACE_ADVANCE, r8
    mov.w   r1, @r8
    mov.l   =STOCK_LOADER, r0
    jsr     @r0
    nop
    lds.l   @r15+, pr
    rts
    mov.l   @r15+, r8
    .pool
