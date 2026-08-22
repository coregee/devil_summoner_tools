; Advance the title caller's pen by the current glyph width, then tail-call
; the stock FONT16 glyph drawer. a0-a3 remain the stock draw arguments and s1
; remains the caller-owned pen. The runtime target is computed PC-relatively so
; this cave needs no ELF relocation record.

title_help_draw_wrapper:
    move t8, ra
    bal pc
    nop
pc:
    addiu t9, ra, title_help_widths - pc
    sltiu t7, a3, 268
    beq t7, zero, fallback
    nop
    addu t6, t9, a3
    lbu t6, 0(t6)
    b advance
    nop
fallback:
    addiu t6, zero, 15
advance:
    addu s1, s1, t6
    lui t9, %hi(stock_title_help_glyph_draw - pc)
    ori t9, t9, %lo(stock_title_help_glyph_draw - pc)
    addu t9, t9, ra
    move ra, t8
    jr t9
    nop

