; Route the three authored field-window records through precomposed FONT16
; strips while retaining the stock renderer for every other row.
prompt_draw:
    mov.l   =PROMPT_FIELD, r0
    cmp/eq  r0, r6
    bt      prompt_bitmap
    mov.l   =YES_FIELD, r0
    cmp/eq  r0, r6
    bt      yes_bitmap
    mov.l   =NO_FIELD, r0
    cmp/eq  r0, r6
    bt      no_bitmap
    mov.l   =ORIGINAL_DRAW, r0
    jmp     @r0
    nop
prompt_bitmap:
    mov.l   =PROMPT_BITMAP, r3
    bra     draw_bitmap
    nop
yes_bitmap:
    mov.l   =YES_ROW, r6
    mov.l   =YES_BITMAP, r3
    bra     draw_bitmap
    nop
no_bitmap:
    mov.l   =NO_ROW, r6
    mov.l   =NO_BITMAP, r3
draw_bitmap:
    mov.l   =SCRATCH, r0
    sts     pr, r1
    mov.l   r1, @r0
    mov.l   =FONT_PTR, r1
    mov.l   @r1, r2
    mov.l   r2, @(4,r0)
    mov.l   r3, @r1
    mov.l   =ORIGINAL_DRAW, r0
    jsr     @r0
    nop
    mov.l   =SCRATCH, r0
    mov.l   =FONT_PTR, r1
    mov.l   @(4,r0), r2
    mov.l   r2, @r1
    mov.l   @r0, r1
    lds     r1, pr
    rts
    nop
    .pool
