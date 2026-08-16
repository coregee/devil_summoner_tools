level_up_learned_dispatcher:
    mov     #8, r0
    cmp/eq  r0, r5
    bt      level_up_learned_skill

level_up_learned_label:
    ; The stock skill staging pass overwrites the stack label after its first
    ; draw. Reload the persistent translated stream for every heading redraw.
    mov.l   =LEARNED_LABEL, r4
    mov.l   =FONT16_VWF, r0
    jmp     @r0
    nop

; The stock learned-skill path widens eight compact MAGNAME bytes onto the
; caller's stack. Recover the live skill id, follow MAGNAME's relocated
; full-name pointer, and expand its FONT8 codes into a terminated FONT16 row.
level_up_learned_skill:
    mov.l   =SCRATCH, r3
    mov.l   =LEARNED_LIST_POINTER, r0
    mov.l   @r0, r0
    add     r10, r0
    add     #1, r0
    mov.b   @r0, r0
    extu.b  r0, r0
    tst     r0, r0
    bt      level_up_skill_done
    mov     #96, r1
    mul.l   r1, r0
    sts     macl, r0
    add     #-92, r0
    mov.l   =MAGIC_BASE, r1
    add     r1, r0
    add     #NAME_POINTER, r0
    mov.w   @r0, r0
    extu.w  r0, r0
    add     r1, r0
    mov     r0, r2
    mov     #MAX_NAME_BYTES, r4

level_up_skill_convert:
    mov.b   @r2+, r0
    extu.b  r0, r0
    mov     #-1, r1
    extu.b  r1, r1
    cmp/eq  r1, r0
    bt      level_up_skill_done

    mov     #118, r1
    cmp/hs  r1, r0
    bt      level_up_skill_high
    mov     #63, r1
    cmp/eq  r1, r0
    bt      level_up_skill_space
    cmp/hs  r1, r0
    bf      level_up_skill_done
    bra     level_up_skill_store
    add     #-63, r0

level_up_skill_space:
    mov.w   =267, r0
    bra     level_up_skill_store
    nop

level_up_skill_high:
    mov.w   =205, r1
    cmp/hs  r1, r0
    bf      level_up_skill_done
    mov.w   =213, r1
    cmp/hs  r1, r0
    bt      level_up_skill_punctuation
    add     #-106, r0
    bra     level_up_skill_store
    add     #-44, r0

level_up_skill_punctuation:
    mov.w   =213, r1
    cmp/eq  r1, r0
    bt      level_up_skill_hyphen
    mov.w   =214, r1
    cmp/eq  r1, r0
    bt      level_up_skill_colon
    mov.w   =217, r1
    cmp/eq  r1, r0
    bt      level_up_skill_apostrophe
    mov.w   =229, r1
    cmp/eq  r1, r0
    bf      level_up_skill_done
    bra     level_up_skill_store
    mov.w   =204, r0

level_up_skill_hyphen:
    bra     level_up_skill_store
    mov.w   =173, r0

level_up_skill_colon:
    bra     level_up_skill_store
    mov.w   =175, r0

level_up_skill_apostrophe:
    mov.w   =177, r0

level_up_skill_store:
    mov.w   r0, @r3
    add     #2, r3
    dt      r4
    bf      level_up_skill_convert

level_up_skill_done:
    mov.w   =0x8000, r0
    mov.w   r0, @r3
    mov.l   =SCRATCH, r4
    mov.l   =FONT16_VWF, r0
    jmp     @r0
    nop
    .pool
    .align 4
