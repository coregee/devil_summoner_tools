; Draw a relocated ITEMNAME name in the shop BUY/SELL list.

buy_sell_item_name_vwf:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    extu.w  r4, r4
    mov     #96, r0
    mul.l   r0, r4
    sts     macl, r0
    add     #-2, r0
    mov.l   =ITEM_BASE, r1
    add     r1, r0
    mov.w   @r0, r0
    extu.w  r0, r0
    add     r1, r0
    mov     r0, r8
    mov     r5, r9
    mov     r6, r10
    extu.w  r7, r11
    mov.l   =FRAMEBUFFER_PTR, r0
    mov.l   @r0, r12
    mov     #52, r0
    mulu.w  r0, r11
    sts     macl, r0
    add     r0, r12
    mov     #0, r14
    mov     #32, r11
buy_loop:
    mov.b   @r8+, r13
    extu.b  r13, r13
    mov     #0xff, r0
    extu.b  r0, r0
    cmp/eq  r0, r13
    bt      buy_done
    mov.l   =WIDTHS, r0
    mov     r13, r1
    mov.b   @(r0,r1), r1
    extu.b  r1, r1
    tst     r1, r1
    bt      buy_done
    mov     r14, r0
    add     r1, r0
    mov     #80, r2
    cmp/hi  r2, r0
    bt      buy_done
    mov     r0, r14
    mov     r12, r4
    mov     #104, r5
    mov     r10, r6
    add     r1, r10
    mov     r13, r7
    mov.l   r9, @-r15
    mov.l   =PIXEL, r0
    jsr     @r0
    nop
    add     #4, r15
    dt      r11
    bf      buy_loop
buy_done:
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
    .align 4
