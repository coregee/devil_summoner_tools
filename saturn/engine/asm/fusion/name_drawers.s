; Fusion's list, preview, chart, guide, and help name consumers share this
; bounded drawer family.  Names and widths are linked from authored assets;
; the executable contains only surface geometry and stock fallbacks.

fusion_race_vwf:
    mov.l   @r15, r1
    extu.w  r1, r1
    mov.l   =RACE_BASE, r0
    sub     r0, r1
    mov     #RACE_COUNT, r0
    cmp/hs  r0, r1
    bf      race_supported
    mov.l   =RACE_STOCK, r0
    jmp     @r0
    nop
race_supported:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    add     #-8, r15
    shll    r1
    mov.l   =RACE_OFFSETS, r0
    add     r1, r0
    mov.w   @r0, r0
    extu.w  r0, r0
    mov.l   =RACE_POOL, r8
    add     r0, r8
    mov     #RACE_MAX_WIDTH, r2
    bra     common_setup
    mov     #2, r3

fusion_chart_race_font8:
    mov.l   @r15, r1
    extu.w  r1, r1
    mov.l   =RACE_BASE, r0
    sub     r0, r1
    mov     #RACE_COUNT, r0
    cmp/hs  r0, r1
    bf      chart_race_supported
    mov.l   =RACE_STOCK, r0
    jmp     @r0
    nop
chart_race_supported:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    add     #-8, r15
    mov.l   =CHART_RACE_WIDTHS, r2
    mov     r1, r0
    mov.b   @(r0,r2), r2
    extu.b  r2, r2
    mov     #CHART_CELL_WIDTH, r0
    sub     r2, r0
    shlr    r0
    add     r0, r6
    shll    r1
    mov.l   =TABLE_RACE_OFFSETS, r0
    add     r1, r0
    mov.w   @r0, r0
    extu.w  r0, r0
    mov.l   =TABLE_RACE_POOL, r8
    add     r0, r8
    bra     common_setup
    mov     #TABLE_FONT8_MODE, r3

fusion_table_race_font8:
    mov.l   @r15, r1
    extu.w  r1, r1
    mov     #RACE_COUNT, r0
    cmp/hs  r0, r1
    bf      table_race_supported
table_race_fallback:
    mov.l   =TABLE_RACE_STOCK, r0
    jmp     @r0
    nop
table_race_supported:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    add     #-8, r15
    shll    r1
    mov.l   =TABLE_RACE_OFFSETS, r0
    add     r1, r0
    mov.w   @r0, r0
    extu.w  r0, r0
    mov.l   =TABLE_RACE_POOL, r8
    add     r0, r8
    mov     #TABLE_RACE_MAX_WIDTH, r2
    bra     common_setup
    mov     #TABLE_FONT8_MODE, r3

fusion_table_demon_font8:
    bra     demon_entry
    mov     #TABLE_FONT8_MODE, r3
fusion_demon_name_vwf:
    bra     demon_entry
    mov     #0, r3
fusion_demon_preview_vwf:
    mov     #2, r3
demon_entry:
    mov.l   @r15, r1
    extu.w  r1, r1
    add     #-1, r1
    mov.l   =DVL_COUNT, r0
    cmp/hs  r0, r1
    bf      demon_supported
    mov.l   =DEMON_STOCK, r0
    jmp     @r0
    nop
demon_supported:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    add     #-8, r15
    shll    r1
    mov.l   =DVL_OFFSETS, r0
    add     r1, r0
    mov.w   @r0, r0
    extu.w  r0, r0
    mov.l   =DVL_POOL, r8
    add     r0, r8
    mov     #NAME_MAX_WIDTH, r2
    bra     common_setup
    nop

fusion_character_name_vwf:
    mov.l   @r15, r0
    extu.w  r0, r0
    mov.l   =PLAYER_ID, r1
    cmp/eq  r1, r0
    bt      character_player
    ; Actor records retain the selector's 0x8000+n key. Match the stock
    ; CHARNAME drawer by indexing its low byte after preserving 0x8000 as the
    ; live player-codename sentinel.
    extu.b  r0, r0
    mov     #CHAR_COUNT, r1
    cmp/hs  r1, r0
    bf      character_supported
    mov.l   =CHARACTER_STOCK, r0
    jmp     @r0
    nop
character_supported:
    mov     r0, r1
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    add     #-8, r15
    shll    r1
    mov.l   =CHAR_OFFSETS, r0
    add     r1, r0
    mov.w   @r0, r0
    extu.w  r0, r0
    mov.l   =CHAR_POOL, r8
    add     r0, r8
    mov     #NAME_MAX_WIDTH, r2
    bra     byte_setup
    nop

character_player:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    add     #-8, r15
    mov.l   =PLAYER_CODENAME, r8
    mov     #NAME_MAX_WIDTH, r2
    bra     common_setup
    mov     #1, r3

byte_setup:
    mov     #0, r3
common_setup:
    mov     r4, r9
    mov     r5, r10
    mov     r6, r11
    mov     r7, r12
    mov.l   @(44,r15), r13
    mov.l   r3, @r15
    mov     r11, r0
    add     r2, r0
    mov.l   r0, @(4,r15)
    mov     r3, r0
    tst     #1, r0
    bf      word_start
    mov     #32, r14
