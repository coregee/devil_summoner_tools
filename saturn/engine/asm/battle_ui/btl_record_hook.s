; Decode BTL_SRF's packed Demon Chat record once, then re-enter the stock loop.

btl_record_hook:
    mov.l   =SCRATCH, r0
    cmp/eq  r0, r12
    bt      loop
    sts.l   pr, @-r15
    add     r1, r12
    mov     r12, r4
    mov.l   =SCRATCH, r5
    bsr     decode_record
    nop
    mov     r0, r12
    lds.l   @r15+, pr

loop:
    mov.b   @r11, r1
    mov.w   @r10, r6
    extu.b  r1, r1
    mov     r1, r0
    add     r1, r0
    mov.l   =CONTINUATION, r1
    jmp     @r1
    nop
    .pool
