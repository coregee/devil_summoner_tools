compact_draw:
    mov.w   @r4, r0
    extu.w  r0, r0
    mov.w   =COMPACT_MARKER, r1
    tst     r1, r0
    bf      compact_begin
    mov.l   =ORIGINAL_DRAW, r1
    jmp     @r1
    nop
    .pool

compact_begin:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r5, r9
    mov     r6, r10
    mov     r7, r11
    mov     r4, r13

    mov.l   =FONT_BASE, r4
    mov.l   =SAVED_FONT, r5
    mov     r10, r6
    shll2   r6
    shll    r6
compact_save_font:
    mov.l   @r4+, r0
    mov.l   r0, @r5
    add     #4, r5
    dt      r6
    bf      compact_save_font

    mov.l   =FONT_BASE, r4
    mov     r10, r6
    shll2   r6
    shll    r6
    mov     #0, r0
compact_clear_font:
    mov.l   r0, @r4
    add     #4, r4
    dt      r6
    bf      compact_clear_font

    mov.w   @r13+, r12
    extu.w  r12, r12
    shll    r12
    mov     #15, r14
    mov     #0, r8

compact_token:
    bsr     compact_read5
    nop
    tst     r0, r0
    bt      compact_render
    mov     #26, r1
    cmp/hi  r1, r0
    bt      compact_control
    add     #96, r0
    bsr     compact_emit
    nop
    bra     compact_token
    nop

compact_control:
    mov     #27, r1
    cmp/eq  r1, r0
    bf      compact_uppercase
    mov     #32, r0
    bsr     compact_emit
    nop
    bra     compact_token
    nop

compact_uppercase:
    mov     #28, r1
    cmp/eq  r1, r0
    bf      compact_extended
    bsr     compact_read5
    nop
    add     #64, r0
    bsr     compact_emit
    nop
    bra     compact_token
    nop

compact_extended:
    mov     #29, r1
    cmp/eq  r1, r0
    bf      compact_dictionary
    bsr     compact_read5
    nop
    mov.l   =EXTENDED_TABLE, r1
    mov.b   @(r0,r1), r0
    extu.b  r0, r0
    bsr     compact_emit
    nop
    bra     compact_token
    nop

compact_dictionary:
    mov     r0, r2
    bsr     compact_read5
    nop
    mov     #31, r1
    cmp/eq  r1, r2
    bf      compact_dictionary_index
    add     #32, r0
compact_dictionary_index:
    shll    r0
    mov.l   =DICTIONARY_OFFSETS, r1
    mov.w   @(r0,r1), r0
    extu.w  r0, r0
    mov.l   =DICTIONARY_POOL, r4
    add     r0, r4
compact_dictionary_character:
    mov.b   @r4+, r0
    extu.b  r0, r0
    tst     r0, r0
    bt      compact_token
    mov.l   r4, @-r15
    bsr     compact_emit
    nop
    mov.l   @r15+, r4
    bra     compact_dictionary_character
    nop

compact_render:
    mov.l   =ROW_CODES, r4
    mov     #0, r0
    mov     r10, r6
compact_row_codes:
    mov.w   r0, @r4
    add     #2, r4
    add     #1, r0
    dt      r6
    bf      compact_row_codes

    mov     r15, r14
    add     #32, r14
    mov.l   @(32,r14), r0
    mov.l   r0, @-r15
    mov.l   @(28,r14), r0
    mov.l   r0, @-r15
    mov.l   @(24,r14), r0
    mov.l   r0, @-r15
    mov.l   @(20,r14), r0
    mov.l   r0, @-r15
    mov.l   @(16,r14), r0
    mov.l   r0, @-r15
    mov.l   @(12,r14), r0
    mov.l   r0, @-r15
    mov.l   @(8,r14), r0
    mov.l   r0, @-r15
    mov.l   @(4,r14), r0
    mov.l   r0, @-r15
    mov.l   @r14, r0
    mov.l   r0, @-r15
    mov.l   =ROW_CODES, r4
    mov     r9, r5
    mov     r10, r6
    mov     r11, r7
    mov.l   =ORIGINAL_DRAW, r1
    jsr     @r1
    nop
    add     #36, r15
    mov.l   r0, @-r15

    mov.l   =SAVED_FONT, r4
    mov.l   =FONT_BASE, r5
    mov     r10, r6
    shll2   r6
    shll    r6
