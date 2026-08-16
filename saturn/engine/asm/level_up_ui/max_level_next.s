; Select the authored seven-cell NEXT fallback at level 99. The alternate
; path preserves the stock numeric NEXT calculation and coordinates.
    mov     r14, r0
    cmp/eq  #99, r0
    bf.s    level_up_numeric_next
    mov     #-24, r7

    mov.l   =MAX_LEVEL_TEXT, r4
    mov     #7, r5
    mov     #-124, r6
    mov.l   =STRING_DRAWER, r0
    jsr     @r0
    mov     #-24, r7
    bra     CONTINUE
    nop

level_up_numeric_next:
    mov.l   @r8, r2
    mov     r2, r1
    add     #26, r1
    mov.w   @r1, r1
    extu.w  r1, r1
    mov     r1, r0
    shll2   r0
    mov.l   =NEXT_TABLE, r1
    mov.l   @(r0,r1), r4
    mov     #-76, r6
    mov.l   @r2, r1
    mov     #0, r5
    jsr     @r9
    sub     r1, r4
    bra     CONTINUE
    nop

MAX_LEVEL_TEXT:
    .byte   MAX_LEVEL_0, MAX_LEVEL_1, MAX_LEVEL_2, MAX_LEVEL_3
    .byte   MAX_LEVEL_4, MAX_LEVEL_5, MAX_LEVEL_6
    .pool
    .word   0x0000
