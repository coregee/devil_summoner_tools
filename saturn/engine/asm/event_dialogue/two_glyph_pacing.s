; Reset the per-update visible-glyph budget, count actual framebuffer commits,
; and preserve phase 0x8000 for one extra visible glyph. Automatic wrapping
; can suppress a requested draw, so the count lives at the blitter boundary.

two_glyph_update:
    sts.l   pr, @-r15
    mov.l   =VISIBLE_COUNT, r1
    mov     #0, r0
    mov.b   r0, @r1
    mov.l   =ORIGINAL_UPDATE, r1
    jsr     @r1
    nop
    lds.l   @r15+, pr
    rts
    nop

two_glyph_blit:
    sts.l   pr, @-r15
    mov.l   =VISIBLE_BLITTER, r1
    jsr     @r1
    nop
    mov.l   =VISIBLE_COUNT, r1
    mov.b   @r1, r2
    add     #1, r2
    mov.b   r2, @r1
    lds.l   @r15+, pr
    rts
    nop

two_glyph_tail:
    mov.w   @r8, r2
    extu.w  r2, r1
    cmp/eq  r11, r1
    bf      tail_continue
    mov.l   =VISIBLE_COUNT, r0
    mov.b   @r0, r1
    mov     #1, r2
    cmp/eq  r2, r1
    bf      stock_clear
    add     #1, r1
    mov.b   r1, @r0
    bra     tail_continue
    nop
stock_clear:
    mov     #0, r1
    mov.w   r1, @r8
tail_continue:
    mov     r11, r3
    mov.l   =TAIL_CONTINUE, r1
    jmp     @r1
    nop
    .pool
