; Resolve fixed shop rows to full editable names.  Unknown rows, including the
; live player codename, retain the ordinary proportional per-glyph path.

shop_character_name_vwf:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15

    mov     r9, r13
    mov.l   @(0x20,r15), r8
    extu.b  r8, r8
    tst     r8, r8
    bt      shop_character_name_done
    mov     r4, r9
    mov     r5, r10
    mov     r6, r11
    mov     r7, r12
    mov.l   @(0x24,r15), r14

    mov     r11, r3
    mov     #0, r2
    tst     r3, r3
    bt      shop_character_name_reset
    mov     r3, r0
    cmp/eq  #8, r0
    bf      shop_character_name_position
    mov.l   =LAST_FIXED, r0
    mov.l   @r0, r0
    tst     r0, r0
    bt      shop_character_name_position
shop_character_name_reset:
    mov.l   =STATE, r0
    mov.l   r3, @r0
    mov.l   =SUPPRESS, r0
    mov     #0, r1
    mov.l   r1, @r0
    mov     #1, r2

shop_character_name_position:
    mov.l   =LAST_FIXED, r0
    mov.l   r3, @r0
    tst     r2, r2
    bt      shop_character_name_suppress

    ; Contiguous callers increment their source pointer before this callback.
    mov     r13, r4
    add     #-1, r4
    mov     #1, r5
    bsr     shop_character_name_match
    nop
    tst     r0, r0
    bt      shop_character_name_try_party_row
    bra     shop_character_name_full
    nop

shop_character_name_try_party_row:
    ; The second comparison row uses fixed character slot 1 directly.
    mov.l   =PARTY_SOURCE_PTR, r0
    mov.l   @r0, r0
    add     #8, r0
    cmp/eq  r13, r0
    bf      shop_character_name_try_stride
    mov.l   =MATCHES, r1
    add     #8, r1
    mov.w   @r1, r0
    extu.w  r0, r0
    mov.l   =NAME_POOL, r1
    add     r1, r0
    bra     shop_character_name_full
    nop

shop_character_name_try_stride:
    mov     r13, r4
    mov     #8, r5
    bsr     shop_character_name_match
    nop
    tst     r0, r0
    bf      shop_character_name_full

shop_character_name_suppress:
    mov.l   =SUPPRESS, r0
    mov.l   @r0, r1
    tst     r1, r1
    bt      shop_character_name_single
    add     #-1, r1
    mov.l   r1, @r0
    bra     shop_character_name_done
    nop

shop_character_name_single:
    mov.l   =WIDTHS, r0
    mov.b   @(r0,r8), r1
    extu.b  r1, r1
    tst     r1, r1
    bt      shop_character_name_fallback
    mov.l   =STATE, r0
    mov.l   @r0, r6
    mov     r6, r3
    add     r1, r3
    mov.l   r3, @r0

    mulu.w  r10, r12
    sts     macl, r0
    shlr    r0
    add     r0, r9
    mov     r9, r4
    mov     r10, r5
    mov     r8, r7
    mov.l   r14, @-r15
    mov.l   =PIXEL, r0
    jsr     @r0
    nop
    add     #4, r15
    bra     shop_character_name_done
    nop

shop_character_name_full:
    mov     r0, r13
    mov.b   @r13+, r1
    extu.b  r1, r1
    mov     r11, r2
    add     r1, r2
    cmp/hi  r10, r2
    bf      shop_character_name_full_position
    mov     #0, r11
shop_character_name_full_position:
    mov.l   =SUPPRESS, r0
    mov     #7, r1
    mov.l   r1, @r0
    mulu.w  r10, r12
    sts     macl, r0
    shlr    r0
    add     r0, r9

shop_character_name_full_loop:
    mov.b   @r13+, r8
    extu.b  r8, r8
    tst     r8, r8
    bt      shop_character_name_full_done
    mov.l   =WIDTHS, r0
    mov.b   @(r0,r8), r1
    extu.b  r1, r1
    tst     r1, r1
    bt      shop_character_name_full_done
    mov     r11, r6
    add     r1, r11
    mov     r9, r4
    mov     r10, r5
    mov     r8, r7
    mov.l   r14, @-r15
    mov.l   =PIXEL, r0
    jsr     @r0
    nop
    add     #4, r15
    bra     shop_character_name_full_loop
    nop

shop_character_name_full_done:
    mov.l   =STATE, r0
    mov.l   r11, @r0

shop_character_name_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

shop_character_name_fallback:
    mov     r9, r4
    mov     r10, r5
    mov     r11, r6
    mov     r12, r7
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    mov.l   =RAW_GLYPH, r0
    jmp     @r0
    nop

; r4=source candidate, r5=source stride. Returns a width-prefixed name in r0.
shop_character_name_match:
    mov.l   r8, @-r15
    mov.l   =MATCHES, r0
    mov     #MATCH_COUNT, r1
shop_character_name_match_entry:
    mov     r0, r2
    mov     r4, r3
    mov     #8, r6
shop_character_name_match_byte:
    mov.b   @r2+, r7
    extu.b  r7, r7
    mov.b   @r3, r8
    extu.b  r8, r8
    cmp/eq  r7, r8
    bf      shop_character_name_match_next
    add     r5, r3
    dt      r6
    bf      shop_character_name_match_byte
    mov.w   @r2, r0
    extu.w  r0, r0
    mov.l   =NAME_POOL, r1
    add     r1, r0
    rts
    mov.l   @r15+, r8

shop_character_name_match_next:
    add     #10, r0
    dt      r1
    bf      shop_character_name_match_entry
    mov     #0, r0
    rts
    mov.l   @r15+, r8
    .pool
    .align 4
