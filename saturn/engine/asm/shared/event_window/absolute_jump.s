; Shared twelve-byte inline trampoline: load an absolute target, jump, and leave the
; fourth instruction word as reviewed padding before the aligned literal.
    mov.l   =TARGET, r3
    jmp     @r3
    nop
    nop
    .pool
