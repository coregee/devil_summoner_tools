; Replace the stock type-compare chain with the relocated profile router.
; ROUTER_POINTER is the existing literal slot patched to the router address.
    mov.l   ROUTER_POINTER, r1
    jmp     @r1
    nop
