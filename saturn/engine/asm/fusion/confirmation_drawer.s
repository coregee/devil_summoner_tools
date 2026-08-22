; Draw one Fusion confirmation string horizontally with proportional FONT16
; advances.  The stock caller supplies the same ABI as the original fixed-cell
; string drawer:
;
;   r4       word-string pointer
;   r5       maximum glyph count
;   r6/r7    fixed y/starting x (the stock glyph ABI is not x/y ordered)
;   @(0,sp)  stock glyph-renderer mode
;   @(4,sp)  palette/surface selector
;   @(8,sp)  stock surface descriptor table
;
; Keep the stock FONT16 single-glyph renderer because it understands this
; menu's VDP surface descriptors.  Only the string traversal and horizontal
; advance need replacing for English text. WIDTHS is the table appended to the
; generated FONT16 atlas.

fusion_confirmation_vwf:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r5, r9
    mov     r6, r10
    mov     r7, r11
    mov.l   @(32,r15), r12
    mov.l   @(36,r15), r13
    mov.l   @(40,r15), r14

confirmation_loop:
    tst     r9, r9
    bt      confirmation_done
    mov.w   @r8, r4
    add     #2, r8
    extu.w  r4, r4
    mov.l   =WORD_TERMINATOR, r0
    cmp/eq  r0, r4
    bt      confirmation_done
    mov.l   =WIDTHS, r1
    mov     r4, r0
    mov.b   @(r0,r1), r2
    extu.b  r2, r2
    mov     r10, r5
    mov     r11, r6
    add     r2, r11
    mov.l   =FONT16_SPACE, r0
    cmp/eq  r0, r4
    bt      confirmation_next
    mov     r12, r7
    mov.l   r14, @-r15
    mov.l   r13, @-r15
    mov.l   =STOCK_GLYPH, r0
    jsr     @r0
    nop
    add     #8, r15

confirmation_next:
    dt      r9
    bf      confirmation_loop

confirmation_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    nop
    .pool
