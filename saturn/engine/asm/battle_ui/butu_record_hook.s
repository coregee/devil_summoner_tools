; Decode one BUTU_SRF ritual-console record, then restore its stock loop state.

butu_record_hook:
    sts.l   pr, @-r15
    mov.l   r2, @-r15
    mov.l   r4, @-r15
    add     r1, r0
    mov     r0, r4
    mov.l   =SCRATCH, r5
    bsr     decode_record
    nop
    mov     r0, r3
    mov.l   @r15+, r4
    mov.l   @r15+, r2
    lds.l   @r15+, pr
    mov     r3, r0
    mov.w   =ROW_STRIDE, r1
    mul.l   r1, r2
    mov     #0, r8
    mov.w   =LINE_WIDTH, r12
    mov.l   =HELPER, r1
    mov.l   =CONTINUATION, r3
    jmp     @r3
    nop
    .pool
