level_up_name_drawer:
    sts.l   pr, @-r15
    mov.l   =SURFACE, r5
    mov.l   =PREPARE, r1
    jsr     @r1
    mov     #17, r4
    mov.l   =SURFACE, r0
    mov.l   r0, @-r15
    mov     #17, r0
    mov.l   r0, @-r15
    mov     #0, r0
    mov.l   r0, @-r15
    mov     #0, r7
    mov     #2, r6
    mov     #8, r5
    mov.l   =CHARACTER_SELECTOR, r0
    mov.w   @r0, r1
    extu.w  r1, r1
    tst     r1, r1
    bt      level_up_player_name
    mov     #CHARACTER_COUNT, r2
    cmp/hi  r2, r1
    bt      level_up_player_name
    add     #-1, r1
    shll2   r1
    mov.l   =CHARACTER_TABLE, r0
    bra     level_up_draw_name
    mov.l   @(r0,r1), r4
level_up_player_name:
    mov.l   =PLAYER_NAME, r4
level_up_draw_name:
    mov.l   =FONT16_VWF, r1
    jsr     @r1
    nop
    add     #12, r15
    lds.l   @r15+, pr
    rts
    nop
    .pool
    .align 4
