field_choice_draw:
    mov.l   =YES_FIELD, r0
    cmp/eq  r0, r6
    bt      field_choice_yes
    mov.l   =NO_FIELD, r0
    cmp/eq  r0, r6
    bf      field_choice_tail
    mov.l   =NO_BITMAP, r1
    bra     field_choice_copy
    nop
field_choice_yes:
    mov.l   =YES_BITMAP, r1
field_choice_copy:
    mov.l   =FONT_DST, r2
    mov     #BITMAP_LONGS, r3
field_choice_copy_loop:
    mov.l   @r1+, r0
    mov.l   r0, @r2
    add     #4, r2
    dt      r3
    bf      field_choice_copy_loop
    mov.l   =ROW, r6
field_choice_tail:
    mov.l   =ORIGINAL_DRAW, r0
    jmp     @r0
    nop
    .pool
