; Direct-index adapter for the portrait VM's three fixed character inserts.
; Entry: r4 is character index 0..2. The shared name-copy/cleanup labels and
; insertion buffer belong to full_term_inserts.s in the same runtime arena.

dialogue_character_name_insert:
    mov.l   =INSERT_STATE, r0
    mov.w   @r0, r1
    extu.w  r1, r0
    tst     r0, r0
    bt      character_prepare
    cmp/eq  #1, r0
    bt      character_cleanup
    rts
    nop

character_cleanup:
    mov.l   =NAME_CLEANUP, r0
    jmp     @r0
    nop

character_prepare:
    mov     r4, r7
    extu.w  r4, r1
    mov     #CHARACTER_COUNT, r0
    cmp/hs  r0, r1
    bt      character_return
    shll    r1
    mov.l   =CHARACTER_OFFSETS, r0
    mov.w   @(r0,r1), r1
    extu.w  r1, r1
    mov.l   =NAME_POOL, r2
    add     r1, r2
    mov.l   =INSERT_BUFFER, r3
    mov     #NAME_LIMIT, r6
    mov.l   =NAME_COPY, r0
    jmp     @r0
    mov     #1, r5

character_return:
    rts
    nop

    .pool
