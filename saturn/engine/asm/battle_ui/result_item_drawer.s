; Draw up to four combat-result item rewards through ITEMNAME's full strings.

combat_result_item_vwf:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     #0, r9

next_item:
    mov.w   @r8+, r0
    extu.w  r0, r0
    tst     r0, r0
    bt      done
    mov     #0x60, r1
    mul.l   r1, r0
    sts     macl, r10
    mov.l   =ITEM_BEFORE_FIRST, r1
    add     r1, r10
    mov     r10, r1
    add     #94, r1
    mov.w   @r1, r0
    extu.w  r0, r0
    mov.l   =ITEM_BASE, r1
    add     r1, r0
    mov     r0, r10

    mov     r9, r0
    tst     r0, r0
    bt      dest0
    cmp/eq  #1, r0
    bt      dest1
    cmp/eq  #2, r0
    bt      dest2
    mov.l   =DEST3, r11
    bra     draw_setup
    nop
dest0:
    mov.l   =DEST0, r11
    bra     draw_setup
    nop
dest1:
    mov.l   =DEST1, r11
    bra     draw_setup
    nop
dest2:
    mov.l   =DEST2, r11

draw_setup:
    mov     #0, r12
    mov     #32, r14

glyph:
    mov.b   @r10+, r13
    extu.b  r13, r13
    mov     #-1, r0
    extu.b  r0, r0
    cmp/eq  r0, r13
    bt      row_done
    mov.l   =WIDTHS, r0
    mov     r13, r1
    mov.b   @(r0,r1), r0
    extu.b  r0, r0
    tst     r0, r0
    bt      row_done
    mov     r12, r1
    add     r0, r1
    mov     #MAX_WIDTH, r2
    cmp/hi  r2, r1
    bt      row_done

    mov     r11, r4
    mov     #2, r5
    shll8   r5
    mov     r12, r6
    mov     r13, r7
    mov.l   r0, @-r15
    mov     #2, r0
    mov.l   r0, @-r15
    mov.l   =PIXEL, r0
    jsr     @r0
    nop
    add     #4, r15
    mov.l   @r15+, r0
    add     r0, r12
    dt      r14
    bf      glyph

row_done:
    add     #1, r9
    mov     #4, r0
    cmp/hs  r0, r9
    bf      next_item

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
