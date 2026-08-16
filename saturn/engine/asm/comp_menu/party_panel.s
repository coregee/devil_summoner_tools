; Resolve full character names and compact overflow demon names in COMP panels.
; r4=direct DVLNAME/CHARNAME record, r5=bitmap, r6=palette.

comp_party_panel:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r5, r9
    mov     r6, r10
    add     #-32, r15

    mov.l   =DVL_BASE, r1
    cmp/hs  r1, r8
    bf      party_character
    mov.l   =DVL_END, r2
    cmp/hs  r2, r8
    bt      party_character
    mov     r8, r12
    sub     r1, r12
    shlr2   r12
    shlr    r12
    mov.l   =LONG_NAME_BITS, r14
    mov     r12, r0
    shlr8   r0
    tst     r0, r0
    bt      party_name_low_page
    extu.b  r12, r12
    add     #32, r14
    mov.l   =HIGH_NAME_POOL, r8
    bra     party_name_page_ready
    nop
party_name_low_page:
    mov.l   =NAME_POOL, r8
party_name_page_ready:
    mov     #1, r13
    tst     r12, r12
    bt      party_name_select
party_name_skip_index:
    mov.b   @r14, r1
    extu.b  r1, r1
    and     r13, r1
    tst     r1, r1
    bt      party_name_next_bit
party_name_skip_packed:
    mov.w   @r8+, r1
    cmp/pz  r1
    bt      party_name_skip_packed
party_name_next_bit:
    shll    r13
    mov     r13, r0
    tst     #0xff, r0
    bf      party_name_bit_ready
    add     #1, r14
    mov     #1, r13
party_name_bit_ready:
    dt      r12
    bf      party_name_skip_index
party_name_select:
    mov.b   @r14, r0
    tst     r13, r0
    bt      party_fallback
    mov     r15, r11
    mov     #1, r12
party_name_word:
    mov.w   @r8+, r1
    mov     r1, r14
    extu.w  r1, r1
    mov     r1, r0
    shlr8   r0
    shlr2   r0
    and     #0x1f, r0
    bsr     party_name_emit
    nop
    mov     r1, r0
    shlr2   r0
    shlr2   r0
    shlr    r0
    and     #0x1f, r0
    bsr     party_name_emit
    nop
    mov     r1, r0
    and     #0x1f, r0
    bsr     party_name_emit
    nop
    cmp/pz  r14
    bt      party_name_word
    mov     #0, r0
    mov.b   r0, @r11
    bra     party_draw_ready
    mov     r15, r8

party_character:
    mov.l   =CHAR_FIRST, r1
    cmp/hs  r1, r8
    bf      party_fallback
    mov.l   =CHAR_END, r1
    cmp/hs  r1, r8
    bt      party_fallback
    mov.l   =CHAR_BASE, r1
    mov     r8, r0
    sub     r1, r0
    mov     r0, r2
    mov     #7, r1
    and     r1, r2
    tst     r2, r2
    bf      party_fallback
    shlr2   r0
    shlr    r0
    shll    r0
    mov.l   =CHAR_OFFSETS, r1
    mov.w   @(r0,r1), r0
    extu.w  r0, r0
    mov.l   =CHAR_POOL, r8
    add     r0, r8

party_draw_ready:
    mov     #0, r11
    mov     #32, r12
party_draw_loop:
    mov.b   @r8+, r13
    extu.b  r13, r13
    tst     r13, r13
    bt      party_done
    mov.l   =WIDTHS, r0
    mov     r13, r1
    mov.b   @(r0,r1), r14
    extu.b  r14, r14
    tst     r14, r14
    bt      party_done
    mov     r11, r0
    add     r14, r0
    mov     #80, r1
    cmp/hi  r1, r0
    bt      party_done
    mov     r9, r4
    mov.w   =STRIDE, r5
    mov     r11, r6
    mov     r13, r7
    mov.l   r10, @-r15
    mov.l   =PIXEL, r0
    jsr     @r0
    nop
    add     #4, r15
    add     r14, r11
    dt      r12
    bf      party_draw_loop
party_done:
    add     #32, r15
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

party_fallback:
    add     #32, r15
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    mov.l   =FALLBACK, r0
    jmp     @r0
    nop

party_name_emit:
    tst     r0, r0
    bt      party_name_emit_return
    cmp/eq  #30, r0
    bt      party_name_toggle
    cmp/eq  #27, r0
    bt      party_name_space
    cmp/eq  #28, r0
    bt      party_name_hyphen
    cmp/eq  #29, r0
    bt      party_name_apostrophe
    cmp/eq  #31, r0
    bt      party_name_eight
    tst     r12, r12
    bt      party_name_lower
    add     #73, r0
    bra     party_name_store_lower
    nop
party_name_lower:
    mov     #19, r2
    cmp/hs  r2, r0
    bt      party_name_lower_tail
    add     #99, r0
    bra     party_name_store_lower
    nop
party_name_lower_tail:
    add     #127, r0
    add     #59, r0
party_name_store_lower:
    mov     #0, r12
    bra     party_name_store
    nop
party_name_toggle:
    mov     #1, r2
    xor     r2, r12
    rts
    nop
party_name_space:
    mov     #63, r0
    bra     party_name_store_upper
    nop
party_name_hyphen:
    mov     #-43, r0
    bra     party_name_store_upper
    nop
party_name_apostrophe:
    mov     #-39, r0
party_name_store_upper:
    mov     #1, r12
    bra     party_name_store
    nop
party_name_eight:
    mov     #72, r0
    mov     #0, r12
party_name_store:
    mov.b   r0, @r11
    add     #1, r11
party_name_emit_return:
    rts
    nop
    .pool
    .align 4
