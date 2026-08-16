table_font8_vwf:
    mov.l   r8, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r6, r10
    mov     r7, r11
    mov     r5, r12
table_font8_loop:
    ; Direct DVLNAME rows can fill all eight bytes without a terminator.
    tst     r12, r12
    bt      table_font8_done
    mov.b   @r8, r1
    extu.b  r1, r1
    tst     r1, r1
    bt      table_font8_done
    mov     #0xfe, r0
    extu.b  r0, r0
    cmp/hs  r0, r1
    bt      table_font8_done
    bsr     table_font8_width
    nop
    mov     r2, r14
    mov.b   @r8, r4
    extu.b  r4, r4
    mov     r10, r5
    mov     r11, r6
    mov.l   @(24,r15), r7
    mov.l   =GLYPH, r0
    jsr     @r0
    nop
    add     #1, r14
    add     r14, r11
    add     #1, r8
    add     #-1, r12
    bra     table_font8_loop
    nop
table_font8_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    rts
    mov.l   @r15+, r8
table_font8_width:
    mov     #118, r0
    cmp/hs  r0, r1
    bf      table_font8_width_low
    add     #-128, r1
    bra     table_font8_width_ready
    add     #-22, r1
table_font8_width_low:
    add     #-63, r1
table_font8_width_ready:
    mov.l   =WIDTHS, r0
    mov.b   @(r0,r1), r2
    extu.b  r2, r2
    rts
    nop
    .pool
    .align 4
