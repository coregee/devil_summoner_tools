font16_from_font8:
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
    mov     r6, r12
    mov     r7, r10
    mov.l   @(32,r15), r11
    mov.l   @(36,r15), r13
    mov.l   @(40,r15), r14
    add     #-4, r15
font16_source_loop:
    tst     r9, r9
    bt      font16_source_done
    mov.b   @r8, r1
    extu.b  r1, r1
    tst     r1, r1
    bt      font16_source_done
    mov     #0xfe, r0
    extu.b  r0, r0
    cmp/hs  r0, r1
    bt      font16_source_done
    bsr     font16_source_width
    nop
    tst     r2, r2
    bt      font16_source_done
    mov.b   @r8, r1
    extu.b  r1, r1
    mov     #63, r0
    cmp/eq  r0, r1
    bt      font16_source_space
    mov     #118, r0
    cmp/hs  r0, r1
    bt      font16_source_high
    add     #-63, r1
    bra     font16_source_mapped
    nop
font16_source_space:
    mov.w   =267, r1
    bra     font16_source_mapped
    nop
font16_source_high:
    mov.w   =205, r0
    cmp/hs  r0, r1
    bf      font16_source_done
    mov.w   =213, r0
    cmp/hs  r0, r1
    bt      font16_source_punctuation
    add     #-106, r1
    add     #-44, r1
    bra     font16_source_mapped
    nop
font16_source_punctuation:
    mov.w   =213, r0
    cmp/eq  r0, r1
    bt      font16_source_hyphen
    mov.w   =214, r0
    cmp/eq  r0, r1
    bt      font16_source_colon
    mov.w   =217, r0
    cmp/eq  r0, r1
    bt      font16_source_apostrophe
    mov.w   =229, r0
    cmp/eq  r0, r1
    bf      font16_source_done
    mov.w   =204, r1
    bra     font16_source_mapped
    nop
font16_source_hyphen:
    mov.w   =173, r1
    bra     font16_source_mapped
    nop
font16_source_colon:
    mov.w   =175, r1
    bra     font16_source_mapped
    nop
font16_source_apostrophe:
    mov.w   =177, r1
font16_source_mapped:
    mov.w   r1, @r15
    mov     r10, r0
    tst     #1, r0
    bt      font16_source_draw
    mov.l   =FONT_BITMAP, r0
    mov     r1, r2
    shll2   r2
    shll2   r2
    shll    r2
    add     r2, r0
    mov     #16, r3
font16_source_shift_right:
    mov.w   @r0, r1
    extu.w  r1, r1
    shlr    r1
    mov.w   r1, @r0
    add     #2, r0
    dt      r3
    bf      font16_source_shift_right
font16_source_draw:
    mov     r15, r4
    mov     #1, r5
    mov     r12, r6
    mov     r10, r7
    mov     r10, r0
    tst     #1, r0
    bt      font16_source_call
    add     #-1, r7
font16_source_call:
    mov.l   r14, @-r15
    mov.l   r13, @-r15
    mov.l   r11, @-r15
    mov.l   =STOCK, r0
    jsr     @r0
    nop
    add     #12, r15
    mov     r10, r0
    tst     #1, r0
    bt      font16_source_advance
    mov.l   =FONT_BITMAP, r0
    mov.w   @r15, r1
    extu.w  r1, r1
    shll2   r1
    shll2   r1
    shll    r1
    add     r1, r0
    mov     #16, r3
font16_source_shift_left:
    mov.w   @r0, r1
    extu.w  r1, r1
    shll    r1
    mov.w   r1, @r0
    add     #2, r0
    dt      r3
    bf      font16_source_shift_left
font16_source_advance:
    mov.b   @r8, r1
    extu.b  r1, r1
    bsr     font16_source_width
    nop
    add     r2, r10
    add     #1, r8
    add     #-1, r9
    bra     font16_source_loop
    nop
font16_source_done:
    add     #4, r15
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

font16_source_width:
    mov     #118, r0
    cmp/hs  r0, r1
    bf      font16_source_width_low
    add     #-128, r1
    bra     font16_source_width_ready
    add     #-22, r1
font16_source_width_low:
    add     #-63, r1
font16_source_width_ready:
    mov.l   =WIDTHS, r0
    mov.b   @(r0,r1), r2
    extu.b  r2, r2
    rts
    nop
    .pool
    .align 4
