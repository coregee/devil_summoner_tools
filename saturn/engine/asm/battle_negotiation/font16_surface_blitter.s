; Draw one proportional FONT16 glyph into the retained battle-dialogue surface.
; Stock surface ABI: r4=base, r5=stride, r6=x, r7=y; glyph, color, and
; shadow color are stacked. The shadow is drawn one pixel down and right.

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
    mov.l   =FONT16_POINTER, r1
    mov.l   @r1, r8
    mov.l   @(28,r15), r1
    extu.w  r1, r4
    shll2   r4
    shll2   r4
    shll    r4
    add     r4, r8
    mov.l   @(32,r15), r11
    extu.b  r11, r11
    mov.l   @(36,r15), r12
    extu.b  r12, r12
    mov     #0, r13

surface_row:
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

surface_shift:
    shll    r1
    dt      r7
    bf      surface_shift
    mov     r3, r2
    shlr2   r2
    add     r2, r2
    add     r10, r2
    mov     #5, r7

surface_column:
    mov     r1, r0
    shlr8   r0
    shlr8   r0
    and     #15, r0
    tst     r0, r0
    bt.s    surface_next
    add     r0, r0
    mov.l   =GLYPH_PATTERN_LUT, r4
    mov.w   @(r0,r4), r4
    mulu.w  r4, r11
    mov.l   =GLYPH_MASK_LUT, r14
    mov.w   @(r0,r14), r14
    mov.w   @r2, r0
    and     r14, r0
    sts     macl, r14
    add     r14, r0
    mov.w   r0, @r2

surface_next:
    shll2   r1
    shll2   r1
    add     #2, r2
    dt      r7
    bf      surface_column

    mov     #15, r1
    cmp/eq  r1, r13
    bt      surface_no_shadow
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

shadow_shift:
    shll    r14
    dt      r7
    bf      shadow_shift
    mov     r2, r1
    shlr2   r1
    add     r1, r1
    add     r10, r1
    mov     #5, r7

shadow_column:
    mov     r14, r0
    shlr8   r0
    shlr8   r0
    and     #15, r0
    tst     r0, r0
    bt.s    shadow_next
    add     r0, r0
    mov.l   =GLYPH_PATTERN_LUT, r4
    mov.w   @(r0,r4), r4
    mulu.w  r4, r12
    sts     macl, r4
    mov.w   @r1, r0
    add     r4, r0
    mov.w   r0, @r1

shadow_next:
    shll2   r14
    shll2   r14
    add     #2, r1
    dt      r7
    bf      shadow_column

surface_no_shadow:
    add     #1, r13
    mov     #16, r1
    cmp/eq  r1, r13
    bf      surface_row
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
