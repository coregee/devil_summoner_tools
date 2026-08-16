; Draw a raw FONT16/FONT12 menu glyph through the shared subpixel blitter and
; return the authored width. Compact low/high FONT16 tables and the FONT12
; table are linked immediately after this source.

event_menu_glyph:
    sts.l   pr, @-r15
    mov.l   r4, @-r15
    mov.l   p_blitter, r1
    jsr     @r1
    nop
    mov.l   @r15+, r3
    mov.l   p_font16, r1
    mov.l   @r1, r1
    mov.l   p_signature_offset, r2
    add     r2, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    cmp/eq  #FONT12_SIGNATURE_VALUE, r0
    bf      font16_lookup
    extu.w  r3, r3
    mov.l   p_font12_limit, r1
    cmp/hs  r1, r3
    bt      stock_width
    mov.l   p_font12_table, r1
    mov     r3, r0
    mov.b   @(r0,r1), r0
    extu.b  r0, r0
    tst     r0, r0
    bf      return
    bra     stock_width
    nop

font16_lookup:
    extu.w  r3, r3
    mov     #LOW_TABLE_LENGTH, r1
    cmp/hs  r1, r3
    bf      low_table
    mov.l   p_high_start, r1
    cmp/hs  r1, r3
    bf      stock_width
    mov     r3, r0
    sub     r1, r0
    mov     #HIGH_TABLE_LENGTH, r1
    cmp/hs  r1, r0
    bt      stock_width
    mov.l   p_high_table, r1
    bra     lookup
    nop

low_table:
    mov     r3, r0
    mov.l   p_low_table, r1

lookup:
    mov.b   @(r0,r1), r0
    extu.b  r0, r0
    tst     r0, r0
    bf      return

stock_width:
    mov     #16, r0

return:
    lds.l   @r15+, pr
    rts
    nop
    nop
    .align 4

p_blitter:          .long BLITTER
p_font16:           .long FONT16_POINTER
p_signature_offset: .long FONT12_SIGNATURE_OFFSET
p_font12_limit:     .long FONT12_CODE_LIMIT
p_font12_table:     .long FONT12_TABLE
p_high_start:       .long HIGH_START
p_high_table:       .long table_data
p_low_table:        .long LOW_TABLE

table_data:
