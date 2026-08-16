automap_entry:
    add     #12, r15
    tst     r8, r8
    ; Floorless labels can still occupy the second four-cell strip.
    bt      automap_draw_tail
    nop
    mov     r8, r4
    bsr     floor_compose
    nop
automap_draw_tail:
    mov.l   r12, @-r15
    mov.l   r11, @-r15
    mov     #0, r0
    mov.l   r0, @-r15
    mov     #64, r7
    mov     r9, r6
    mov     #4, r5
    mova    FLOOR_CODE_ROW, r0
    mov     r0, r4
    mov.l   =DRAW_NAME, r1
    jsr     @r1
    nop
    add     #12, r15
automap_return:
    mov.l   =RETURN_ADDR, r0
    jmp     @r0
    nop
    .align  4
    .pool

automap_name_wrapper:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r14
    bsr     prepare_label
    nop
    tst     r0, r0
    bt      automap_name_ready
    mova    TOP_CODE_ROW, r0
    mov     r0, r14
automap_name_ready:
    mov     r14, r4
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    mov.l   =DRAW_NAME, r0
    jmp     @r0
    nop
