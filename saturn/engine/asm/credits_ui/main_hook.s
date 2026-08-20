; Replace the six stock per-glyph calls with one complete proportional row.
    mov.w   @r12, r4
    extu.w  r4, r4
    mov     r13, r5
    mov     r14, r6
    mov     #6, r7
    mov.l   VDP_LITERAL, r3
    mov.l   RENDERER_LITERAL, r1
    jsr     @r1
    nop
    add     #6, r13
    bra     CONTINUATION
    nop
