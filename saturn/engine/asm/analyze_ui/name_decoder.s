name_decoder:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r12
    mov.l   =NAME_POOL, r8
    mov.l   =LONG_NAME_BITS, r9
    mov     #1, r10
    mov     r12, r0
    tst     r0, r0
    bt      name_select
name_skip_index:
    mov.b   @r9, r1
    extu.b  r1, r1
    mov     r1, r2
    and     r10, r2
    tst     r2, r2
    bt      name_next_bit
name_skip_packed:
    mov.w   @r8+, r1
    cmp/pz  r1
    bt      name_skip_packed
name_next_bit:
    shll    r10
    mov     r10, r1
    extu.b  r1, r1
    tst     r1, r1
    bf      name_bit_ready
    add     #1, r9
    mov     #1, r10
name_bit_ready:
    dt      r0
    bf      name_skip_index
name_select:
    mov.b   @r9, r1
    extu.b  r1, r1
    and     r10, r1
    tst     r1, r1
    bt      name_direct
    mov     r5, r11
    mov     r6, r12
    mov     r7, r13
    add     #-32, r15
    mov     r15, r9
    mov     #1, r10
name_word:
    mov.w   @r8+, r1
    mov     #0, r14
    cmp/pz  r1
    bt      name_not_final
    mov     #1, r14
name_not_final:
    extu.w  r1, r1
    mov     r1, r0
    shlr2   r0
    shlr2   r0
    shlr2   r0
    shlr2   r0
    shlr2   r0
    and     #0x1f, r0
    bsr     name_emit
    nop
    mov     r1, r0
    shlr2   r0
    shlr2   r0
    shlr    r0
    and     #0x1f, r0
    bsr     name_emit
    nop
    mov     r1, r0
    and     #0x1f, r0
    bsr     name_emit
    nop
    tst     r14, r14
    bt      name_word
    mov     #0, r0
    mov.b   r0, @r9
    mov     r15, r4
    mov     #32, r9
    mov     #32, r5
    bra     name_call
    nop
name_direct:
    mov.l   =DVL_SOURCE, r0
    shll2   r12
    shll    r12
    add     r0, r12
    mov     r12, r4
    mov     #0, r9
    mov     r5, r11
    mov     r6, r12
    mov     r7, r13
    mov     #8, r5
name_call:
    add     r9, r15
    mov.l   @(32,r15), r14
    mov.l   @(36,r15), r10
    mov.l   @(40,r15), r8
    sub     r9, r15
    mov     r12, r6
    mov     r13, r7
    mov.l   r8, @-r15
    mov.l   r10, @-r15
    mov.l   r14, @-r15
    jsr     @r11
    nop
    add     #12, r15
    add     r9, r15
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

name_emit:
    tst     r0, r0
    bt      name_emit_return
    cmp/eq  #30, r0
    bt      name_toggle
    cmp/eq  #27, r0
    bt      name_space
    cmp/eq  #28, r0
    bt      name_hyphen
    cmp/eq  #29, r0
    bt      name_apostrophe
    cmp/eq  #31, r0
    bt      name_eight
    tst     r10, r10
    bt      name_lower
    add     #73, r0
    bra     name_store_lower
    nop
name_lower:
    mov     #19, r2
    cmp/hs  r2, r0
    bt      name_lower_tail
    add     #99, r0
    bra     name_store_lower
    nop
name_lower_tail:
    add     #127, r0
    add     #59, r0
name_store_lower:
    mov     #0, r10
    bra     name_store
    nop
name_toggle:
    mov     #1, r2
    xor     r2, r10
    rts
    nop
name_space:
    mov     #63, r0
    bra     name_store_upper
    nop
name_hyphen:
    mov     #-43, r0
    bra     name_store_upper
    nop
name_apostrophe:
    mov     #-39, r0
name_store_upper:
    mov     #1, r10
    bra     name_store
    nop
name_eight:
    mov     #72, r0
    mov     #0, r10
name_store:
    mov.b   r0, @r9
    add     #1, r9
name_emit_return:
    rts
    nop
    .pool
    .align 4
