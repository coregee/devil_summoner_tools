    ; Replace the Japanese record-byte comparison with the authored English
    ; dense rank table. Demon ID remains the stock deterministic tie-breaker.
    mov     r3, r4
    mov.w   @(r0,r4), r1
    extu.w  r1, r1
    add     #-1, r1
    mov     r1, r0
    mov.l   RANK_TABLE_LITERAL, r7
    mov.b   @(r0,r7), r3
    extu.b  r3, r3
    mov     r6, r2
    add     r6, r2
    mov     r2, r9
    mov     r2, r0
    mov.w   @(r0,r4), r1
    extu.w  r1, r1
    add     #-1, r1
    mov     r1, r0
    mov.b   @(r0,r7), r1
    extu.b  r1, r1
    bra     CONTINUE
    nop
