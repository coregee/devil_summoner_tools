level_up_learned_prepare:
    ; Surface 19 is live VDP1 texture memory. Clearing it on every idle redraw
    ; lets VDP1 sample the translated row halfway through rebuilding. Preserve
    ; the completed texture until the learned skill changes.
    mov.l   =LEARNED_LIST_POINTER, r1
    mov.l   @r1, r1
    add     r10, r1
    add     #1, r1
    mov.b   @r1, r0
    mov.l   =LAST_SKILL, r1
    mov.b   @r1, r2
    cmp/eq  r2, r0
    bt      level_up_learned_prepare_done
    mov.b   r0, @r1
    mov.l   =PREPARE, r1
    jmp     @r1
    nop

level_up_learned_prepare_done:
    rts
    nop
    .pool
    .align 4
