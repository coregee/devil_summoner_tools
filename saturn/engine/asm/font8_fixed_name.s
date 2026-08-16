; Draw an eight-byte name with proportional FONT8 advances.
; r4=string, r5=bitmap, r6=palette.

font8_fixed_name:
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
    mov     #0, r11
    mov     #8, r12
font8_fixed_loop:
    mov.b   @r8+, r13
    extu.b  r13, r13
    tst     r13, r13
    bt      font8_fixed_done
    mov.l   =WIDTHS, r0
    mov     r13, r1
    mov.b   @(r0,r1), r14
    extu.b  r14, r14
    tst     r14, r14
    bt      font8_fixed_japanese
    mov     r9, r4
    mov.w   =STRIDE, r5
    mov     r11, r6
    mov     r13, r7
    mov.l   r10, @-r15
    mov.l   =PIXEL, r0
    jsr     @r0
    nop
    add     #4, r15
    bra     font8_fixed_next
    add     r14, r11

font8_fixed_japanese:
    mov     r9, r4
    mov.w   =STRIDE, r5
    mov     r11, r6
    shlr2   r6
    shlr    r6
    mov     r13, r7
    mov.l   r10, @-r15
    mov.l   =STOCK, r0
    jsr     @r0
    nop
    add     #4, r15
    add     #8, r11

font8_fixed_next:
    dt      r12
    bf      font8_fixed_loop

font8_fixed_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
