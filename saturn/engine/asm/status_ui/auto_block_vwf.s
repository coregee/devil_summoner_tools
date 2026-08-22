; Move the AUTO/P.A. ASCII block down four pixels.  The three party-alignment
; values additionally resolve to authored strings and reuse the shared FONT8
; VWF after adapting the stock ASCII-drawer argument layout.

status_auto_block_vwf:
    mov.l   =LAW_SOURCE, r0
    cmp/eq  r0, r4
    bt      auto_block_law
    mov.l   =NEUTRAL_SOURCE, r0
    cmp/eq  r0, r4
    bt      auto_block_neutral
    mov.l   =CHAOS_SOURCE, r0
    cmp/eq  r0, r4
    bf      auto_block_fallback
    mov.l   =CHAOS_TEXT, r4
    bra     auto_block_alignment
    nop
auto_block_law:
    mov.l   =LAW_TEXT, r4
    bra     auto_block_alignment
    nop
auto_block_neutral:
    mov.l   =NEUTRAL_TEXT, r4

auto_block_alignment:
    ; ASCII drawer: r5=color, r6=x, r7=y, stack=raw0/raw1/mode.
    ; FONT8 VWF:    r6=color, r7=x, stack=y/raw0/raw1.
    ; Keep the stock y here; the shared status VWF applies the common +4 shift.
    mov     r7, r1
    mov     r6, r0
    mov     r5, r6
    mov     r0, r7
    mov.l   @(4,r15), r3
    mov.l   @r15, r2
    mov.l   r3, @(8,r15)
    mov.l   r2, @(4,r15)
    mov.l   r1, @r15
    mov.l   =FONT8_VWF, r0
    jmp     @r0
    nop

auto_block_fallback:
    add     #4, r7
    mov.l   =STOCK, r0
    jmp     @r0
    nop
    .pool
    .align 4
