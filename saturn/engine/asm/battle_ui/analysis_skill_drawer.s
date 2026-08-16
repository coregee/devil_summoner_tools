; Follow MAGNAME's relocated full-name pointer for Analyze's skill page.

combat_analysis_skill_font8:
    mov     r5, r0
    cmp/eq  #8, r0
    bf      fallback
    mov.l   =MAGIC_FIRST, r0
    cmp/hs  r0, r4
    bf      fallback
    mov.l   =MAGIC_END, r0
    cmp/hi  r4, r0
    bf      fallback

    add     #90, r4
    mov.w   @r4, r0
    extu.w  r0, r0
    mov.l   =MAGIC_BASE, r4
    add     r0, r4

    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r6, r9
    mov     r7, r10
    mov     #0, r11
    mov     #32, r12

loop:
    mov.b   @r8+, r13
    extu.b  r13, r13
    mov     #0xff, r0
    extu.b  r0, r0
    cmp/eq  r0, r13
    bt      done
    mov.l   =WIDTHS, r0
    mov     r13, r1
    mov.b   @(r0,r1), r14
    extu.b  r14, r14
    tst     r14, r14
    bt      done
    mov     r11, r0
    add     r14, r0
    mov     #MAX_WIDTH, r1
    cmp/hi  r1, r0
    bt      done

    mov     r9, r4
    mov.w   =STRIDE, r5
    mov     r11, r6
    mov     r13, r7
    mov.l   r10, @-r15
    mov.l   =PIXEL, r0
    jsr     @r0
    nop
    add     #4, r15
    add     r14, r11
    dt      r12
    bf      loop

done:
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov     #8, r0
    rts
    mov.l   @r15+, r8

fallback:
    mov.l   =STOCK_COUNTED, r0
    jmp     @r0
    nop
    .pool
    .align 4
