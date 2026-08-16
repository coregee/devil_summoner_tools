; English inserts used by the Combat Conversation runtime.
combat_compact_name_insert:
    mov     r4, r1
    mov.l   =DVL_BASE_POINTER, r0
    mov.l   @r0, r0
    cmp/hs  r0, r1
    bf      compact_name_fallback
    sub     r0, r1
    mov.l   =DVL_SOURCE_SIZE, r0
    cmp/hs  r0, r1
    bt      compact_name_fallback

    shlr2   r1
    shlr    r1
    shll    r1
    mov     r1, r0
    mov.l   =NAME_OFFSETS, r4
    mov.w   @(r0,r4), r1
    extu.w  r1, r1
    mov.l   =STRING_POOL, r4
    add     r1, r4
    mov.l   =FULLWORD_COPY, r0
    jmp     @r0
    nop

compact_name_fallback:
    mov.l   =COMPACT_COPY, r0
    jmp     @r0
    nop

combat_fullword_insert:
    mov.l   =ITEM_BUFFER0, r0
    cmp/eq  r0, r4
    bt      item_buffer0
    mov.l   =ITEM_BUFFER1, r0
    cmp/eq  r0, r4
    bt      item_buffer1

    mov     r4, r1
    mov.l   =RACE_SOURCE, r0
    cmp/hs  r0, r1
    bf      fullword_fallback
    mov.l   =RACE_SOURCE_END, r2
    cmp/hs  r2, r1
    bt      fullword_fallback
    sub     r0, r1
    shlr2   r1
    shlr    r1
    shll    r1
    mov     r1, r0
    mov.l   =RACE_OFFSETS, r4
    mov.w   @(r0,r4), r1
    extu.w  r1, r1
    mov.l   =STRING_POOL, r4
    add     r1, r4
    mov.l   =FULLWORD_COPY, r0
    jmp     @r0
    nop

item_buffer0:
    mov.l   =ITEM_ID0, r0
    bra     item_from_id
    mov.l   @r0, r1

item_buffer1:
    mov.l   =ITEM_ID1, r0
    mov.l   @r0, r1

item_from_id:
    mov     r1, r2
    mov.l   =ITEM_FLAG_MASK, r0
    and     r0, r2
    tst     r2, r2
    bf      fullword_fallback
    tst     r1, r1
    bt      fullword_fallback
    mov.l   =ITEM_ID_LIMIT, r0
    cmp/hs  r0, r1
    bt      fullword_fallback

    add     #-1, r1
    mov     #ITEM_RECORD_SIZE, r2
    mul.l   r2, r1
    mov.l   =ITEM_BASE_POINTER, r0
    mov.l   @r0, r2
    sts     macl, r4
    add     r2, r4
    mov     r4, r1
    add     #ITEM_FULL_NAME_OFFSET, r1
    mov.w   @r1, r0
    extu.w  r0, r0
    add     r2, r0
    mov     r0, r4
    bra     font8_to_pending
    nop

fullword_fallback:
    mov.l   =FULLWORD_COPY, r0
    jmp     @r0
    nop

font8_to_pending:
    mov.l   =PENDING_BUFFER, r2
    mov     #ITEM_NAME_LIMIT, r3

font8_pending_loop:
    mov.b   @r4+, r0
    extu.b  r0, r0
    tst     r0, r0
    bt      font8_pending_done
    mov     #-1, r1
    extu.b  r1, r1
    cmp/eq  r1, r0
    bt      font8_pending_done
    shll    r0
    mov.l   =FONT8_TO_FONT16, r1
    mov.w   @(r0,r1), r0
    mov.w   r0, @r2
    add     #2, r2
    dt      r3
    bf      font8_pending_loop

font8_pending_done:
    mov.w   =COLOR_RESET, r0
    mov.w   r0, @r2
    add     #2, r2
    mov.w   =TERMINATOR, r0
    mov.w   r0, @r2
    mov.l   =PENDING_FLAG, r1
    mov     #1, r0
    mov.w   r0, @r1
    mov.l   =PENDING_BUFFER, r1
    mov.w   @r1, r0
    rts
    extu.w  r0, r0
    .pool
