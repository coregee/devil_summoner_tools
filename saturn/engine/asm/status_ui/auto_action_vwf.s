; Recover the selected item or magic record from the active human/demon AUTO
; state, resolve its full translated name, and draw complete proportional
; glyphs through END_X.  Four-byte generic command text stays on the stock path.

status_auto_action_vwf:
    mov     r5, r0
    cmp/eq  #8, r0
    bt      auto_action_lookup
    cmp/eq  #4, r0
    bt      auto_action_shift_prefix
    bra     auto_action_fallback
    nop
auto_action_shift_prefix:
    mov.l   @r15, r0
    add     #4, r0
    mov.l   r0, @r15
    bra     auto_action_fallback
    nop

auto_action_lookup:
    mov.l   =PARTY_TYPE, r0
    mov.b   @r0, r0
    extu.b  r0, r0
    tst     r0, r0
    bt      auto_action_human
    cmp/eq  #2, r0
    bf      auto_action_reject
    mov.l   =DEMON_AUTO_STATE, r0
    mov.l   @r0, r0
    bra     auto_action_state
    add     #64, r0
auto_action_human:
    mov.l   =HUMAN_AUTO_STATE, r0
    mov.l   @r0, r0
    add     #79, r0
auto_action_state:
    mov.b   @r0, r1
    extu.b  r1, r1
    add     #1, r0
    mov.b   @r0, r2
    extu.b  r2, r2
    tst     r2, r2
    bt      auto_action_reject
    mov     r1, r0
    cmp/eq  #7, r0
    bt      auto_action_item
    cmp/eq  #6, r0
    bt      auto_action_magic
    mov     #24, r3
    cmp/hs  r3, r1
    bf      auto_action_reject
    mov     #27, r3
    cmp/hi  r3, r1
    bt      auto_action_reject
auto_action_magic:
    mov.l   =MAGIC_BASE, r1
    bra     auto_action_resolve
    nop
auto_action_item:
    mov.l   =ITEM_BASE, r1
auto_action_resolve:
    mov     #96, r3
    mul.l   r3, r2
    sts     macl, r4
    add     r1, r4
    add     #-92, r4
    mov     r4, r0
    add     #NAME_POINTER, r0
    mov.w   @r0, r0
    extu.w  r0, r0
    add     r1, r0
    mov     r0, r4
    bra     auto_action_draw
    nop
auto_action_reject:
    bra     auto_action_fallback
    nop

auto_action_draw:
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
    mov.l   @(32,r15), r11
    add     #4, r11
    mov.l   @(36,r15), r12
    mov.l   @(40,r15), r13
    mov.l   =WIDTHS, r14
    mov.l   r10, @-r15
    mov     #0, r0
    mov.l   r0, @-r15
    mov.l   r0, @-r15

    ; Keep a fitting name on the stock line.  Otherwise remember the last
    ; usable space (or the first overflowing glyph) as the upward wrap point.
    mov     r8, r4
    mov     r10, r5
    mov     #0, r6
auto_measure_loop:
    mov.b   @r4, r1
    extu.b  r1, r1
    mov     #0xff, r0
    extu.b  r0, r0
    cmp/eq  r0, r1
    bt      auto_measure_done
    mov     r1, r0
    cmp/eq  #SPACE_CODE, r0
    bf      auto_measure_width
    mov     r4, r6
auto_measure_width:
    mov     r1, r0
    mov.b   @(r0,r14), r2
    extu.b  r2, r2
    tst     r2, r2
    bt      auto_measure_done
    mov     r5, r0
    add     r2, r0
    mov     #END_X, r3
    cmp/hi  r3, r0
    bt      auto_measure_wrap
    add     #1, r2
    add     r2, r5
    add     #1, r4
    bra     auto_measure_loop
    nop
