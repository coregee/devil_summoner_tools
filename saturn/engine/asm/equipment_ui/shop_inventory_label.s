; Replace the stock two-cell "Inv." tile pair with one editable FONT8 label.
; The two NORMALIZE instructions are rendered as nop for low glyph codes and
; extu.b r0,r0 for high glyph codes whose mov immediate is sign-extended.

shop_panel_glyph:
    mov.l   @r15, r0
    extu.b  r0, r0
    mov     #INVENTORY_TILE_0_SIGNED, r1
    extu.b  r1, r1
    cmp/eq  r1, r0
    bt      shop_inventory_label
    mov     #INVENTORY_TILE_1_SIGNED, r1
    extu.b  r1, r1
    cmp/eq  r1, r0
    bt      shop_inventory_tail
    mov.l   =RAW_GLYPH, r1
    jmp     @r1
    nop

shop_inventory_tail:
    rts
    nop

shop_inventory_label:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    sts.l   pr, @-r15
    mov     r4, r8
    mov     r5, r9
    mov     r6, r10
    mov     r7, r11
    mov.l   @(28,r15), r12
    add     #INITIAL_SHIFT, r10

    mov     #CODE_0, r0
    bsr     shop_inventory_glyph
    @NORMALIZE_0@
    add     #ADVANCE_0, r10
    mov     #CODE_1, r0
    bsr     shop_inventory_glyph
    @NORMALIZE_1@
    add     #ADVANCE_1, r10
    mov     #CODE_2_SIGNED, r0
    extu.b  r0, r0
    bsr     shop_inventory_glyph
    nop
    add     #ADVANCE_2, r10
    mov     #CODE_3_SIGNED, r0
    extu.b  r0, r0
    bsr     shop_inventory_glyph
    nop

    lds.l   @r15+, pr
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8

shop_inventory_glyph:
    sts.l   pr, @-r15
    mov     r8, r4
    mov     r9, r5
    mov     r10, r6
    mov     r11, r7
    mov.l   r12, @-r15
    mov.l   r0, @-r15
    mov.l   =RAW_GLYPH, r1
    jsr     @r1
    nop
    add     #8, r15
    lds.l   @r15+, pr
    rts
    nop
    .pool
