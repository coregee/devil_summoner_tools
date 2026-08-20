status_skill_dispatch:
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   @r4, r8
    mov.l   @(4,r4), r9
    mov.l   =ambiguous_keys, r10
    mov     #4, r11
check_ambiguous:
    mov.l   @r10+, r0
    mov.l   @r10+, r1
    cmp/eq  r0, r8
    bf      check_ambiguous_next
    cmp/eq  r1, r9
    bt      dispatch_stock
check_ambiguous_next:
    dt      r11
    bf      check_ambiguous
lookup_start:
    mov.l   =MAGIC_FIRST, r10
    mov     #-1, r11
    extu.b  r11, r11
lookup_loop:
    mov.l   @r10, r0
    cmp/eq  r0, r8
    bf      lookup_next
    mov.l   @(4,r10), r0
    cmp/eq  r0, r9
    bt      dispatch_vwf
lookup_next:
    add     #96, r10
    dt      r11
    bf      lookup_loop
    bra     dispatch_stock
    nop
dispatch_vwf:
    mov     r10, r4
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    mov.l   =SKILL_VWF, r0
    jmp     @r0
    nop
dispatch_stock:
    mov.l   @r15+, r11
    mov.l   @r15+, r10
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    mov.l   =STOCK, r0
    jmp     @r0
    nop
    .pool
    .align 4
ambiguous_keys:
    .long   AMBIG0_HI, AMBIG0_LO
    .long   AMBIG1_HI, AMBIG1_LO
    .long   AMBIG2_HI, AMBIG2_LO
    .long   AMBIG3_HI, AMBIG3_LO

