; Follow ITEMNAME's relocated full-name pointer and draw up to 80 pixels.

equipment_item_name_vwf:
    mov.l   =ITEM_FIRST, r0
    cmp/hs  r0, r4
    bf      equipment_fallback
    mov.l   =ITEM_END, r0
    cmp/hi  r4, r0
    bf      equipment_fallback
    mov     r4, r1
    add     #90, r1
    mov.w   @r1, r0
    extu.w  r0, r0
    mov.l   =ITEM_BASE, r4
    add     r0, r4

    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r6, r9
    mov     r7, r10
    mov.l   @(0x20,r15), r11
    add     #-1, r11
    mov     #0, r12
    mov     #32, r13
equipment_loop:
    mov.b   @r8+, r14
    extu.b  r14, r14
    mov     #0xff, r0
    extu.b  r0, r0
    cmp/eq  r0, r14
    bt      equipment_done
    mov.l   =WIDTHS, r0
    mov     r14, r1
    mov.b   @(r0,r1), r1
    extu.b  r1, r1
    tst     r1, r1
    bt      equipment_done
    mov     r12, r0
    add     r1, r0
    mov     #80, r2
    cmp/hi  r2, r0
    bt      equipment_done
    mov     r0, r12
    mov     r14, r4
    mov     r9, r5
    mov     r10, r6
    add     r1, r10
    mov     r11, r7
    mov.l   =GLYPH, r0
    jsr     @r0
    nop
    dt      r13
    bf      equipment_loop
equipment_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
equipment_fallback:
    mov.l   =STOCK, r0
    jmp     @r0
    nop
    .pool
    .align 4
