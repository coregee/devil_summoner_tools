status_english_atlas_wrapper:
    mov.l   r8, @-r15
    sts.l   pr, @-r15
    mov.l   =SOURCE_PTR, r8
    mov.l   =EN_ATLAS, r0
    mov.l   r0, @r8
    mov.l   =DIRTY, r8
    mov     #1, r0
    mov.b   r0, @r8
    mov.l   =MASK_PTR, r8
    mov.l   =EN_MASKS, r0
    mov.l   r0, @r8
    mov.l   =ORIGINAL, r0
    jsr     @r0
    nop
    mov.l   =STOCK_MASKS, r0
    mov.l   r0, @r8
    mov.l   =SOURCE_PTR, r8
    mov.l   =STOCK_ATLAS, r0
    mov.l   r0, @r8
    lds.l   @r15+, pr
    rts
    mov.l   @r15+, r8
    .pool
    .align 4
