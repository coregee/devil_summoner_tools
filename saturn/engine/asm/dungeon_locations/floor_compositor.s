    .align  4
    .pool

prepare_label:
    mov.l   =BOTTOM_ADDR, r9
    mov     #0, r0
    mov     #32, r10
prepare_clear_bottom:
    mov.l   r0, @r9
    add     #4, r9
    dt      r10
    bf      prepare_clear_bottom
    mov     #-1, r1
    mov.l   =CURRENT_APPEND, r2
    mov.b   r1, @r2
    mov.w   @r4, r0
    extu.w  r0, r0
    mov.w   =LABEL_BASE, r1
    cmp/hs  r1, r0
    bf      prepare_legacy
    sub     r1, r0
    mov.w   =LABEL_COUNT, r1
    cmp/hs  r1, r0
    bt      prepare_legacy
    mov     r0, r2
    mov.l   =APPEND_OFFSETS, r0
    mov.b   @(r0,r2), r0
    mov.l   =CURRENT_APPEND, r1
    mov.b   r0, @r1
    mov     r2, r0
    shll8   r0
    mov.l   =BITMAPS, r8
    add     r0, r8
    mov.l   =TOP_ADDR, r9
    mov     #64, r10
prepare_copy:
    mov.l   @r8+, r0
    mov.l   r0, @r9
    add     #4, r9
    dt      r10
    bf      prepare_copy
    rts
    mov     #1, r0
prepare_legacy:
    rts
    mov     #0, r0
    .align  4
    .pool

floor_compose:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    add     #-8, r15
    mov     r15, r13
    mov     #0, r10
    mov     #0, r12
    cmp/pz  r4
    bt      floor_abs_ready
    mov     #1, r12
    neg     r4, r4
floor_abs_ready:
    tst     r4, r4
    bt      floor_formatted
    mov     #0, r8
floor_tens:
    mov     #10, r0
    cmp/hs  r0, r4
    bf      floor_digits
    add     #-10, r4
    add     #1, r8
    bra     floor_tens
    nop
floor_digits:
    tst     r12, r12
    bt      floor_no_negative_prefix
    mov.w   =CODE_NEGATIVE_PREFIX, r0
    mov.w   r0, @r13
    add     #2, r13
    add     #1, r10
floor_no_negative_prefix:
    tst     r8, r8
    bt      floor_ones
    mov.w   =CODE_0, r0
    add     r8, r0
    mov.w   r0, @r13
    add     #2, r13
    add     #1, r10
floor_ones:
    mov.w   =CODE_0, r0
    add     r4, r0
    mov.w   r0, @r13
    add     #2, r13
    add     #1, r10
    mov.w   =CODE_SUFFIX, r0
    mov.w   r0, @r13
    add     #1, r10
floor_formatted:
    bra     floor_format_ready
    nop
    .align  4
    .pool
floor_format_ready:
    mov.l   =BOTTOM_ADDR, r11
    mov     #0, r14
    mov     r15, r13
    mov     r10, r9
floor_measure:
    tst     r9, r9
    bt      floor_measured
    mov.w   @r13+, r2
    extu.w  r2, r2
    mova    WIDTHS, r0
    mov.b   @(r0,r2), r0
    extu.b  r0, r0
    add     r0, r14
    dt      r9
    bra     floor_measure
    nop
floor_measured:
    mov.l   =CURRENT_APPEND, r0
    mov.b   @r0, r8
    extu.b  r8, r8
    mov     #-1, r0
    extu.b  r0, r0
    cmp/eq  r0, r8
    bf      floor_positioned
    mov     #64, r8
    sub     r14, r8
floor_positioned:
    mov     r15, r13
    mov     r10, r9
floor_glyph:
    tst     r9, r9
    bt      floor_done
    mov.w   @r13+, r14
    extu.w  r14, r14
    mova    WIDTHS, r0
    mov.b   @(r0,r14), r7
    extu.b  r7, r7
    mov     r8, r5
    shlr2   r5
    shlr2   r5
    mov     r14, r0
    shll2   r0
    shll2   r0
    shll    r0
    mov.l   =FONT_BASE, r6
    add     r0, r6
    mov     r5, r0
    shll2   r0
    shll2   r0
    shll    r0
    mov     r11, r3
    add     r0, r3
    mov     #16, r4
floor_row:
    mov.w   @r6+, r0
    extu.w  r0, r0
    swap.w  r0, r0
    mov     r8, r1
    mov     #15, r2
    and     r2, r1
    tst     r1, r1
    bt      floor_shifted
floor_shift:
    shlr    r0
    dt      r1
    bf      floor_shift
floor_shifted:
    mov     r0, r14
    mov     r0, r1
    swap.w  r1, r1
    extu.w  r1, r1
    mov.w   @r3, r2
    extu.w  r2, r2
    or      r1, r2
    mov.w   r2, @r3
    mov     #3, r0
    cmp/eq  r0, r5
    bt      floor_next_row
    mov     r3, r2
    add     #32, r2
    mov     r14, r1
    extu.w  r1, r1
    mov.w   @r2, r0
    extu.w  r0, r0
    or      r1, r0
    mov.w   r0, @r2
floor_next_row:
    add     #2, r3
    dt      r4
    bf      floor_row
    add     r7, r8
    dt      r9
    bra     floor_glyph
    nop
floor_done:
    add     #8, r15
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    rts
    nop
    .align  4
    .pool
TOP_CODE_ROW:
    .word   TOP_CODE, TOP_CODE+1, TOP_CODE+2, TOP_CODE+3
FLOOR_CODE_ROW:
    .word   BOTTOM_CODE, BOTTOM_CODE+1, BOTTOM_CODE+2, BOTTOM_CODE+3
    .align  4
CURRENT_APPEND:
    .byte   255
    .align  4
    .pool
