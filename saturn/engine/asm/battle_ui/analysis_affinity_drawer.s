; Resolve Analyze's fixed-width Japanese affinity records to translated FONT8.

combat_analysis_affinity_font8:
    mov.l   =SOURCE, r0
    mov     r4, r1
    sub     r0, r1
    mov.w   =SOURCE_SIZE, r2
    cmp/hs  r2, r1
    bt      fallback

    mov     #0, r1
    mov     #COUNT, r2
lookup:
    cmp/eq  r0, r4
    bt      found
    add     #SOURCE_STRIDE, r0
    add     #1, r1
    dt      r2
    bf      lookup

fallback:
    mov.l   =STOCK_COUNTED, r0
    jmp     @r0
    nop

found:
    shll    r1
    mov     r1, r0
    mov.l   =OFFSETS, r2
    mov.w   @(r0,r2), r1
    extu.w  r1, r1
    mov.l   =POOL, r4
    add     r1, r4

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
    mov.w   =Y_OFFSET, r0
    add     r0, r9
    mov     r7, r10
    mov     #0, r11

loop:
    mov.b   @r8+, r13
    extu.b  r13, r13
    tst     r13, r13
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
    bra     loop
    add     r14, r11

done:
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
