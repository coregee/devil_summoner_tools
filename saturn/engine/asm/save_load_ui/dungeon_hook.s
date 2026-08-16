; Replace the stock dungeon-name call site with an absolute jump to the cave.
    mov.l   =DUNGEON_DRAWER, r0
    jmp     @r0
    nop
    .pool
