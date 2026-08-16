; Resolve COMBAT Analyze's counted race and demon-name records, then draw
; their translated FONT8 text. Unknown record kinds retain the stock drawer.

smallfont_counted_vwf:
    mov     r5, r0
    cmp/eq  #7, r0
    bt      race_lookup
    cmp/eq  #8, r0
    bf      fallback

    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   @r4, r2
    mov     r4, r0
    add     #4, r0
    mov.l   @r0, r3
    mov.l   =DVL_SOURCE, r0
    mov.w   =DVL_COUNT, r1
name_lookup_loop:
    mov.l   @r0, r8
    cmp/eq  r8, r2
    bf      name_lookup_next
    mov     r0, r8
    add     #4, r8
    mov.l   @r8, r8
    cmp/eq  r8, r3
    bt      name_found
name_lookup_next:
    add     #8, r0
    dt      r1
    bf      name_lookup_loop
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    bra     fallback
    nop
name_found:
    mov.w   =DVL_COUNT, r8
    sub     r1, r8
    mov     r8, r1
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    mov     r1, r0
    shll    r0
    mov.l   =NAME_OFFSETS, r2
    mov.w   @(r0,r2), r1
    extu.w  r1, r1
    mov.l   =NAME_POOL, r4
    add     r1, r4
    bra     setup
    mov     #32, r5

fallback:
    mov.l   =STOCK_COUNTED, r0
    jmp     @r0
    nop

race_lookup:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   =RACE_SOURCE, r0
    mov     #RACE_COUNT, r1
race_lookup_loop:
    mov     r4, r2
    mov     r0, r3
    mov     #6, r10
race_compare_loop:
    mov.b   @r2+, r8
    mov.b   @r3+, r9
    cmp/eq  r8, r9
    bf      race_lookup_next
    dt      r10
    bf      race_compare_loop
    bra     race_found
    nop
race_lookup_next:
    add     #RACE_SOURCE_STRIDE, r0
    dt      r1
    bf      race_lookup_loop
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    bra     fallback
    nop

race_found:
    mov     #RACE_COUNT, r8
    sub     r1, r8
    mov     r8, r1
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    shll2   r1
    shll    r1
    mov.l   =RACE_POOL, r4
    add     r1, r4
    mov     #RACE_RECORD_SIZE, r5

setup:
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
    mov     #0, r11
    mov     r7, r12

loop:
    tst     r9, r9
    bt      done
    mov.b   @r8+, r13
    extu.b  r13, r13
    tst     r13, r13
    bt      done
    mov.l   =WIDTHS, r0
    mov     r13, r1
    mov.b   @(r0,r1), r14
    extu.b  r14, r14
    tst     r14, r14
    bt      japanese

    mov     r10, r4
    mov.w   =STRIDE, r5
    mov     r11, r6
    mov     r13, r7
    mov.l   r12, @-r15
    mov.l   =PIXEL, r0
    jsr     @r0
    nop
    add     #4, r15
    bra     next
    add     r14, r11

japanese:
    mov     r10, r4
    mov.w   =STRIDE, r5
    mov     r11, r6
    shlr2   r6
    shlr    r6
    mov     r13, r7
    mov.l   r12, @-r15
    mov.l   =STOCK_GLYPH, r0
    jsr     @r0
    nop
    add     #4, r15
    add     #8, r11

next:
    add     #-1, r9
    bra     loop
    nop

done:
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
    .pool
