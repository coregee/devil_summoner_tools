status_skill_vwf:
    mov.l   =MAGIC_FIRST, r0
    cmp/hs  r0, r4
    bf      skill_fallback
    mov.l   =MAGIC_END, r0
    cmp/hs  r0, r4
    bt      skill_fallback
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    add     #NAME_POINTER, r8
    mov.w   @r8, r0
    extu.w  r0, r0
    mov.l   =MAGIC_BASE, r8
    add     r0, r8
    mov     r6, r9
    mov     r7, r10
    mov.l   @(32,r15), r11
    mov.l   @(36,r15), r12
    mov.l   @(40,r15), r13
    mov.l   =WIDTHS, r14
skill_loop:
    mov.b   @r8, r1
    extu.b  r1, r1
    mov     #0xff, r0
    extu.b  r0, r0
    cmp/eq  r0, r1
    bt      skill_done
    mov     r1, r0
    mov.b   @(r0,r14), r2
    extu.b  r2, r2
    tst     r2, r2
    bt      skill_done
    mov     r10, r0
    tst     #1, r0
    bt      skill_draw
    mov.l   =FONT_BITMAP, r0
    mov     r1, r2
    shll2   r2
    shll    r2
    add     r2, r0
    mov     #8, r3
skill_shift_right:
    mov.b   @r0, r1
    extu.b  r1, r1
    shlr    r1
    mov.b   r1, @r0
    add     #1, r0
    dt      r3
    bf      skill_shift_right
skill_draw:
    mov.b   @r8, r4
    extu.b  r4, r4
    mov     r9, r5
    mov     r10, r6
    mov     r11, r7
    mov     r10, r0
    tst     #1, r0
    bt      skill_call
    add     #-1, r6
skill_call:
    mov.l   r13, @-r15
    mov.l   r12, @-r15
    mov.l   =GLYPH, r0
    jsr     @r0
    nop
    add     #8, r15
    mov     r10, r0
    tst     #1, r0
    bt      skill_advance
    mov.l   =FONT_BITMAP, r0
    mov.b   @r8, r1
    extu.b  r1, r1
    shll2   r1
    shll    r1
    add     r1, r0
    mov     #8, r3
skill_shift_left:
    mov.b   @r0, r1
    extu.b  r1, r1
    shll    r1
    mov.b   r1, @r0
    add     #1, r0
    dt      r3
    bf      skill_shift_left
skill_advance:
    mov.b   @r8, r1
    extu.b  r1, r1
    mov     r1, r0
    mov.b   @(r0,r14), r2
    extu.b  r2, r2
    add     #1, r2
    add     r2, r10
    bra     skill_loop
    add     #1, r8
skill_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
skill_fallback:
    mov.l   =STOCK, r0
    jmp     @r0
    nop
    .pool
    .align 4
