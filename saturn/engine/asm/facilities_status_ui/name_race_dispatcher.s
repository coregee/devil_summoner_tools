status_name_race:
    mov     r5, r0
    cmp/eq  #8, r0
    bt      lookup_name
    cmp/eq  #3, r0
    bf      status_text_fallback
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov     r4, r8
    mov.l   =RACE_SOURCE, r9
    mov.l   =RACE_TABLE, r10
    mov     #43, r11
race_loop:
    cmp/eq  r9, r8
    bt      race_found
    add     #6, r9
    dt      r11
    bf      race_loop
    bra     dispatch_fallback
    nop
race_found:
    mov     #43, r0
    sub     r11, r0
    shll2   r0
    mov.l   @(r0,r10), r0
    bra     dispatch_font16
    nop
lookup_name:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   =CURRENT_NAME_PTR, r0
    mov.l   @r0, r0
    mov.l   @r0, r8
    add     #4, r0
    mov.l   @r0, r0
    xor     r0, r8
    mov.l   =NAME_LOOKUP, r9
    mov.w   =NAME_COUNT, r10
name_loop:
    mov.l   @r9, r0
    cmp/eq  r0, r8
    bt      name_found
    add     #8, r9
    dt      r10
    bf      name_loop
    mov.l   =PARTY_TYPE, r0
    mov.b   @r0, r1
    extu.b  r1, r1
    tst     r1, r1
    bt      player_name
    bra     dispatch_fallback
    nop
player_name:
    mov.l   =PLAYER_NAME, r0
    bra     dispatch_font16
    nop
name_found:
    mov     r9, r0
    add     #4, r0
    mov.l   @r0, r0
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    mov     r0, r4
    mov     #32, r5
    mov.l   =NAME_VWF, r0
    jmp     @r0
    nop
dispatch_font16:
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    mov     r0, r4
    mov.l   =FONT16_VWF, r0
    jmp     @r0
    nop
dispatch_fallback:
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
status_text_fallback:
    mov.l   =STOCK, r0
    jmp     @r0
    nop
    .pool
    .align 4

