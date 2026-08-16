; Adapt a stock FONT16 surface call to the exact-X blitter and return the
; configured glyph advance. r4=buffer, r5=stride, r6=x, r7=glyph, stack=color.

font16_width_adapter:
    mov.l   @r15, r0
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    sts.l   pr, @-r15
    mov     r0, r8
    mov     r6, r9
    mov     r7, r10
    mov     r10, r0
    mov.l   =CODE_LIMIT, r1
    cmp/hs  r1, r0
    bt      fixed_width
    mov.l   =FONT16_POINTER, r1
    mov.l   @r1, r1
    mov.l   =WIDTH_OFFSET, r2
    add     r2, r1
    mov.b   @(r0,r1), r11
    extu.b  r11, r11
    tst     r11, r11
    bf      width_ready
fixed_width:
    mov     #16, r11
width_ready:
    mov     r9, r0
    add     r11, r0
    mov.l   =MAX_WIDTH, r1
    cmp/hi  r1, r0
    bt      done
    mov.l   r8, @-r15
    mov.l   r10, @-r15
    mov     #0, r7
    mov.l   =BLITTER, r0
    jsr     @r0
    nop
    add     #8, r15
done:
    mov     r11, r0
    lds.l   @r15+, pr
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    nop
    .pool
