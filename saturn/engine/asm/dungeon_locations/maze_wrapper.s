maze_entry:
    mov     #-1, r0
    mov.l   =CURRENT_APPEND, r1
    mov.b   r0, @r1
    mov     r11, r4
    bsr     floor_compose
    nop
    mov.w   =BOTTOM_CODE, r1
    mov     r15, r2
    add     #8, r2
    mov     #4, r3
maze_codes:
    mov.w   r1, @r2
    add     #1, r1
    add     #2, r2
    dt      r3
    bf      maze_codes
    mov.l   =RETURN_ADDR, r0
    jmp     @r0
    nop
    .align  4
    .pool

maze_name_wrapper:
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
    bt      maze_name_ready
    mova    TOP_CODE_ROW, r0
    mov     r0, r14
maze_name_ready:
    mov     r14, r4
    mov.l   =DRAW_NAME, r1
    jsr     @r1
    nop
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    rts
    nop
