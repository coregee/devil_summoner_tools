; Draw one FONT12/FONT16 glyph onto a caller-owned 4bpp surface at an exact
; pixel x-coordinate.  The caller supplies base, stride, x, and y in r4-r7,
; followed by glyph and palette colour on the stack.

font16_surface_blitter:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    mov     r4, r10
    mov     r5, r9
    mov     r6, r5
    mov     r7, r6
    mov.l   =FONT12, r1
    mov.l   @r1, r8
    mov.l   @(28,r15), r1
    extu.w  r1, r4
    shll2   r4
    shll2   r4
    shll    r4
    add     r4, r8
    mov.l   @(32,r15), r11
    extu.b  r11, r11
    mov     #0, r13

row_loop:
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

shift_row:
    shll    r1
    dt      r7
    bf      shift_row

    mov     r3, r2
    shlr2   r2
    add     r2, r2
    add     r10, r2
    mov     #5, r7

column_loop:
    mov     r1, r0
    shlr8   r0
    shlr8   r0
    and     #15, r0
    tst     r0, r0
    bt.s    next_column
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

next_column:
    shll2   r1
    shll2   r1
    add     #2, r2
    dt      r7
    bf      column_loop

    add     #1, r13
    mov     #16, r1
    cmp/eq  r1, r13
    bf      row_loop
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    nop
    .pool
