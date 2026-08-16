; Draw editable equipment actions and comparison headings with proportional
; FONT8 glyphs.  Text and width tables are linked after this code by Python.

equipment_draw_labels_vwf:
    mov     #4, r0
    cmp/eq  r0, r5
    bt      draw_recommend
    mov     #3, r0
    cmp/eq  r0, r5
    bt      draw_unequip
    mov.l   =STOCK_DRAW, r0
    jmp     @r0
    nop

draw_recommend:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r6, r9
    mov     r7, r10
    mov.l   @(0x20,r15), r11
    mov.l   =S_RECOMMEND, r8
    bsr     draw_one_label
    nop

    mov     #0, r9
    mov.l   =S_STRENGTH, r8
    mov     #-54, r10
    mov     #0, r11
    bsr     draw_one_label
    nop
    mov.l   =S_SWORD_ATTACK, r8
    mov     #-16, r10
    mov     #0, r11
    bsr     draw_one_label
    nop
    mov.l   =S_INTELLIGENCE, r8
    mov     #-54, r10
    mov     #14, r11
    bsr     draw_one_label
    nop
    mov.l   =S_SWORD_ACCURACY, r8
    mov     #-16, r10
    mov     #14, r11
    bsr     draw_one_label
    nop
    mov.l   =S_MAGIC, r8
    mov     #-54, r10
    mov     #28, r11
    bsr     draw_one_label
    nop
    mov.l   =S_GUN_ATTACK, r8
    mov     #-16, r10
    mov     #28, r11
    bsr     draw_one_label
    nop
    mov.l   =S_VITALITY, r8
    mov     #-54, r10
    mov     #42, r11
    bsr     draw_one_label
    nop
    mov.l   =S_GUN_ACCURACY, r8
    mov     #-16, r10
    mov     #42, r11
    bsr     draw_one_label
    nop
    mov.l   =S_AGILITY, r8
    mov     #-54, r10
    mov     #56, r11
    bsr     draw_one_label
    nop
    mov.l   =S_DEFENSE, r8
    mov     #-16, r10
    mov     #56, r11
    bsr     draw_one_label
    nop
    mov.l   =S_LUCK, r8
    mov     #-54, r10
    mov     #70, r11
    bsr     draw_one_label
    nop
    mov.l   =S_EVASION, r8
    mov     #-16, r10
    mov     #70, r11
    bsr     draw_one_label
    nop
    mov.l   =S_MAGIC_POWER, r8
    mov     #-16, r10
    mov     #84, r11
    bsr     draw_one_label
    nop
    mov.l   =S_MAGIC_EFFECT, r8
    mov     #-16, r10
    mov     #98, r11
    bsr     draw_one_label
    nop
    bra     labels_done
    nop

draw_unequip:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    mov     r6, r9
    mov     r7, r10
    mov.l   @(0x20,r15), r11
    mov.l   =S_UNEQUIP, r8
    bsr     draw_one_label
    nop

labels_done:
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

draw_one_label:
    sts.l   pr, @-r15
    mov     #16, r12
label_loop:
    mov.b   @r8+, r14
    extu.b  r14, r14
    mov     #0xff, r0
    extu.b  r0, r0
    cmp/eq  r0, r14
    bt      label_done
    mov.l   =WIDTHS, r0
    mov     r14, r1
    mov.b   @(r0,r1), r1
    extu.b  r1, r1
    mov     r14, r4
    mov     r9, r5
    mov     r10, r6
    add     r1, r10
    mov     r11, r7
    mov.l   =GLYPH, r0
    jsr     @r0
    nop
    dt      r12
    bf      label_loop
label_done:
    lds.l   @r15+, pr
    rts
    nop
    .pool
    .align 4
