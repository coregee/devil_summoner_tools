; Adapt either seven-cell staff-test grid to the shared global name pool.
; In: r4 = local name index, r5 = destination row index.
test_wrapper:
    sts.l   pr, @-r15
    mov     #7, r0
    mulu.w  r0, r5
    sts     macl, r5
    add     #INDEX_BASE, r4
    mov     #-1, r6
    mov     #7, r7
    mov.l   =VDP_BITMAP, r3
    mov.l   =RENDERER, r0
    jsr     @r0
    nop
    lds.l   @r15+, pr
    rts
    nop
    .pool
