; Draw one NORMHELP word and return its proportional advance in r0.

normcom_help_draw_word:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r9, r10
    mov     r9, r0
    shlr    r0
    sub     r0, r8
    mov.l   =SCRATCH_FB, r0
    mov.l   r8, @r0
    mov.l   =SCRATCH_STRIDE, r0
    mov.w   r5, @r0
    mov     r7, r11
    mov     #0, r12

    mov     r11, r13
    shlr8   r13
    mov     r13, r0
    add     #-8, r0
    mov     #0x78, r1
    cmp/hs  r1, r0
    bt      help_native
    mov     r11, r14
    extu.b  r14, r14
    mov     r13, r4
    bsr     help_latin
    nop
    tst     r14, r14
    bt      help_done
    mov     r14, r4
    bsr     help_latin
    nop
    bra     help_done
    nop

help_native:
    mov     r11, r4
    mov     r10, r5
    mov     #0, r6
    mov.l   =BLITTER, r0
    jsr     @r0
    nop
    mov     r11, r0
    extu.w  r0, r0
    tst     r0, r0
    bt      help_native_fixed
    mov.w   =WIDTH_LIMIT, r1
    cmp/hs  r1, r0
    bt      help_native_fixed
    mov.l   =WIDTHS, r1
    mov.b   @(r0,r1), r12
    extu.b  r12, r12
    tst     r12, r12
    bf      help_done
help_native_fixed:
    bra     help_done
    mov     #16, r12

help_latin:
    sts.l   pr, @-r15
    extu.b  r4, r4
    add     #-8, r4
    tst     r4, r4
    bf      help_code_ready
    mov.w   =PACKED_SPACE, r4
help_code_ready:
    mov     r4, r0
    mov.l   =WIDTHS, r1
    mov.b   @(r0,r1), r13
    extu.b  r13, r13
    tst     r13, r13
    bf      help_width_ready
    mov     #16, r13
help_width_ready:
    mov     r10, r5
    add     r12, r5
    mov     #0, r6
    mov.l   =BLITTER, r0
    jsr     @r0
    nop
    add     r13, r12
    lds.l   @r15+, pr
    rts
    nop

help_done:
    mov     r12, r3
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    rts
    mov     r3, r0
    .pool
