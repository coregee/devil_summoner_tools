options_glyph_vwf:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov.w   =PADDING, r1
    extu.w  r1, r1
    cmp/eq  r1, r8
    bt      glyph_padding
    mov.l   =STOCK_GLYPH, r1
    mov     r8, r2
    mov.w   =COMPOUND_BASE, r3
    extu.w  r3, r3
    cmp/hs  r3, r2
    bf      draw_glyph
    mov.w   =COMPOUND_END, r3
    extu.w  r3, r3
    cmp/hs  r3, r2
    bt      draw_glyph
    mov.l   =COMPOUND_GLYPH, r1
draw_glyph:
    mov.l   @(12,r15), r2
    mov.l   @(16,r15), r3
    mov.l   r3, @-r15
    mov.l   r2, @-r15
    jsr     @r1
    nop
    add     #8, r15
    mov     r8, r2
    mov.w   =COMPOUND_BASE, r1
    cmp/hs  r1, r2
    bf      regular_glyph
    mov.w   =COMPOUND_END, r1
    cmp/hs  r1, r2
    bt      japanese_glyph
    mov.w   =COMPOUND_BASE, r1
    sub     r1, r2
    mova    COMPOUND_WIDTHS, r0
    mov.b   @(r0,r2), r0
    extu.b  r0, r0
    bra     glyph_done
    nop
regular_glyph:
    mov.w   =WIDTH_LIMIT, r1
    cmp/hs  r1, r2
    bt      japanese_glyph
    mova    WIDTHS, r0
    mov.b   @(r0,r2), r0
    extu.b  r0, r0
    tst     r0, r0
    bf      glyph_done
japanese_glyph:
    mov     #16, r0
    bra     glyph_done
    nop
glyph_padding:
    mov     #0, r0
glyph_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
    .align  4
