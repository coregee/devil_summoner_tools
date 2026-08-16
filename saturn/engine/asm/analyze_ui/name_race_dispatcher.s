table_dispatcher:
    mov     r5, r0
    cmp/eq  #6, r0
    bt      table_race
    cmp/eq  #8, r0
    bf      table_fallback
    mov.l   =DVL_SOURCE, r0
    sub     r0, r4
    shlr2   r4
    shlr    r4
    mov.l   =TABLE_FONT8_VWF, r5
    mov.l   =NAME_DECODER, r0
    jmp     @r0
    nop
table_race:
    mov.l   =TABLE_FONT8_VWF, r0
    mov.l   r0, @-r15
    mov.l   =TABLE_RACE_SOURCE, r0
    sub     r0, r4
    bra     race_index
    nop
table_fallback:
    mov.l   =TABLE_STOCK, r0
    jmp     @r0
    nop

detailed_dispatcher:
    mov     r5, r0
    cmp/eq  #3, r0
    bt      detailed_race
    cmp/eq  #8, r0
    bf      detailed_fallback
    mov.l   =CURRENT_NAME_PTR, r0
    mov.l   @r0, r4
    mov.l   =DVL_SOURCE, r0
    sub     r0, r4
    shlr2   r4
    shlr    r4
    mov.l   =FONT16_VWF, r5
    mov.l   =NAME_DECODER, r0
    jmp     @r0
    nop
detailed_race:
    mov.l   =FONT16_VWF, r0
    mov.l   r0, @-r15
    mov.l   =DETAIL_RACE_SOURCE, r0
    sub     r0, r4
race_index:
    mov     #0, r0
    mov     #6, r1
race_divide:
    cmp/hs  r1, r4
    bf      race_divide_done
    add     #-6, r4
    add     #1, r0
    bra     race_divide
    nop
race_divide_done:
    shll    r0
    mov.l   =RACE_OFFSETS, r1
    mov.w   @(r0,r1), r0
    extu.w  r0, r0
    mov.l   =RACE_POOL, r4
    add     r0, r4
race_ready:
    mov     #16, r5
    mov.l   @r15+, r0
    jmp     @r0
    nop
detailed_fallback:
    mov.l   =DETAIL_STOCK, r0
    jmp     @r0
    nop
    .pool
    .align 4
