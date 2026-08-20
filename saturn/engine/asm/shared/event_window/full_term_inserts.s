; Stage complete translated demon names and races for the cloned event VM.
;
; Entry: r4 is the stock insert selector. The VM calls each handler twice,
; first to install a temporary stream and again to clean its insertion state.
; Demon names are stored as NUL-terminated FONT8 codes and mapped to FONT16 in
; INSERT_BUFFER. Race rows are already terminated FONT16 streams.

dialogue_demon_name_insert:
    mov.l   =INSERT_STATE, r0
    mov.w   @r0, r1
    extu.w  r1, r0
    tst     r0, r0
    bt      name_prepare
    cmp/eq  #1, r0
    bt      name_cleanup
    rts
    nop

name_cleanup:
    mov     #1, r0
    bra     insert_cleanup
    nop

name_prepare:
    mov     r4, r7
    mov     #0, r5
    shll    r4
    mov.l   =CURRENT_DEMON_IDS, r0
    mov.w   @(r0,r4), r1
    extu.w  r1, r1
    tst     r1, r1
    bt      name_fallback
    mov.w   =DEMON_COUNT, r0
    cmp/hi  r0, r1
    bt      name_fallback
    add     #-1, r1
    shll    r1
    mov.l   =NAME_OFFSETS, r0
    mov.w   @(r0,r1), r1
    extu.w  r1, r1
    mov.l   =NAME_POOL, r2
    add     r1, r2
    mov.l   =INSERT_BUFFER, r3
    mov     #NAME_LIMIT, r6

name_copy:
    mov.b   @r2+, r0
    extu.b  r0, r0
    tst     r0, r0
    bt      name_done
    cmp/eq  #63, r0
    bt      name_space
    mov     #64, r1
    cmp/hs  r1, r0
    bf      name_fallback
    mov     #118, r1
    cmp/hs  r1, r0
    bf      name_primary
    mov.w   =FONT8_TAIL_FIRST, r1
    cmp/hs  r1, r0
    bf      name_fallback
    mov.w   =FONT8_TAIL_END, r1
    cmp/hs  r1, r0
    bf      name_tail
    mov.w   =FONT8_HYPHEN, r1
    cmp/eq  r1, r0
    bt      name_hyphen
    mov.w   =FONT8_APOSTROPHE, r1
    cmp/eq  r1, r0
    bf      name_fallback
    mov.w   =FONT16_APOSTROPHE, r0
    bra     name_store
    nop

name_space:
    mov.w   =FONT16_SPACE, r0
    bra     name_store
    nop

name_primary:
    add     #-63, r0
    bra     name_store
    nop

name_tail:
    mov.w   =FONT8_TAIL_DELTA, r1
    sub     r1, r0
    bra     name_store
    nop

name_hyphen:
    mov.w   =FONT16_HYPHEN, r0

name_store:
    mov.w   r0, @r3
    add     #2, r3
    dt      r6
    bf      name_copy

name_done:
    mov.w   =TERMINATOR, r0
    mov.w   r0, @r3
    mov.l   =INSERT_BUFFER, r4
    mov     #0, r7
    bra     insert_begin
    nop

name_fallback:
    tst     r5, r5
    bf      insert_cleanup_return
    mov     r7, r4
    mov.l   =STOCK_DEMON_INSERT, r0
    jmp     @r0
    nop

dialogue_race_insert:
    mov.l   =INSERT_STATE, r0
    mov.w   @r0, r1
    extu.w  r1, r0
    tst     r0, r0
    bt      race_prepare
    cmp/eq  #1, r0
    bt      race_cleanup
    rts
    nop

race_cleanup:
    mov     #0, r0
    bra     insert_cleanup
    nop

race_prepare:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    shll    r4
    mov.l   =CURRENT_DEMON_IDS, r0
    mov.w   @(r0,r4), r4
    mov.l   =RACE_ID_HELPER, r0
    jsr     @r0
    extu.w  r4, r4
    extu.w  r0, r0
    mov     #RACE_COUNT, r1
    cmp/hs  r1, r0
    bt      race_fallback
    shll2   r0
    mov.l   =RACE_TABLE, r1
    mov.l   @(r0,r1), r4
    lds.l   @r15+, pr
    mov.l   @r15+, r8
    mov     #1, r7
    bra     insert_begin
    nop

race_fallback:
    mov     r8, r4
    lds.l   @r15+, pr
    mov.l   @r15+, r8
    mov.l   =STOCK_RACE_INSERT, r0
    jmp     @r0
    nop

insert_begin:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r7, r9
    mov.l   =INSERT_ACTIVE, r2
    mov     #1, r1
    mov.b   r1, @r2
    mov.l   =INSERT_STATE, r2
    mov.w   @r2, r1
    add     #1, r1
    mov.l   =STREAM_PUSH, r0
    jsr     @r0
    mov.w   r1, @r2
    mov.l   =STREAM_POINTER, r1
    mov.l   r8, @r1
    mov.l   =STREAM_STATUS, r2
    mov.w   =ACTIVE_STATUS, r1
    mov.w   r1, @r2
    tst     r9, r9
    bt      insert_begin_return
    mov.l   =INSERT_BUFFER, r0

insert_begin_return:
    lds.l   @r15+, pr
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    rts
    nop

insert_cleanup:
    mov.l   =TEXT_FLAGS, r3
    mov.w   @r3, r1
    mov.w   =ACTIVE_STATUS, r2
    and     r2, r1
    mov.w   r1, @r3
    mov.l   =INSERT_STATE, r3
    mov     #0, r4
    mov.w   r4, @r3
    mov.l   =INSERT_ACTIVE, r2
    mov.b   r4, @r2

insert_cleanup_return:
    rts
    nop

    .pool
