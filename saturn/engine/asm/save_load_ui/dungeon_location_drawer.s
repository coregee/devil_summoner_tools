; Draw one complete generated dungeon/floor row for the selected save slot.
dungeon_draw_entry:
    sts.l   pr, @-r15
    mov.l   =DRAW_CONTEXT, r0
    mov.l   r0, @-r15
    mov.l   r4, @-r15
    mov     #4, r0
    mov.l   r0, @-r15

    mov.l   =DUNGEON_INDEX, r0
    mov.b   @r0, r0
    extu.b  r0, r0
    mov     #DUNGEON_RECORD_BYTES, r1
    mul.l   r1, r0
    sts     macl, r0
    mov.l   =dungeon_table, r4
    add     r0, r4
    mov     #DUNGEON_RECORD_CELLS, r5
    mov     #-1, r6
    mov.w   =0x00a4, r7
    mov.l   =DRAW_TEXT, r0
    jsr     @r0
    nop

    add     #12, r15
    lds.l   @r15+, pr
    rts
    nop
    .pool
