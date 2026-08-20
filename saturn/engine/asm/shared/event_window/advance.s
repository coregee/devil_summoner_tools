; Advance Latin glyphs by authored width while preserving the stock event-window
; wrap routine and its mutable globals. FONT12 and FONT16 share this hook; the
; tracked loader selects the active width table at runtime.

event_vwf_advance:
    sts.l   pr, @-r15
    mov.l   r5, @-r15
    mov.l   p_scratch, r2
    mov.l   p_text_advance, r1
    mov.w   @r1, r0
    mov.w   r0, @r2
    mov.l   p_right_margin, r1
    mov.w   @r1, r0
    mov.w   r0, @(2,r2)
    extu.w  r4, r3
    mov.l   p_font16_code_limit, r1
    cmp/hs  r1, r3
    bt      japanese
    mov.l   p_font_mode, r1
    mov.w   @r1, r0
    cmp/eq  #1, r0
    bt      font12
    mov.l   p_font16_pointer, r1
    mov.l   @r1, r1
    mov.l   p_font12_signature_offset, r5
    add     r5, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    cmp/eq  #FONT12_SIGNATURE_VALUE, r0
    bt      font12
    mov     r3, r0
    mov.l   p_font16_pointer, r1
    mov.l   @r1, r1
    mov.l   p_font16_width_offset, r5
    add     r5, r1
    mov     r3, r0
    mov.b   @(r0,r1), r0
    extu.b  r0, r3
    tst     r3, r3
    bt      japanese
    bra     width_ready
    nop

font12:
    extu.w  r4, r3
    mov.l   p_font12_code_limit, r1
    cmp/hs  r1, r3
    bt      japanese
    mov.l   p_font12_widths, r1
    mov     r3, r0
    mov.b   @(r0,r1), r0
    extu.b  r0, r3
    tst     r3, r3
    bt      japanese

width_ready:
    mov.l   p_text_right_edge, r0
    sub     r3, r0
    add     #1, r0
    bra     set_margin
    nop

japanese:
    mov.w   @(0,r2), r0
    mov     r0, r3
    mov.w   @(2,r2), r0

set_margin:
    mov.l   p_right_margin, r1
    mov.w   r0, @r1
    mov.l   p_cursor_x, r1
    mov.w   @r1, r0
    cmp/pz  r0
    bt.s    advance_ready
    mov.w   @(4,r2), r0
    mov.w   @r1, r0
    neg     r0, r0

advance_ready:
    mov.l   p_text_advance, r1
    mov.w   r0, @r1
    mov     r3, r0
    mov.w   r0, @(4,r2)
    mov.l   p_stock_advance, r1
    jsr     @r1
    nop
    mov.l   p_cursor_x, r1
    mov.w   @r1, r0
    tst     r0, r0
    bf      cursor_ready
    mov     #TEXT_LEFT_MARGIN, r0
    mov.w   r0, @r1

cursor_ready:
    mov.l   p_scratch, r2
    mov.l   p_text_advance, r1
    mov.w   @(0,r2), r0
    mov.w   r0, @r1
    mov.l   p_right_margin, r1
    mov.w   @(2,r2), r0
    mov.w   r0, @r1
    mov.l   @r15+, r5
    lds.l   @r15+, pr
    rts
    nop
    .align  4

p_scratch:                 .long scratch_state
p_text_advance:            .long TEXT_ADVANCE
p_right_margin:            .long RIGHT_MARGIN
p_text_right_edge:         .long TEXT_RIGHT_EDGE
p_font16_code_limit:       .long FONT16_CODE_LIMIT
p_font_mode:               .long FONT_MODE
p_font16_pointer:          .long FONT16_POINTER
p_font12_signature_offset: .long FONT12_SIGNATURE_OFFSET
p_font16_width_offset:     .long FONT16_WIDTH_OFFSET
p_font12_code_limit:       .long FONT12_CODE_LIMIT
p_font12_widths:           .long font12_widths
p_cursor_x:                .long CURSOR_X
p_stock_advance:           .long STOCK_ADVANCE

scratch_state:
    .word   16, 0, 16
    .align  4
font12_widths:
