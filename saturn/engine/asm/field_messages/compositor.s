field_message_compose:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r13

    mov.w   =SCRATCH_CODE, r12
    mov     r12, r0
    shll2   r0
    shll2   r0
    shll    r0
    mov.l   =FONT_BASE, r11
    add     r0, r11

    mov     #0, r0
    mov     r11, r1
    mov.w   =SCRATCH_LONGS, r2
field_clear:
    mov.l   r0, @r1
    add     #4, r1
    dt      r2
    bf      field_clear

    mov.l   =ROW, r1
    mov     #CELL_COUNT, r5
    mov.w   @r13, r0
    extu.w  r0, r0
    mov.w   =PROMPT_CODE, r2
    extu.w  r2, r2
    cmp/eq  r2, r0
    bf      field_codes_ready
    mov.w   r0, @r1
    add     #2, r1
    add     #2, r13
    add     #-1, r5
field_codes_ready:
    mov     r12, r0
    mov     r5, r2
field_codes:
    mov.w   r0, @r1
    add     #2, r1
    add     #1, r0
    dt      r2
    bf      field_codes

    mov     #0, r8
    mov     #MAX_GLYPHS, r10
    mov     #0, r12
    mov.w   @r13, r0
    extu.w  r0, r0
    mov.w   =CURRENCY_YEN_CODE, r1
    extu.w  r1, r1
    cmp/eq  r1, r0
    bf      field_check_mag
    mov     r13, r12
    mov.l   =YEN_PREFIX, r13
    bra     field_glyph
    nop
field_check_mag:
    mov.w   =CURRENCY_MAG_CODE, r1
    extu.w  r1, r1
    cmp/eq  r1, r0
    bf      field_glyph
    mov     r13, r12
    mov.l   =MAG_PREFIX, r13

field_glyph:
    mov.w   @r13+, r0
    extu.w  r0, r14
    tst     r14, r14
    bt      field_source_done

    mov     #2, r1
    cmp/eq  r1, r12
    bf      field_currency_digits
    mov.w   =CURRENCY_YEN_CODE, r1
    extu.w  r1, r1
    cmp/eq  r1, r14
    bf      field_currency_mag
    mov     #4, r12
    bra     field_glyph_ready
    nop
field_currency_mag:
    mov     #5, r12
    bra     field_glyph_ready
    nop

field_currency_digits:
    mov     #4, r1
    cmp/hs  r1, r12
    bf      field_glyph_ready
    mov     #6, r1
    cmp/hs  r1, r12
    bt      field_glyph_ready
    mov     #1, r1
    cmp/hs  r1, r14
    bf      field_currency_suffix
    mov     #11, r1
    cmp/hs  r1, r14
    bt      field_currency_suffix
    bra     field_glyph_ready
    nop

field_source_done:
    tst     r12, r12
    bt      field_done
    mov     #3, r1
    cmp/eq  r1, r12
    bt      field_done
    mov     #6, r1
    cmp/hs  r1, r12
    bf      field_currency_suffix
    mov     r12, r13
    mov     #2, r12
    bra     field_glyph
    nop

field_currency_suffix:
    mov     #4, r1
    cmp/eq  r1, r12
    bf      field_currency_mag_suffix
    mov.l   =YEN_SUFFIX, r13
    bra     field_currency_suffix_ready
    nop
field_currency_mag_suffix:
    mov.l   =MAG_SUFFIX, r13
field_currency_suffix_ready:
    mov     #3, r12
    bra     field_glyph
    nop

field_glyph_ready:
    mov.w   =WIDTH_LIMIT, r1
    cmp/hs  r1, r14
    bt      field_fullwidth
    mov     r14, r0
    mov.l   =WIDTHS, r1
    mov.b   @(r0,r1), r7
    extu.b  r7, r7
    tst     r7, r7
    bf      field_width_ready
field_fullwidth:
    mov     #16, r7
field_width_ready:

    mov     r8, r9
    shlr2   r9
    shlr2   r9
    cmp/hs  r5, r9
    bt      field_done

    mov     r14, r0
    shll2   r0
    shll2   r0
    shll    r0
    mov.l   =FONT_BASE, r6
    add     r0, r6
    mov     r9, r0
    shll2   r0
    shll2   r0
    shll    r0
    mov     r11, r3
    add     r0, r3
    mov     #16, r4
field_row:
    mov.w   @r6+, r0
    extu.w  r0, r0
    swap.w  r0, r0
    mov     r8, r1
    mov     #15, r2
    and     r2, r1
    tst     r1, r1
    bt      field_shifted
field_shift:
    shlr    r0
    dt      r1
    bf      field_shift
field_shifted:
    mov     r0, r14
    mov     r0, r1
    swap.w  r1, r1
    extu.w  r1, r1
    mov.w   @r3, r2
    extu.w  r2, r2
    or      r1, r2
    mov.w   r2, @r3

    mov     r9, r0
    add     #1, r0
    cmp/hs  r5, r0
    bt      field_next_row
    mov     r3, r2
    add     #32, r2
    mov     r14, r1
    extu.w  r1, r1
    mov.w   @r2, r0
    extu.w  r0, r0
    or      r1, r0
    mov.w   r0, @r2
field_next_row:
    add     #2, r3
    dt      r4
    bf      field_row
    add     r7, r8
    dt      r10
    bf      field_glyph

field_done:
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
    .pool
