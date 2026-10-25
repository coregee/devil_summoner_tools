; Adapt either seven-cell staff-test grid to the shared global name pool.
; In: r4 = local name index, r5 = destination row index.
; The stock loops also draw the grid's blank rows (main 10, extra 2-6), so an
; index past the grid's names clears its seven cells by drawing in colour 0.
test_wrapper:
    sts.l   pr, @-r15
    mov     #7, r0
    mulu.w  r0, r5
    sts     macl, r5
    mov     #-1, r6
    mov     #NAME_COUNT, r0
    cmp/hs  r0, r4
    bf      named
    mov     #0, r6
    mov     #0, r4
named:
    add     #INDEX_BASE, r4
    mov     #7, r7
    mov.l   =VDP_BITMAP, r3
    mov.l   =RENDERER, r0
    jsr     @r0
    nop
    lds.l   @r15+, pr
    rts
    nop
    .pool
