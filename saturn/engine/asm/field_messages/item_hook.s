field_item_hook:
    mov.l   =TARGET, r0
    jsr     @r0
    nop
    bra     field_item_hook_ready
    nop
    .pool
field_item_hook_ready:
