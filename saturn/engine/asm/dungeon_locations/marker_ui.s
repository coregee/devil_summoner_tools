; Stock ASCII ABI:
;   r4=char*, r5=color, r6=x, r7=y, stack[0]=surface, stack[4]=descriptor.
; Translate the three marker literals to precomposed FONT16 scratch cells, then
; reorder the arguments for the stock raw-u16 row drawer. Unknown pointers keep
; using the original ASCII drawer.
marker_ascii_vwf:
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
    mov     r7, r11
    mov.l   @(32,r15), r12
    mov.l   @(36,r15), r13
    mov.l   =NO_DATA_POINTER, r0
    cmp/eq  r0, r8
    bt      marker_ascii_no_data
    mov.l   =YES_POINTER, r0
    cmp/eq  r0, r8
    bt      marker_ascii_yes
    mov.l   =NO_POINTER, r0
    cmp/eq  r0, r8
    bt      marker_ascii_no
marker_ascii_fallback:
    mov.l   =ASCII_DRAWER, r0
    lds.l   @r15+, pr
    mov.l   @r15+, r14
    mov.l   @r15+, r13
    mov.l   @r15+, r12
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    jmp     @r0
    mov.l   @r15+, r8
marker_ascii_no_data:
    mov.l   =NO_DATA_BITMAP, r4
    mov     #NO_DATA_CELLS, r14
    bra     marker_ascii_draw
    nop
marker_ascii_yes:
    mov.l   =YES_BITMAP, r4
    mov     #YES_CELLS, r14
    bra     marker_ascii_draw
    nop
marker_ascii_no:
    mov.l   =NO_BITMAP, r4
    mov     #NO_CELLS, r14
    mov     #NO_X_BIAS, r0
    add     r0, r10
marker_ascii_draw:
    mov     r14, r5
    bsr     marker_prepare_bitmap
    nop
    mov     r11, r0
    mov.l   r13, @-r15
    mov.l   r12, @-r15
    mov.l   r0, @-r15
    mov.l   =TOP_CODE_ROW, r4
    mov     r14, r5
    mov     r9, r6
    mov     r10, r7
    mov.l   =RAW_DRAWER, r0
    jsr     @r0
    nop
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

; The stock Delete producer is hardcoded to six words. Its caller is redirected
; here so an authored translation can use the same scratch-row path.
marker_delete_vwf:
    sts.l   pr, @-r15
    mov.l   =DELETE_BITMAP, r4
    mov     #DELETE_CELLS, r5
    bsr     marker_prepare_bitmap
    nop
    mov.l   =DRAW_DESCRIPTOR, r0
    mov.l   r0, @-r15
    mov     #DELETE_SURFACE, r0
    mov.l   r0, @-r15
    mov     #0, r0
    mov.l   r0, @-r15
    mov.l   =TOP_CODE_ROW, r4
    mov     #DELETE_CELLS, r5
    mov     #-1, r6
    mov     #0, r7
    mov.l   =RAW_DRAWER, r0
    jsr     @r0
    nop
    add     #12, r15
    lds.l   @r15+, pr
    rts
    nop

; Copy one to four 16x16 cells into the established dungeon-label scratch row.
marker_prepare_bitmap:
    mov.l   =TOP_ADDR, r0
    mov     r5, r1
    shll2   r1
    shll    r1
marker_prepare_long:
    mov.l   @r4+, r2
    mov.l   r2, @r0
    add     #4, r0
    dt      r1
    bf      marker_prepare_long
    rts
    nop
    .align  4
    .pool
