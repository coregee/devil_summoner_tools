; BUTU_SRF's displaced loop expects its cave address in r3.

trampoline:
    mov.l   =TARGET, r3
    jmp     @r3
    nop
    .pool