auto_measure_wrap:
    ; Prefer the last space only when its remaining suffix also fits.  A name
    ; such as "7 Shooting Stars" instead needs a balanced glyph-boundary wrap.
    mov     r4, r5
    tst     r6, r6
    bt      auto_measure_store
    mov     r6, r7
    add     #1, r7
    mov     r10, r3
auto_measure_suffix:
    mov.b   @r7, r1
    extu.b  r1, r1
    mov     #0xff, r0
    extu.b  r0, r0
    cmp/eq  r0, r1
    bt      auto_measure_space_wrap
    mov     r1, r0
    mov.b   @(r0,r14), r2
    extu.b  r2, r2
    tst     r2, r2
    bt      auto_measure_store
    mov     r3, r0
    add     r2, r0
    mov     #END_X, r1
    cmp/hi  r1, r0
    bt      auto_measure_store
    add     #1, r2
    add     r2, r3
    bra     auto_measure_suffix
    add     #1, r7
auto_measure_space_wrap:
    mov     r6, r4
    mov     r6, r5
    bra     auto_measure_store
    add     #1, r5
auto_measure_store:
    mov.l   r4, @r15
    mov.l   r5, @(4,r15)
    add     #-8, r11
auto_measure_done:
auto_full_loop:
    mov.l   @r15, r0
    tst     r0, r0
    bt      auto_full_character
    cmp/eq  r0, r8
    bf      auto_full_character
    mov.l   @(4,r15), r8
    mov     #0, r0
    mov.l   r0, @r15
    add     #8, r11
    mov.l   @(8,r15), r10
    bra     auto_full_loop
    nop
auto_full_character:
    mov.b   @r8, r1
    extu.b  r1, r1
    mov     #0xff, r0
    extu.b  r0, r0
    cmp/eq  r0, r1
    bt      auto_full_done
    mov     r1, r0
    mov.b   @(r0,r14), r2
    extu.b  r2, r2
    tst     r2, r2
    bt      auto_full_done
    mov     r10, r0
    add     r2, r0
    mov     #END_X, r3
    cmp/hi  r3, r0
    bt      auto_full_done
    mov     r10, r0
    tst     #1, r0
    bt      auto_full_draw
    mov.l   =FONT_BITMAP, r0
    mov     r1, r2
    shll2   r2
    shll    r2
    add     r2, r0
    mov     #8, r3
auto_full_shift_right:
    mov.b   @r0, r1
    extu.b  r1, r1
    shlr    r1
    mov.b   r1, @r0
    add     #1, r0
    dt      r3
    bf      auto_full_shift_right
auto_full_draw:
    mov.b   @r8, r4
    extu.b  r4, r4
    mov     r9, r5
    mov     r10, r6
    mov     r11, r7
    mov     r10, r0
    tst     #1, r0
    bt      auto_full_call
    add     #-1, r6
auto_full_call:
    mov.l   r13, @-r15
    mov.l   r12, @-r15
    mov.l   =GLYPH, r0
    jsr     @r0
    nop
    add     #8, r15
    mov     r10, r0
    tst     #1, r0
    bt      auto_full_advance
    mov.l   =FONT_BITMAP, r0
    mov.b   @r8, r1
    extu.b  r1, r1
    shll2   r1
    shll    r1
    add     r1, r0
    mov     #8, r3
auto_full_shift_left:
    mov.b   @r0, r1
    extu.b  r1, r1
    shll    r1
    mov.b   r1, @r0
    add     #1, r0
    dt      r3
    bf      auto_full_shift_left
auto_full_advance:
    mov.b   @r8, r1
    extu.b  r1, r1
    mov     r1, r0
    mov.b   @(r0,r14), r2
    extu.b  r2, r2
    add     #1, r2
    add     r2, r10
    bra     auto_full_loop
    add     #1, r8
auto_full_done:
    add     #12, r15
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    rts
    mov.l   @r15+, r8
auto_action_fallback:
    mov.l   =STOCK, r0
    jmp     @r0
    nop
    .pool
    .align 4
