action_vwf:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov.l   @(8,r15), r2
    mov.l   @(12,r15), r3
    mov.l   r3, @-r15
    mov.l   r2, @-r15
    mov.l   =ACTION_GLYPH, r1
    jsr     @r1
    nop
    add     #8, r15
    tst     r8, r8
    bt      action_blank
    mov     #ACTION_END, r1
    cmp/hs  r1, r8
    bt      action_fixed
    add     #-1, r8
    mova    ACTION_WIDTHS, r0
    mov.b   @(r0,r8), r0
    extu.b  r0, r0
    bra     action_done
    nop
action_blank:
    bra     action_done
    mov     #0, r0
action_fixed:
    mov     #12, r0
action_done:
    lds.l   @r15+, pr
    rts
    mov.l   @r15+, r8
    .pool
    .align  4
