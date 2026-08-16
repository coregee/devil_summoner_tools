; Replace the two Japanese combat-result headings with authored FONT8 labels.

combat_result_label_vwf:
    tst     r6, r6
    bf      continuation

    mov     #0x5d, r0
    cmp/eq  r0, r7
    bt      life_stones
    mov     #0x5c, r0
    cmp/eq  r0, r7
    bt      beads
    bra     fallback
    nop

continuation:
    mov     #0x4c, r0
    cmp/eq  r0, r7
    bt      suppress
    mov     #0x45, r0
    cmp/eq  r0, r7
    bt      suppress
    mov     #0x41, r0
    cmp/eq  r0, r7
    bt      suppress
    mov     #-0x32, r0
    extu.b  r0, r0
    cmp/eq  r0, r7
    bt      suppress
    mov     #0x75, r0
    cmp/eq  r0, r7
    bt      suppress
    mov     #0x46, r0
    cmp/eq  r0, r7
    bt      suppress
    bra     fallback
    nop

life_stones:
    mov.l   =LIFE_STONES, r0
    bra     draw
    nop

beads:
    mov.l   =BEADS, r0

draw:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r0, r8
    mov     r4, r9
    mov     r5, r10
    mov     r5, r0
    shll    r0
    add     r0, r9
    mov     #0, r11
    mov     #32, r12

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

    mov     r9, r4
    mov     r10, r5
    mov     r11, r6
    mov     r13, r7
    mov     #2, r0
    mov.l   r0, @-r15
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
    rts
    mov.l   @r15+, r8

suppress:
    rts
    nop

fallback:
    mov.l   =STOCK, r0
    jmp     @r0
    nop
    .pool