byte_loop:
    mov.b   @r8+, r2
    extu.b  r2, r2
    mov     #-1, r0
    extu.b  r0, r0
    cmp/eq  r0, r2
    bt      draw_done
    bra     draw_glyph
    nop
word_start:
    mov     #8, r14
word_loop:
    mov.w   @r8, r2
    add     #2, r8
    extu.w  r2, r2
    mov.l   =WORD_TERMINATOR, r0
    cmp/eq  r0, r2
    bt      draw_done
    mov.l   =FONT16_SPACE, r0
    cmp/eq  r0, r2
    bf      draw_glyph
    mov     #0, r2
draw_glyph:
    mov.l   @r15, r3
    mov     #TABLE_FONT8_MODE, r0
    cmp/eq  r0, r3
    bf      standard_width
    mov.l   =FONT8_CODE_MAP, r1
    mov     r2, r0
    mov.b   @(r0,r1), r2
    extu.b  r2, r2
font8_width:
    mov.l   =FONT8_WIDTHS, r1
    bra     width_ready
    nop
standard_width:
    mov.l   =WIDTHS, r1
width_ready:
    mov     r2, r0
    mov.b   @(r0,r1), r1
    extu.b  r1, r1
    tst     r1, r1
    bt      draw_done
    mov     #TABLE_FONT8_MODE, r0
    cmp/eq  r0, r3
    bf      advance_ready
    mov     #FONT8_SPACE, r0
    cmp/eq  r0, r2
    bt      advance_ready
    add     #1, r1
advance_ready:
    mov     r11, r6
    add     r1, r11
    mov.l   @(4,r15), r0
    cmp/hi  r0, r11
    bt      draw_done
    mov     r9, r4
    mov     r10, r5
    mov     r12, r7
    mov.l   r13, @-r15
    mov.l   r2, @-r15
    mov.l   @(8,r15), r3
    mov     #TABLE_FONT8_MODE, r0
    cmp/eq  r0, r3
    bt      font8_glyph
    mov     #2, r0
    cmp/hs  r0, r3
    bt      stock_glyph
    mov.l   =SURFACE_GLYPH, r0
    bra     call_glyph
    nop
stock_glyph:
    mov.l   =STOCK_GLYPH, r0
    bra     call_glyph
    nop
font8_glyph:
    add     #TABLE_FONT8_Y_OFFSET, r7
    mov.l   =FONT8_GLYPH, r0
call_glyph:
    jsr     @r0
    nop
    add     #8, r15
    dt      r14
    bt      draw_done
    mov.l   @r15, r3
    mov     r3, r0
    tst     #1, r0
    bt      byte_loop
    bra     word_loop
    nop
draw_done:
    add     #8, r15
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

fusion_word_font8_glyph:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    sts.l   pr, @-r15
    mov.l   @(12,r15), r8
    extu.w  r8, r8
    mov.l   @(16,r15), r9
    mov     #-1, r0
    extu.b  r0, r0
    cmp/hi  r0, r8
    bt      word_font8_stock
    mov.l   =FONT8_CODE_MAP, r1
    mov     r8, r0
    mov.b   @(r0,r1), r8
    extu.b  r8, r8
    mov     #-1, r0
    extu.b  r0, r0
    cmp/eq  r0, r8
    bt      word_font8_stock
    mov.l   r9, @-r15
    mov.l   r8, @-r15
    add     #TABLE_FONT8_Y_OFFSET, r7
    mov.l   =FONT8_GLYPH, r0
    jsr     @r0
    nop
    add     #8, r15
    mov.l   =FONT8_WIDTHS, r1
    mov     r8, r0
    mov.b   @(r0,r1), r0
    extu.b  r0, r0
    mov     #FONT8_SPACE, r1
    cmp/eq  r1, r8
    bt      word_font8_return
    add     #1, r0
word_font8_return:
    lds.l   @r15+, pr
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
word_font8_stock:
    mov.l   r9, @-r15
    mov.l   r8, @-r15
    mov.l   =STOCK_GLYPH, r0
    jsr     @r0
    nop
    add     #8, r15
    mov     #12, r0
    bra     word_font8_return
    nop

fusion_guide_mixed_glyph:
    sts.l   pr, @-r15
    mov.w   =GUIDE_DESCRIPTION_Y, r0
    cmp/hs  r0, r7
    bt      guide_vwf_glyph
    tst     r6, r6
    bf      guide_vwf_glyph
    mov.l   @(8,r15), r1
    mov.l   r1, @-r15
    mov.l   @(8,r15), r1
    mov.l   r1, @-r15
    mov.l   =STOCK_GLYPH, r0
    jsr     @r0
    nop
    add     #8, r15
    mov     #15, r0
    add     r0, r11
    bra     guide_mixed_return
    nop
guide_vwf_glyph:
    mov.l   @(8,r15), r1
    mov.l   r1, @-r15
    mov.l   @(8,r15), r1
    mov.l   r1, @-r15
    mov.l   =fusion_word_font8_glyph, r0
    jsr     @r0
    nop
    add     #8, r15
    add     r0, r11
guide_mixed_return:
    lds.l   @r15+, pr
    rts
    nop
    .pool
