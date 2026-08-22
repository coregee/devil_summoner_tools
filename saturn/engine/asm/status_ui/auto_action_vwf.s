; Proportionally draw the compact eight-byte item or magic name that the stock
; AUTO summary has already copied into its stack buffer.  The same call site is
; also used for four-byte generic command text, which stays on the stock path.

status_auto_action_vwf:
    mov     r5, r0
    cmp/eq  #8, r0
    bf      auto_action_fallback

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
    mov.l   @(36,r15), r12
    mov.l   @(40,r15), r13
    mov.l   =WIDTHS, r14
    mov     #8, r0
    mov.l   r0, @-r15
auto_compact_loop:
    mov.b   @r8, r1
    extu.b  r1, r1
    tst     r1, r1
    bt      auto_compact_done
    mov     r1, r0
    mov.b   @(r0,r14), r2
    extu.b  r2, r2
    tst     r2, r2
    bt      auto_compact_done
    mov     r10, r0
    add     r2, r0
    mov     #96, r3
    cmp/hi  r3, r0
    bt      auto_compact_done
    mov     r10, r0
    tst     #1, r0
    bt      auto_compact_draw
    mov.l   =FONT_BITMAP, r0
    mov     r1, r2
    shll2   r2
    shll    r2
    add     r2, r0
    mov     #8, r3
auto_compact_shift_right:
    mov.b   @r0, r1
    extu.b  r1, r1
    shlr    r1
    mov.b   r1, @r0
    add     #1, r0
    dt      r3
    bf      auto_compact_shift_right
auto_compact_draw:
    mov.b   @r8, r4
    extu.b  r4, r4
    mov     r9, r5
    mov     r10, r6
    mov     r11, r7
    mov     r10, r0
    tst     #1, r0
    bt      auto_compact_call
    add     #-1, r6
auto_compact_call:
    mov.l   r13, @-r15
    mov.l   r12, @-r15
    mov.l   =GLYPH, r0
    jsr     @r0
    nop
    add     #8, r15
    mov     r10, r0
    tst     #1, r0
    bt      auto_compact_advance
    mov.l   =FONT_BITMAP, r0
    mov.b   @r8, r1
    extu.b  r1, r1
    shll2   r1
    shll    r1
    add     r1, r0
    mov     #8, r3
auto_compact_shift_left:
    mov.b   @r0, r1
    extu.b  r1, r1
    shll    r1
    mov.b   r1, @r0
    add     #1, r0
    dt      r3
    bf      auto_compact_shift_left
auto_compact_advance:
    mov.b   @r8, r1
    extu.b  r1, r1
    mov     r1, r0
    mov.b   @(r0,r14), r2
    extu.b  r2, r2
    add     #1, r2
    add     r2, r10
    add     #1, r8
    mov.l   @r15, r0
    add     #-1, r0
    mov.l   r0, @r15
    tst     r0, r0
    bf      auto_compact_loop
auto_compact_done:
    add     #4, r15
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
