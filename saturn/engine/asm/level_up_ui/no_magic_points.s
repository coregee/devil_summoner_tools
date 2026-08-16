; Build the fixed eight-cell no-MP fallback on the caller's stack. The two
; packed longs come from the authored field through the stock-Latin map.
    mov.l   =TEXT_FIRST, r3
    mov.l   r3, @r15
    mov.l   =TEXT_SECOND, r3
    mov.l   r3, @(4,r15)
    bra     CONTINUE
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    .pool
    .word   0x0009