compact_restore_font:
    mov.l   @r4+, r0
    mov.l   r0, @r5
    add     #4, r5
    dt      r6
    bf      compact_restore_font

    mov.l   @r15+, r0
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

compact_read5:
    mov     #0, r0
    mov     #5, r1
compact_read5_bit:
    shll    r12
    rotcl   r0
    add     #-1, r14
    tst     r14, r14
    bf      compact_read5_next
    mov.w   @r13+, r12
    extu.w  r12, r12
    mov     #16, r14
compact_read5_next:
    dt      r1
    bf      compact_read5_bit
    rts
    nop

compact_emit:
    add     #-32, r0
    mov     r0, r1
    shll2   r0
    shll    r0
    mov.l   =FONT_BITMAPS, r3
    add     r0, r3
    mov     r1, r0
    mov.l   =FONT_WIDTHS, r2
    mov.b   @(r0,r2), r7
    extu.b  r7, r7

    mov     r8, r2
    shlr2   r2
    shlr2   r2
    mov     r2, r0
    shll2   r0
    shll2   r0
    shll    r0
    mov.l   =FONT_BASE, r2
    add     r0, r2
    mov     r8, r6
    mov     #15, r0
    and     r0, r6
    mov     #8, r5
compact_emit_row:
    mov.b   @r3+, r0
    extu.b  r0, r0
    shll16  r0
    shll8   r0
    mov     r6, r4
    tst     r4, r4
    bt      compact_emit_shifted
compact_emit_shift:
    shlr    r0
    dt      r4
    bf      compact_emit_shift
compact_emit_shifted:
    swap.w  r0, r1
    extu.w  r1, r1
    mov.w   @r2, r4
    extu.w  r4, r4
    or      r1, r4
    mov.w   r4, @r2
    add     #2, r2
    mov.w   @r2, r4
    extu.w  r4, r4
    or      r1, r4
    mov.w   r4, @r2
    add     #-2, r2

    extu.w  r0, r1
    tst     r1, r1
    bt      compact_emit_next
    mov     r2, r4
    add     #32, r4
    mov.w   @r4, r0
    extu.w  r0, r0
    or      r1, r0
    mov.w   r0, @r4
    add     #2, r4
    mov.w   @r4, r0
    extu.w  r0, r0
    or      r1, r0
    mov.w   r0, @r4
compact_emit_next:
    add     #4, r2
    dt      r5
    bf      compact_emit_row
    add     r7, r8
    rts
    nop
    .pool

compact_stat_draw:
    mov.l   =STAT_SOURCE_CODES, r1
    mov     #0, r2
    mov     #6, r3
compact_stat_find:
    mov.w   @r1+, r0
    extu.w  r0, r0
    cmp/eq  r4, r0
    bt      compact_stat_begin
    add     #1, r2
    dt      r3
    bf      compact_stat_find
    mov.l   =ORIGINAL_GLYPH_DRAW, r1
    jmp     @r1
    nop
    .pool

compact_stat_begin:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r5, r9
    mov     r6, r10
    mov     r7, r11

    mov.l   =FONT_BASE, r4
    mov.l   =SAVED_FONT, r5
    mov     #8, r6
compact_stat_save_font:
    mov.l   @r4+, r0
    mov.l   r0, @r5
    add     #4, r5
    dt      r6
    bf      compact_stat_save_font

    mov     r2, r0
    shll2   r0
    shll2   r0
    shll    r0
    mov.l   =STAT_BITMAPS, r4
    add     r0, r4
    mov.l   =FONT_BASE, r5
    mov     #8, r6
compact_stat_install_font:
    mov.l   @r4+, r0
    mov.l   r0, @r5
    add     #4, r5
    dt      r6
    bf      compact_stat_install_font

    mov     r15, r14
    add     #32, r14
    mov.l   @(4,r14), r0
    mov.l   r0, @-r15
    mov.l   @r14, r0
    mov.l   r0, @-r15
    mov     #0, r4
    mov     r9, r5
    mov     r10, r6
    mov     r11, r7
    mov.l   =ORIGINAL_GLYPH_DRAW, r1
    jsr     @r1
    nop
    add     #8, r15
    mov.l   r0, @-r15

    mov.l   =SAVED_FONT, r4
    mov.l   =FONT_BASE, r5
    mov     #8, r6
compact_stat_restore_font:
    mov.l   @r4+, r0
    mov.l   r0, @r5
    add     #4, r5
    dt      r6
    bf      compact_stat_restore_font

    mov.l   @r15+, r0
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
