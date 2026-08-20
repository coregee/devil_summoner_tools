; Cloned EVENT/MSGR choice-menu loops handle 0x8006/0x8007 outside the dialogue VM.
; Stock code draws at most three Japanese glyphs and estimates the next X from
; that fixed-width limit.  English name rows contain up to eight proportional
; FONT16 glyphs, so draw the complete bounded row and return its exact final X.
;
; Entry: r4 = terminated FONT16 row, r5 = x, r6 = y
; Exit:  r0 = final x

raw_menu_name_insert:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r5, r9
    mov     r6, r10
    mov     #8, r11

raw_menu_name_loop:
    mov.w   @r8+, r4
    extu.w  r4, r4
    mov.w   =TERMINATOR, r1
    cmp/eq  r1, r4
    bt      raw_menu_name_done
    mov     r9, r5
    mov     r10, r6
    mov.l   MENU_BLITTER_POINTER, r12
    jsr     @r12
    nop
    ; The VWF adapter returns the proportional advance in r0.  A selective
    ; name_runtime build keeps the stock blitter, whose r0 return is unrelated
    ; to glyph width, so read the stock renderer's live fixed advance instead.
    mov.l   =ORIGINAL_BLITTER, r1
    cmp/eq  r1, r12
    bf      raw_menu_name_advance_ready
    mov.l   =STOCK_ADVANCE, r1
    mov.w   @r1, r0
    extu.w  r0, r0
raw_menu_name_advance_ready:
    add     r0, r9
    dt      r11
    bf      raw_menu_name_loop
    nop

raw_menu_name_done:
    mov     r9, r0
    lds.l   @r15+, pr
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
