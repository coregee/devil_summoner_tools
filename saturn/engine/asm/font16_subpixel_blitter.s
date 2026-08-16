; Merge one 16x16 FONT16/FONT12 glyph at an arbitrary pixel X coordinate.
; r4=glyph code, r5=x, r6=y. Runtime state is supplied through pointer symbols.

font16_blit_subpixel:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    mov.l   =FONT16_POINTER, r1
    mov.l   @r1, r8
    extu.w  r4, r4
    shll2   r4
    shll2   r4
    shll    r4
    add     r4, r8
    mov.l   =RIGHT_MARGIN, r1
    mov.w   @r1, r9
    extu.w  r9, r9
    mov.l   =FRAMEBUFFER_POINTER, r1
    mov.l   @r1, r10
    mov.l   =TEXT_COLOR, r1
    mov.b   @r1, r11
    extu.b  r11, r11
    mov.l   =LINE_HEIGHT, r1
    mov.w   @r1, r12
    extu.w  r12, r12
    add     #-1, r12
    extu.w  r5, r5
    extu.w  r6, r6
    mov     #0, r13

font16_row:
    mov     r6, r1
    add     r13, r1
    extu.w  r1, r1
    mulu.w  r9, r1
    sts     macl, r2
    mov     r5, r3
    add     r2, r3
    mov.b   @r8+, r1
    extu.b  r1, r1
    shll8   r1
    mov.b   @r8+, r2
    extu.b  r2, r2
    or      r2, r1
    mov     r3, r0
    and     #3, r0
    mov     #4, r7
    sub     r0, r7
font16_shift_main:
    shll    r1
    dt      r7
    bf      font16_shift_main
    mov     r3, r2
    shlr2   r2
    add     r2, r2
    add     r10, r2
    mov     #5, r7
font16_column_main:
    mov     r1, r0
    shlr8   r0
    shlr8   r0
    and     #0x0f, r0
    tst     r0, r0
    bt.s    font16_next_main
    add     r0, r0
    mov.l   =PATTERN_LUT, r4
    mov.w   @(r0,r4), r4
    mulu.w  r4, r11
    mov.l   =MASK_LUT, r14
    mov.w   @(r0,r14), r14
    mov.w   @r2, r0
    and     r14, r0
    sts     macl, r14
    add     r14, r0
    mov.w   r0, @r2
font16_next_main:
    shll2   r1
    shll2   r1
    add     #2, r2
    dt      r7
    bf      font16_column_main

    cmp/eq  r12, r13
    bt      font16_no_shadow
    mov     r3, r2
    add     r9, r2
    add     #1, r2
    mov     r8, r1
    add     #-2, r1
    mov.b   @r1+, r14
    extu.b  r14, r14
    shll8   r14
    mov.b   @r1, r1
    extu.b  r1, r1
    or      r1, r14
    mov     r2, r0
    and     #3, r0
    mov     #4, r7
    sub     r0, r7
font16_shift_shadow:
    shll    r14
    dt      r7
    bf      font16_shift_shadow
    mov     r2, r1
    shlr2   r1
    add     r1, r1
    add     r10, r1
    mov     #5, r7
font16_column_shadow:
    mov     r14, r0
    shlr8   r0
    shlr8   r0
    and     #0x0f, r0
    tst     r0, r0
    bt.s    font16_next_shadow
    add     r0, r0
    mov.l   =PATTERN_LUT, r4
    mov.w   @(r0,r4), r4
    mov.w   @r1, r0
    add     r4, r0
    mov.w   r0, @r1
font16_next_shadow:
    shll2   r14
    shll2   r14
    add     #2, r1
    dt      r7
    bf      font16_column_shadow

font16_no_shadow:
    add     #1, r13
    mov     #16, r1
    cmp/eq  r1, r13
    bf      font16_row
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
