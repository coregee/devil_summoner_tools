; Replace the original 12-byte prologue with a jump to the shop drawer.

    mov.l   =TARGET, r0
    jmp     @r0
    nop
    .pool
