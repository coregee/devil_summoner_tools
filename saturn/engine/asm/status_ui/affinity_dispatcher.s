status_affinity:
    mov.l   =SELECTOR, r0
    mov.b   @r0, r1
    extu.b  r1, r1
    add     #-32, r1
    mov     #66, r0
    cmp/hs  r0, r1
    bt      affinity_fallback
    mov     r1, r3
    mov     #34, r2
    mulu.w  r2, r1
    sts     macl, r2
    mov.l   =SOURCE, r0
    add     r0, r2
    add     #16, r2
    shll2   r3
    shll    r3
    cmp/eq  r2, r4
    bf      affinity_first
    add     #4, r3
affinity_first:
    mov     r3, r0
    mov.l   =TABLE, r3
    mov.l   @(r0,r3), r4
    mov.l   =FONT8_VWF, r0
    jmp     @r0
    nop
affinity_fallback:
    mov.l   =STOCK, r0
    jmp     @r0
    nop
    .pool
    .align 4
