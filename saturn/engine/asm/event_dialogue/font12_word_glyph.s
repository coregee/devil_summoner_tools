; Adapt a stock FONT12 word-glyph call to the exact-pixel surface renderer and
; return the authored advance. Unmapped/Japanese glyphs retain stock width.

font12_word_glyph_vwf:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    sts.l   pr, @-r15
    mov.l   @(12,r15), r8
    mov.l   @(16,r15), r9
    mov.l   r9, @-r15
    mov.l   r8, @-r15
    mov.l   =SURFACE_BLITTER, r0
    jsr     @r0
    nop
    add     #8, r15
    mov     #-1, r1
    extu.b  r1, r1
    cmp/hi  r1, r8
    bt      stock_width
    mov.l   =WIDTHS, r1
    mov     r8, r0
    mov.b   @(r0,r1), r0
    extu.b  r0, r0
    tst     r0, r0
    bf      return
stock_width:
    mov     #12, r0
return:
    lds.l   @r15+, pr
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
