status_font16_vwf:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r6, r9
    mov     r7, r10
    mov.l   @(32,r15), r11
    mov.l   @(36,r15), r12
    mov.l   @(40,r15), r13
    mov.l   =WIDTHS, r14
font16_loop:
    mov.w   @r8, r1
    extu.w  r1, r1
    mov.w   =END_MASK, r0
    tst     r0, r1
    bf      font16_done
    mov     r10, r0
    tst     #1, r0
    bt      font16_draw
    mov.l   =FONT_BITMAP, r0
    mov     r1, r2
    shll2   r2
    shll2   r2
    shll    r2
    add     r2, r0
    mov     #16, r3
font16_shift_right:
    mov.w   @r0, r1
    extu.w  r1, r1
    shlr    r1
    mov.w   r1, @r0
    add     #2, r0
    dt      r3
    bf      font16_shift_right
font16_draw:
    mov     r8, r4
    mov     #1, r5
    mov     r9, r6
    mov     r10, r7
    mov     r10, r0
    tst     #1, r0
    bt      font16_call
    add     #-1, r7
font16_call:
    mov.l   r13, @-r15
    mov.l   r12, @-r15
    mov.l   r11, @-r15
    mov.l   =STOCK, r0
    jsr     @r0
    nop
    add     #12, r15
    mov     r10, r0
    tst     #1, r0
    bt      font16_advance
    mov.l   =FONT_BITMAP, r0
    mov.w   @r8, r1
    extu.w  r1, r1
    shll2   r1
    shll2   r1
    shll    r1
    add     r1, r0
    mov     #16, r3
font16_shift_left:
    mov.w   @r0, r1
    extu.w  r1, r1
    shll    r1
    mov.w   r1, @r0
    add     #2, r0
    dt      r3
    bf      font16_shift_left
font16_advance:
    mov.w   @r8, r1
    extu.w  r1, r1
    mov     r1, r0
    mov.b   @(r0,r14), r2
    extu.b  r2, r2
    add     r2, r10
    bra     font16_loop
    add     #2, r8
font16_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
    .align 4
