; Resolve the full ITEMNAME string for the battle event-window item grid.

combat_event_item_vwf:
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

    mov     r8, r0
    add     #ITEM_FULL_NAME_FROM_COMPACT, r0
    mov.w   @r0, r0
    extu.w  r0, r0
    mov.l   =ITEM_BASE_POINTER, r1
    mov.l   @r1, r8
    add     r0, r8

    mov     #0, r11
    mov     r9, r12
divide_slot:
    mov     #3, r0
    cmp/hs  r0, r12
    bf      slot_ready
    add     #-3, r12
    add     #1, r11
    bra     divide_slot
    nop

slot_ready:
    mov     #COLUMN_WIDTH, r0
    mulu.w  r0, r12
    sts     macl, r12
    add     #START_X, r12

    mov     #ROW_HEIGHT, r0
    mulu.w  r0, r11
    sts     macl, r11
    add     #START_Y, r11
    mov.l   =FRAMEBUFFER_POINTER, r0
    mov.l   @r0, r9
    mov.w   =FRAMEBUFFER_BYTE_STRIDE, r0
    mulu.w  r0, r11
    sts     macl, r11
    add     r11, r9
    mov     #0, r11

loop:
    mov.b   @r8+, r13
    extu.b  r13, r13
    mov     #-1, r0
    extu.b  r0, r0
    cmp/eq  r0, r13
    bt      done
    mov.l   =WIDTHS, r0
    mov     r13, r1
    mov.b   @(r0,r1), r14
    extu.b  r14, r14
    tst     r14, r14
    bt      done
    mov     r11, r0
    add     r14, r0
    mov     #MAX_WIDTH, r1
    cmp/hi  r1, r0
    bt      done

    mov     r9, r4
    mov.w   =FRAMEBUFFER_STRIDE, r5
    mov     r12, r6
    add     r11, r6
    mov     r13, r7
    mov.l   r10, @-r15
    mov.l   =PIXEL, r0
    jsr     @r0
    nop
    add     #4, r15
    add     r14, r11
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
