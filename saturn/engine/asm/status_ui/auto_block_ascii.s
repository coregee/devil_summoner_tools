; Move the AUTO/P.A. block down four pixels.  Party-alignment values resolve
; to their unrestricted runtime records but retain the stock ASCII/FONT8 path.

status_auto_block_ascii:
    mov.l   =LAW_SOURCE, r0
    cmp/eq  r0, r4
    bt      auto_block_law
    mov.l   =NEUTRAL_SOURCE, r0
    cmp/eq  r0, r4
    bt      auto_block_neutral
    mov.l   =CHAOS_SOURCE, r0
    cmp/eq  r0, r4
    bf      auto_block_draw
    mov.l   =CHAOS_TEXT, r4
    bra     auto_block_draw
    nop
auto_block_law:
    mov.l   =LAW_TEXT, r4
    bra     auto_block_draw
    nop
auto_block_neutral:
    mov.l   =NEUTRAL_TEXT, r4

auto_block_draw:
    add     #4, r7
    mov.l   =STOCK, r0
    jmp     @r0
    nop
    .pool
    .align 4
