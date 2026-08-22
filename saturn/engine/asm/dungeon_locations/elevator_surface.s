    .align  4
    .pool

elevator_entry:
    sts.l   pr, @-r15
    mov     #1, r0
    mov.l   =ELEVATOR_MODE, r1
    mov.b   r0, @r1
    mov.l   =ELEVATOR_DRAW, r1
    jsr     @r1
    nop
    mov     #0, r0
    mov.l   =ELEVATOR_MODE, r1
    mov.b   r0, @r1
    lds.l   @r15+, pr
    rts
    nop
    .align  4
    .pool

elevator_floor_compose:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    add     #-8, r15
    mov     r15, r13
    mov     #0, r10
    mov     #0, r12
    cmp/pz  r4
    bt      elevator_abs_ready
    mov     #1, r12
    neg     r4, r4
elevator_abs_ready:
    tst     r4, r4
    bt      elevator_formatted
    mov     #0, r8
elevator_tens:
    mov     #10, r0
    cmp/hs  r0, r4
    bf      elevator_parts
    add     #-10, r4
    add     #1, r8
    bra     elevator_tens
    nop
elevator_parts:
    mov.l   =ELEVATOR_FORMAT, r11
    mov     #3, r9
elevator_part:
    mov.b   @r11+, r0
    extu.b  r0, r0
    cmp/eq  #1, r0
    bt      elevator_lower
    cmp/eq  #2, r0
    bt      elevator_number
    mov.w   =ELEVATOR_CODE_FLOOR, r0
    mov.w   r0, @r13
    add     #2, r13
    add     #1, r10
    bra     elevator_next_part
    nop
elevator_lower:
    tst     r12, r12
    bt      elevator_next_part
    mov.w   =ELEVATOR_CODE_LOWER, r0
    mov.w   r0, @r13
    add     #2, r13
    add     #1, r10
    bra     elevator_next_part
    nop
elevator_number:
    tst     r8, r8
    bt      elevator_ones
    mov.w   =CODE_0, r0
    add     r8, r0
    mov.w   r0, @r13
    add     #2, r13
    add     #1, r10
elevator_ones:
    mov.w   =CODE_0, r0
    add     r4, r0
    mov.w   r0, @r13
    add     #2, r13
    add     #1, r10
elevator_next_part:
    dt      r9
    bf      elevator_part
elevator_formatted:
    bra     floor_format_ready
    nop
    .align  4
    .pool

ELEVATOR_FORMAT:
    .byte   ELEVATOR_PART_0, ELEVATOR_PART_1, ELEVATOR_PART_2
ELEVATOR_MODE:
    .byte   0
    .align  4
    .pool
