options_compound_glyph:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    mov     r5, r11
    mov.l   @(28,r15), r9
    mov.l   @(32,r15), r12

    mov.w   =COMPOUND_BASE, r1
    sub     r1, r4
    shll2   r4
    shll2   r4
    add     r4, r4
    mov.l   =BITMAPS, r8
    add     r4, r8

    mov.l   =BIT_MASK, r14
    mov     #16, r5
    mul.l   r5, r9
    sts     macl, r3
    add     r12, r3
    mov     r3, r1
    add     #12, r1
    mov.w   @r1, r1
    mov.l   =FRAMEBUFFER, r2
    extu.w  r1, r1
    shll2   r1
    add     r1, r1
    mov     r1, r4
    add     r2, r4
    mov.w   @r3, r1
    mov     r14, r13
    extu.w  r1, r1
    mul.l   r7, r1
    mov     r5, r10
    mov     #15, r5
    sts     macl, r1
    add     r6, r1
    add     r1, r1
    add     r1, r4
    mov     #0, r6

compound_row:
    mov.w   @r8+, r1
    mov     #0, r3
    extu.w  r1, r7
compound_column:
    mov     r13, r1
    and     r7, r1
    tst     r1, r1
    bt/s    next_compound_column
    mov     r3, r2
    add     r3, r2
    mul.l   r10, r9
    add     r4, r2
    mov.w   r11, @r2
    sts     macl, r0
    mov.w   @(r0,r12), r1
    extu.w  r1, r1
    add     r1, r1
    add     r2, r1
    add     #2, r1
    mov.w   r14, @r1
next_compound_column:
    mov     r7, r1
    shll    r1
    extu.w  r1, r7
    mov     r3, r1
    add     #1, r1
    extu.w  r1, r3
    cmp/hi  r5, r3
    bf/s    compound_column
    mov     r13, r1
    mul.l   r10, r9
    sts     macl, r0
    mov.w   @(r0,r12), r1
    extu.w  r1, r1
    add     r1, r1
    add     r1, r4
    mov     r6, r1
    add     #1, r1
    extu.w  r1, r6
    cmp/hi  r5, r6
    bf      compound_row

    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
    .align  4
