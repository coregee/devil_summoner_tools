status_stock_icon_wrapper:
    mov.l   r0, @-r15
    mov.l   =DIRTY, r0
    mov.b   @r0, r0
    tst     r0, r0
    bt      icon_ready
    mov.l   r2, @-r15
    mov.l   r3, @-r15
    mov.l   r4, @-r15
    mov.l   r5, @-r15
    mov.l   r6, @-r15
    mov.l   r7, @-r15
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    sts.l   pr, @-r15
    mov     #0, r8
    mov.l   =BUILD_ATLAS_TILE, r9
restore_panel_atlas:
    mov     #12, r1
    mulu.w  r1, r8
    mov.l   =PANEL_ATLAS_CACHE, r2
    mov.l   r2, @-r15
    mov     #4, r7
    mov     #0, r5
    mov     r8, r4
    sts     macl, r6
    jsr     @r9
    exts.w  r6, r6
    add     #4, r15
    mov     r8, r1
    add     #1, r1
    extu.w  r1, r8
    mov     #20, r2
    cmp/hi  r2, r8
    bf      restore_panel_atlas
    mov.l   =BUILD_ATLAS, r0
    jsr     @r0
    nop
    mov.l   =DIRTY, r0
    mov     #0, r2
    mov.b   r2, @r0
    lds.l   @r15+, pr
    mov.l   @r15+, r9
    mov.l   @r15+, r8
    mov.l   @r15+, r7
    mov.l   @r15+, r6
    mov.l   @r15+, r5
    mov.l   @r15+, r4
    mov.l   @r15+, r3
    mov.l   @r15+, r2
icon_ready:
    mov.l   @r15+, r0
    mov.l   =STOCK, r1
    jmp     @r1
    nop
    .pool
    .align 4
