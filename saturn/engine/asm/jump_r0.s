; Replace a displaced prologue with an absolute jump through r0.

jump_r0:
    mov.l   =TARGET, r0
    jmp     @r0
    nop
    .pool
