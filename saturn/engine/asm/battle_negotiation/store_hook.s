; The hook begins two bytes off a four-byte boundary. The explicit pool is
; therefore immediately after the three instructions at the aligned address.

store_hook:
    mov.l   =STORE, r0
    jmp     @r0
    nop
    .pool
    nop
