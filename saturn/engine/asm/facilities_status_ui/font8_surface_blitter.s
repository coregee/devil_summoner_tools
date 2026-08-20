; Draw an 8x8 FONT8 glyph onto a caller-owned 4bpp surface at an exact pixel
; x-coordinate.  Unlike the framebuffer-oriented shared FONT8 renderer, this
; surface contract does not add a palette-1 shadow.

font8_blit_surface_pixel_x:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r5, r9
    shlr    r9
    mov     r6, r10
    mov     r7, r0
    mulu.w  r9, r0
    sts     macl, r14
    add     r14, r8
    mov.l   @(36,r15), r12
    mov     #15, r0
    and     r0, r12
    mov.l   @(32,r15), r11
    extu.w  r11, r11
    shll2   r11
    shll    r11
    mov.l   =FONT8, r0
    add     r0, r11
    mov     #0, r13

surface_row:
    mulu.w  r9, r13
    sts     macl, r14
    add     r8, r14
    mov.b   @r11+, r6
    extu.b  r6, r6
    mov     #0, r7
    mov     r10, r3

surface_col:
    mov     #-128, r1
    tst     r1, r6
    bt      surface_advance
    mov     r14, r1
    mov     r3, r2
    mov     r12, r0
    bsr     set_surface_4bpp_pixel
    nop

surface_advance:
    shll    r6
    extu.b  r6, r6
    add     #1, r3
    add     #1, r7
    mov     #8, r0
    cmp/hs  r0, r7
    bf      surface_col
    add     #1, r13
    mov     #8, r0
    cmp/hs  r0, r13
    bf      surface_row
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

set_surface_4bpp_pixel:
    mov     #1, r5
    tst     r5, r2
    bt      surface_even
    shlr    r2
    add     r2, r1
    mov.b   @r1, r2
    extu.b  r2, r2
    mov     #-16, r5
    and     r5, r2
    or      r0, r2
    rts
    mov.b   r2, @r1

surface_even:
    shlr    r2
    add     r2, r1
    mov.b   @r1, r2
    extu.b  r2, r2
    mov     #15, r5
    and     r5, r2
    shll2   r0
    shll2   r0
    or      r0, r2
    rts
    mov.b   r2, @r1
    .pool

