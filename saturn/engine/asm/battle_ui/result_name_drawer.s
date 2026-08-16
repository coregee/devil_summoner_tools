; Draw the protagonist codename or an authored party-character name in the
; combat-results panel.

combat_result_name_vwf:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15

    mov     r4, r1
    tst     r1, r1
    bf      character
    mov.l   =CODENAME, r8
    mov.l   =DEST0, r9
    bra     setup
    nop

character:
    shll    r1
    mov.l   =OFFSETS, r0
    mov.w   @(r0,r1), r0
    extu.w  r0, r0
    mov.l   =POOL, r8
    add     r0, r8
    mov.l   =DEST1, r9

setup:
    mov     #2, r10
    shll8   r10
    mov     #0, r11
    mov     #32, r12

loop:
    mov.b   @r8+, r13
    extu.b  r13, r13
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
    .pool
