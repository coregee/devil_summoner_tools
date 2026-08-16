; Replace the stock packed-code dispatcher prologue with a cave trampoline.

dispatch_hook:
    mov.l   DISPATCH_CAVE_POINTER, r0
    jmp     @r0
    nop
    nop
    nop
    nop
